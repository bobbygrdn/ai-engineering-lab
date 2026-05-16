# Part 4 Local Agentic Capstone

## Daily Progress

- **Date:** 2026-05-15
  - **Summary:** Implemented type-safe LLM-backed support ticket classifier, retry/error handling, file-based invalid-output logging, FastAPI endpoints, and a minimal React frontend UI. Added unit tests for backend logic and endpoints.
  - **Completed:**
    - **Backend — Schemas:** type_safety.py — implemented `SupportTicket`, `Priority`, and `Department` (Pydantic + enums).
    - **Backend — LLM handler:** agentic_logic.py — `classify_support_ticket` using `instructor` client and schema enforcement; `classify_support_ticket_with_retries` with retry and validation logic.
    - **Backend — Invalid-output logging:** helpers.py — log_invalid_output appends invalid/uncertain LLM responses to `invalid_outputs.log` for later inspection.
    - **Backend — API:** app.py — FastAPI with `/api/classify` and `/api/heartbeat` endpoints; error handling wired to logging and retry logic.
    - **Backend — Tests:** test_agentic_logic.py, test_app.py — unit tests for classification logic and the API; tests include handling of empty input, invalid payload, and logging behavior.
    - **Frontend — API client:** api.ts — simple wrapper to call the backend endpoint.
    - **Frontend — Input UI:** InputForm.jsx — collects email text from the user.
    - **Frontend — Output UI:** OutputDisplay.jsx — displays `priority`, `department`, and `summary` returned from the API.
    - **Project scaffolding:** `requirements.txt`, package.json, Vite config and initial app structure for local dev.
  - **Tests run:** Run `pytest -v` from backend to exercise the backend tests (see tests for specific test cases). Tests designed to be non-destructive to existing logs (tests read only newly appended entries).
