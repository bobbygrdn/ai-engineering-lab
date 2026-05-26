"""Simple end-to-end smoke test script.

- Creates a temporary SQLite state store
- Patches reflection.run_reflection_pipeline to return deterministic results
- Registers a user, posts two /api/handle calls to simulate writeback + recall
- Checks DB for stored messages and prints results

Run with: venv\\Scripts\\python.exe scripts\\smoke_test.py
"""
import tempfile
import json
from fastapi.testclient import TestClient
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))  # backend/ as import root

import app as app_module
from app import app
from modules.schemas.type_safety import SupportAIService
from modules.state import SQLiteStateStore
import modules.logic.reflection as reflection_mod


def make_fake_reflection():
    class FakeReflectionResult:
        def __init__(self, text: str):
            self.final_text = text
            self.policy_compliant = True
            self.attempts = 1
            self.generation_latency = 0.01
            self.critique_latency = 0.0
            self.total_latency = 0.01
            self.reviews = []
            self.usage = {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
                "interaction_price": 0.0,
            }

    captured = {"prompts": []}

    def fake_run_reflection(prompt_text: str, **kwargs):
        captured["prompts"].append(prompt_text)
        if len(captured["prompts"]) == 1:
            text = (
                "Acknowledged. PATCHES:["
                '{"op":"upsert","type":"preferences","content":{"communication_preference":"email updates"},"importance":0.9,"token_count":6}'
                "]"
            )
        else:
            text = "You prefer email updates for communication."
        return FakeReflectionResult(text)

    return fake_run_reflection, captured


def run():
    tmpdir = tempfile.TemporaryDirectory()
    db_path = Path(tmpdir.name) / "app_state.db"

    store = SQLiteStateStore(db_path=str(db_path))
    store.init_db()

    # patch global app state to use temp DB
    app.dependency_overrides = {}
    app_module.state_store = store
    app_module.ai_service = SupportAIService(state_store=store)

    client = TestClient(app_module.app)

    fake_reflection, captured = make_fake_reflection()
    reflection_mod.run_reflection_pipeline = fake_reflection

    # Register user with unique name
    import uuid
    username = f"smoke_user_{uuid.uuid4().hex[:8]}"
    password = "StrongPass123!"
    email = f"{username}@example.com"
    r = client.post("/api/auth/register", json={"username": username, "email": email, "password": password})
    print("register:", r.status_code, r.text)
    if r.status_code != 200:
        print("Register failed; aborting")
        return 2
    body = r.json()
    token = body.get("access_token")
    user_id = body.get("user", {}).get("id")

    headers = {"Authorization": f"Bearer {token}"}

    # First handle - should apply PATCHES
    r1 = client.post("/api/handle", json={"email_text": "I prefer email updates for account alerts."}, headers=headers)
    print("first handle (http):", r1.status_code, r1.text[:500])

    # Also invoke the service handler directly to ensure the generator finalizer runs
    for event in app_module.ai_service.handle_ticket("I prefer email updates for account alerts.", user_id=user_id, request_meta={}):
        pass

    # Login again to simulate a new session
    rlogin = client.post("/api/auth/login", json={"username": username, "password": password})
    new_token = rlogin.json().get("access_token")
    headers2 = {"Authorization": f"Bearer {new_token}"}

    r2 = client.post("/api/handle", json={"email_text": "What communication preference do I have?"}, headers=headers2)
    print("second handle (http):", r2.status_code, r2.text[:500])

    for event in app_module.ai_service.handle_ticket("What communication preference do I have?", user_id=user_id, request_meta={}):
        pass

    # Inspect DB
    # read back from the same temporary DB
    store2 = SQLiteStateStore(db_path=str(db_path))
    msgs = store2.get_recent_messages(user_id=user_id or 1, limit=10)
    print("messages:", json.dumps(msgs, indent=2))

    print("captured prompts count:", len(captured["prompts"]))
    print("captured prompts sample:", captured["prompts"]) 

    # close TestClient and clear references to allow the temp dir to be removed on Windows
    try:
        client.close()
    except Exception:
        pass

    del app_module.state_store
    del app_module.ai_service
    del store
    del store2

    try:
        tmpdir.cleanup()
    except Exception as e:
        print("Failed to cleanup tempdir; please remove:", db_path)
        print("Cleanup error:", e)
    return 0


if __name__ == "__main__":
    rc = run()
    sys.exit(rc)
