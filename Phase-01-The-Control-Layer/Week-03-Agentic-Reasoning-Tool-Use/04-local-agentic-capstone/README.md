# Part 4 Local Agentic Capstone

## Daily Progress

- **Date:** 2026-05-19
  - **Summary:** Converted internal model streaming to client-facing SSE (Server-Sent Events) streaming, built complete frontend UI with real-time response display and metadata visualization, and updated all tests to support generator-based architecture. MVP now fully functional end-to-end with streaming responses visible to users.
  - **Completed:**
    - **Backend — Generator-based streaming:** Modified `SLModel.infer_response()` and `FrontierModel.infer_response()` to yield events instead of buffering. Each model now yields: `delta` events (text chunks), `done` event (text complete), and `completed` event (full response object with metadata). Preserves existing logic—no duplication.
    - **Backend — Service streaming:** Updated `SupportAIService.handle_ticket()` to use `yield from`, passing events directly from selected model to caller.
    - **Backend — SSE endpoint:** Modified `/api/handle` in app.py to return `StreamingResponse` with SSE format (`data: {json}\n\n`). Includes error handling that gracefully yields error events if exceptions occur during streaming.
    - **Backend — Exception handling:** Moved error handling inside the event generator to catch streaming errors and yield them as error events rather than crashing the stream.
    - **Frontend — SSE client:** Implemented `streamHandleEmail()` in api.ts that parses raw SSE stream, extracts JSON events, and calls callbacks for delta/done/completed/error events.
    - **Frontend — Input component:** Built `InputForm.tsx` with textarea input, submit button, and loading state management.
    - **Frontend — Output component:** Built `OutputDisplay.tsx` with: (1) streaming text display with blinking cursor, (2) intent badge (simple/complex), (3) metadata grid showing duration, token counts, and interaction price.
    - **Frontend — Main component:** Updated `App.tsx` to orchestrate InputForm → stream submission → real-time text display → metadata display flow.
    - **Frontend — Styling:** Created component styles (styles.css) and app styling (App.css) with gradient background, responsive grid layout, and visual feedback (loading states, cursor animation).
    - **Backend — Test updates:** Updated all model tests to collect generator events and verify sequence (delta → done → completed). Updated app endpoint test to parse SSE format and validate event structure. Updated edge case test to expect error events instead of HTTP 500.
    - **Verification:** All 25 backend tests passing. Frontend tested in browser and shows real-time streaming, correct intent classification, and complete metadata display.
  - **Architecture decisions:**
    - Models yield events directly (no new methods added)—reuses existing streaming logic without duplication.
    - Error handling inside generator allows graceful error communication via SSE stream.
    - Frontend parses SSE by buffering incomplete events and splitting on `\n\n` boundaries.
    - Metadata (usage, pricing) included in final `completed` event for immediate client display.
  - **MVP Status:** ✅ **COMPLETE** — Backend streams responses via SSE, frontend displays text in real-time, metadata shown on completion. Ready for demonstration.

- **Date:** 2026-05-18
  - **Summary:** Refactored backend to use OpenAI Responses API for streaming, implemented proper token usage extraction, restructured tests with correct mock boundaries (unit vs. integration), and verified end-to-end functionality with live API testing.
  - **Completed:**
    - **Backend — LLM streaming:** agentic_logic.py — replaced `chat.completions.create` with `responses.create` for structured event-based streaming. Implemented proper event loop to handle `response.output_text.delta`, `response.output_text.done`, and `response.completed` events.
    - **Backend — Token usage:** Switched to Responses API field names (`input_tokens`, `output_tokens`, `total_tokens`) and implemented `_usage_from_event` to extract usage from final completion event. Verified token counts now correctly reported in Metadata.
    - **Backend — Event parsing:** Added `_event_type`, `_delta_text_from_event`, and `_usage_from_event` helpers to handle Responses API event shapes (both dict and object attribute access for SDK compatibility).
    - **Tests — Unit test strategy:** Updated test_agentic_logic.py with proper mock boundaries: mock only the OpenAI stream, not the classifier logic itself. Implemented `make_response_event` factory to generate realistic Responses API event fixtures matching actual SDK event sequence.
    - **Tests — Integration test:** Created test_integration_agentic_logic.py with opt-in live OpenAI testing (runs only when `RUN_OPENAI_INTEGRATION_TESTS=1` env var is set). Allows verification of real-world flow without breaking deterministic unit tests.
    - **Tests — App endpoint tests:** Updated test_app.py to patch `app_module.classify_support_ticket_with_retries` (the bound function) rather than the logic module, ensuring proper import-time binding.
    - **Manual testing:** Verified with Postman that `/api/classify` correctly returns `{ticket, metadata}` with real token counts (e.g., input_tokens=57, output_tokens=44, total_tokens=101) and all classification fields populated.
  - **Tests run:** All 10 tests pass (`pytest -vv`): 5 unit tests for agentic_logic (stream parsing, retries, empty input, invalid output logging), 4 endpoint tests for app (heartbeat, success, empty email, invalid payload), 1 integration test.
  - **Architecture notes:** Responses API streaming provides typed events and cleaner lifecycle management than chat.completions deltas. Usage is now reliably extracted from the completion event rather than defaulting to zeros. Unit tests use deterministic fake streams; integration test runs against real OpenAI API.

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
