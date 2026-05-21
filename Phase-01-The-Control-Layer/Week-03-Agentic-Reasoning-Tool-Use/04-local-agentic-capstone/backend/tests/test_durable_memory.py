import os
import tempfile
import json
from modules.memory.durable_memory import DurableMemoryStore, assemble_prompt_from_zones, parse_and_apply_response
from modules.memory.integration import DurableMemoryManager
from modules.schemas.type_safety import SupportAIService
from modules.memory.durable_memory import WRITEBACK_INSTRUCTION


def test_add_and_persist_and_load():
    td = tempfile.TemporaryDirectory()
    path = os.path.join(td.name, "memories.json")
    store = DurableMemoryStore(path=path, token_budget=100)
    m1 = store.add_memory("preferences", {"theme": "dark"}, importance=0.9, token_count=10)
    m2 = store.add_memory("past_issues", {"id": 123, "summary": "foo"}, importance=0.4, token_count=20)
    assert os.path.exists(path)
    # reload
    store2 = DurableMemoryStore(path=path, token_budget=100)
    allm = store2.list_memories()
    assert any(m.id == m1.id for m in allm)
    assert any(m.id == m2.id for m in allm)


def test_hydration_attention_zones():
    td = tempfile.TemporaryDirectory()
    path = os.path.join(td.name, "memories.json")
    store = DurableMemoryStore(path=path, token_budget=100)
    # create several memories with varying token counts and importance
    for i in range(10):
        store.add_memory("past_issues", {"i": i}, importance=0.2 + 0.08 * i, token_count=10)

    zones = store.hydrate(types=["past_issues"], max_tokens=100, top_pct=0.25, bottom_pct=0.10)
    assert "top" in zones and "middle" in zones and "bottom" in zones
    top_tokens = sum(m.token_count for m in zones["top"])
    bottom_tokens = sum(m.token_count for m in zones["bottom"])
    assert top_tokens <= int(100 * 0.25)
    assert bottom_tokens <= int(100 * 0.10)


def test_apply_patches_upsert_delete():
    td = tempfile.TemporaryDirectory()
    path = os.path.join(td.name, "memories.json")
    store = DurableMemoryStore(path=path, token_budget=100)
    # upsert new
    patches = [{"op": "upsert", "type": "preferences", "content": {"k": "v"}, "importance": 0.7}]
    res = store.apply_patches(patches)
    assert res[0]["ok"]
    mid = res[0]["id"]
    # update existing
    res2 = store.apply_patches([{"op": "upsert", "id": mid, "content": {"k": "v2"}}])
    assert res2[0]["ok"]
    # delete
    res3 = store.apply_patches([{"op": "delete", "id": mid}])
    assert res3[0]["ok"]


def test_assemble_and_parse_apply():
    td = tempfile.TemporaryDirectory()
    path = os.path.join(td.name, "memories.json")
    store = DurableMemoryStore(path=path, token_budget=100)
    store.add_memory("preferences", {"lang": "en"}, importance=0.8, token_count=5)
    zones = store.hydrate(types=None, max_tokens=100, top_pct=0.25, bottom_pct=0.10)
    prompt_section = assemble_prompt_from_zones(zones)
    assert "Memory Peak (Top)" in prompt_section or "Low-Attention Zone" in prompt_section

    # simulate LLM patches JSON
    patches = [{"op": "upsert", "type": "preferences", "content": {"lang": "fr"}}]
    text = """PATCHES:\n""" + json.dumps(patches)
    res = parse_and_apply_response(store, text)
    assert "applied" in res and isinstance(res["applied"], list)


def test_manager_apply_and_service_prompt():
    td = tempfile.TemporaryDirectory()
    path = os.path.join(td.name, "memories.json")
    store = DurableMemoryStore(path=path, token_budget=100)
    mgr = DurableMemoryManager(store=store)
    store.add_memory("preferences", {"lang": "en"}, importance=0.8, token_count=5)
    section = mgr.store.hydrate(types=None, max_tokens=100)
    assembled = assemble_prompt_from_zones(section, max_tokens=100)
    assert WRITEBACK_INSTRUCTION not in assembled

    # Service prompt should include the instruction as well
    td2 = tempfile.TemporaryDirectory()
    state_path = os.path.join(td2.name, "conversation.json")
    svc = SupportAIService(state_path=state_path, token_budget=100)
    prompt = svc._build_prompt("Hello, I need help")
    # ensure system instruction containing write-back guidance is stored
    system_msgs = [m for m in svc.conversation.messages if m.role == "system"]
    assert system_msgs and WRITEBACK_INSTRUCTION in system_msgs[0].content


def test_prompt_size_reduction_for_simple_intent():
    td3 = tempfile.TemporaryDirectory()
    state_path2 = os.path.join(td3.name, "conversation.json")
    svc = SupportAIService(state_path=state_path2, token_budget=1000)
    # create some conversation history
    svc.conversation.append_message("user", "I have an issue with billing charges that are unexpected.", 10)
    svc.conversation.append_message("assistant", "Sorry to hear that. Can you share your invoice number?", 12)
    svc.conversation.append_message("user", "Invoice 12345. Also, I need status update.", 8)

    simple_prompt = svc._build_prompt("What's the status?", intent="simple")
    complex_prompt = svc._build_prompt("I'm being charged twice on my bill", intent="complex")
    # estimate token counts by word count
    simple_tokens = len(simple_prompt.split())
    complex_tokens = len(complex_prompt.split())
    assert simple_tokens <= complex_tokens
