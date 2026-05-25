from __future__ import annotations

import json
import time
from typing import Any, Dict, Generator, Optional

from dotenv import load_dotenv
import openai

from modules.tools.engine import ToolEngine
from modules.utils.helpers import extract_json
from modules.utils.interactions import record_event
from modules.utils.tokenizer import count_tokens
from modules.memory.summarizer import summarize_messages
from modules.memory.integration import DurableMemoryManager

from modules.logic.agentic_logic import _delta_text_from_event, _event_type

load_dotenv()
openai.api_key = None
try:
    import os

    openai.api_key = os.getenv("OPENAI_API_KEY")
except Exception:
    pass


class _SQLiteWritebackAdapter:
    def __init__(self, state_store, user_id: int):
        self.state_store = state_store
        self.user_id = user_id

    def apply_patches(self, patches):
        return self.state_store.apply_patches(user_id=self.user_id, patches=patches)


def _compact_memories_if_needed(state_store, user_id: int) -> None:
    """Simple compaction: if total memory tokens exceed budget, summarize and merge oldest memories."""
    try:
        mems = state_store.list_memories(user_id=user_id)
        if not mems:
            return
        total = sum(int(m.token_count or 0) for m in mems)
        budget = getattr(state_store, "token_budget", 4000)
        if total <= budget:
            return

        # remove oldest memories until under budget and create a summary of removed
        # sort by created_at ascending (oldest first)
        sorted_m = sorted(mems, key=lambda m: m.created_at)
        removed = []
        removed_tokens = 0
        target_remove = total - budget
        for m in sorted_m:
            if removed_tokens >= target_remove:
                break
            removed.append(m)
            removed_tokens += int(m.token_count or 0)

        # build summarization input (SimpleNamespace compatible)
        from types import SimpleNamespace

        to_summarize = []
        for m in removed:
            msg = SimpleNamespace()
            msg.message = SimpleNamespace()
            msg.message.role = m.type
            # stringify content for summarization
            msg.message.content = json.dumps(m.content, ensure_ascii=False)
            msg.token_count = int(m.token_count or 0)
            to_summarize.append(msg)

        summary_text, summary_tokens = summarize_messages(to_summarize)

        # delete removed memories and insert summary memory
        for m in removed:
            try:
                state_store.delete_memory(user_id=user_id, memory_id=m.id)
            except Exception:
                pass

        # add summary as new memory
        state_store.add_memory(
            user_id=user_id,
            mtype="summary",
            content={"summary": summary_text, "merged_ids": [m.id for m in removed]},
            importance=0.7,
            tags=["summary"],
            token_count=max(1, int(summary_tokens)),
        )
        try:
            record_event("memory_compacted", {"user_id": user_id, "removed_tokens": removed_tokens, "summary_tokens": summary_tokens, "removed_count": len(removed)})
        except Exception:
            pass
    except Exception:
        # compaction best-effort
        pass


def run_react_session(
    prompt_text: str,
    user_id: Optional[int],
    request_meta: Optional[dict],
    tool_engine: ToolEngine,
    state_store,
    auth_manager,
    max_steps: int = 6,
) -> Generator[Dict[str, Any], None, None]:
    """
    Run a ReAct-style reasoning loop driven by the LLM.

    Yields structured events (as dict) suitable for SSE streaming to clients. Event types:
      - reasoning: {'step', 'delta'} streaming thought text
      - tool_call: {'step','tool','args'} when the agent requests a tool
      - observation: {'step','tool','result'} after tool executes
      - final: {'final_answer'} when loop terminates with a final answer
      - error: {'message'} for unrecoverable errors or max-steps reached

    The function relies on `tool_engine.invoke()` to validate and run tools.
    DB-mutating tool functions should implement transactional semantics; this loop treats tool invoke results as authoritative.
    """

    system_prompt = (
        "You are an agent that may call tools to accomplish a user's request.\n"
        "On each turn output EXACTLY one top-level JSON object and nothing else.\n"
        "Allowed keys: 'thought' (string), 'tool_call' (object with 'name' and 'args'), and 'final_answer' (object).\n"
        "If you emit 'tool_call', use the tool name from the provided manifest list and provide typed 'args' matching the manifest.\n"
        "If you emit 'final_answer', the agent will stop and return that to the user.\n"
        "Do not include plain text outside the JSON object."
    )

    history: list[str] = []

    # durable memory manager for parsing/applying PATCHES into SQLite
    durable_mgr = DurableMemoryManager(store=_SQLiteWritebackAdapter(state_store, user_id))

    for step in range(max_steps):
        # Build a concise user message that includes previous observations for context
        composed = prompt_text + "\n\nHistory:\n" + ("\n".join(history[-10:]) if history else "")

        start = time.time()
        content_parts: list[str] = []

        try:
            stream = openai.responses.create(
                model="gpt-4o-mini",
                input=[{"role": "system", "content": system_prompt}, {"role": "user", "content": composed}],
                stream=True,
            )
        except Exception as e:
            record_event("agent_error", {"step": step, "error": str(e)})
            yield {"type": "error", "data": {"message": f"LLM invocation failed: {e}"}}
            return

        # stream partial reasoning to client
        try:
            for i, ev in enumerate(stream):
                delta = _delta_text_from_event(ev)
                if delta:
                    content_parts.append(delta)
                    yield {"type": "reasoning", "data": {"step": step, "delta": delta}}
        except Exception as e:
            # best-effort; yield error and exit
            record_event("agent_error", {"step": step, "error": str(e)})
            yield {"type": "error", "data": {"message": f"Streaming error: {e}"}}
            return

        raw = "".join(content_parts).strip()
        elapsed = time.time() - start
        record_event("agent_thought", {"step": step, "text": (raw[:500]), "duration": elapsed, "user_id": user_id or "unknown"})

        # Persist thought to durable DB memory (if available)
        try:
            if state_store is not None and user_id is not None:
                token_est = max(1, int(count_tokens(raw or "", model="gpt-4o-mini")))
                state_store.add_memory(
                    user_id=user_id,
                    mtype="agent_trace",
                    content={"step": step, "text": raw},
                    importance=0.5,
                    tags=["agent_trace"],
                    token_count=token_est,
                )
                # compact memories if over budget
                try:
                    _compact_memories_if_needed(state_store, user_id)
                except Exception:
                    pass
        except Exception:
            pass

        if not raw:
            history.append("<empty response from LLM>")
            continue

        # Parse JSON payload
        parsed = None
        try:
            parsed = json.loads(raw)
        except Exception:
            maybe = extract_json(raw)
            if maybe:
                try:
                    parsed = json.loads(maybe)
                except Exception:
                    parsed = None

        if parsed is None:
            # ask LLM to reformulate on next turn by adding a history note
            history.append("Assistant produced non-JSON output; please respond with only a JSON object on the next turn.")
            yield {"type": "observation", "data": {"step": step, "note": "invalid_json", "raw": raw}}
            continue

        # If the model emitted structured PATCHES in-text, attempt to apply them
        try:
            if "PATCHES:" in raw or (isinstance(parsed, dict) and "patches" in parsed):
                try:
                    wb_res = durable_mgr.apply_llm_writeback(raw)
                    record_event("agent_writeback_applied", {"step": step, "result": wb_res, "user_id": user_id or "unknown"})
                    yield {"type": "observation", "data": {"step": step, "writeback": wb_res}}
                    history.append(f"Writeback applied: {wb_res}")
                except Exception as e:
                    record_event("agent_writeback_error", {"step": step, "error": str(e), "user_id": user_id or "unknown"})
                    yield {"type": "observation", "data": {"step": step, "writeback_error": str(e)}}
        except Exception:
            pass

        # If final_answer present, finish
        if "final_answer" in parsed:
            final = parsed.get("final_answer")
            record_event("agent_final", {"step": step, "final": final, "user_id": user_id or "unknown"})
            # persist final answer as durable memory + include trace
            try:
                if state_store is not None and user_id is not None:
                    trace_text = "\n".join(history[-50:])
                    final_text = json.dumps(final) if not isinstance(final, str) else final
                    # add final answer as memory
                    state_store.add_memory(
                        user_id=user_id,
                        mtype="agent_final_answer",
                        content={"final": final, "trace": trace_text},
                        importance=0.9,
                        tags=["agent_final"],
                        token_count=max(1, int(count_tokens(final_text, model="gpt-4o-mini"))),
                    )
                    try:
                        _compact_memories_if_needed(state_store, user_id)
                    except Exception:
                        pass
            except Exception:
                pass
            yield {"type": "final", "data": final}
            return

        # If tool_call present, validate and invoke
        tc = parsed.get("tool_call")
        if tc:
            tool_name = tc.get("name")
            args = tc.get("args") or {}
            yield {"type": "tool_call", "data": {"step": step, "tool": tool_name, "args": args}}
            record_event("agent_tool_request", {"step": step, "tool": tool_name, "args": args, "user_id": user_id or "unknown"})

            # create a short-lived access token for the caller so ToolEngine's token enforcement works
            caller_token = None
            try:
                user = state_store.get_user_by_id(user_id) if user_id is not None else None
                if user:
                    caller_token = auth_manager.create_access_token(user_id=user_id, username=user.get("username"))
            except Exception:
                caller_token = None

            # invoke via tool engine
            try:
                result = tool_engine.invoke(tool_name, args, caller=caller_token)
            except Exception as e:
                record_event("agent_tool_error", {"step": step, "tool": tool_name, "error": str(e), "user_id": user_id or "unknown"})
                yield {"type": "observation", "data": {"step": step, "tool": tool_name, "error": str(e)}}
                history.append(f"Tool {tool_name} raised an exception: {e}")
                continue

            # result contains success flag and result or error
            if not result.get("success"):
                # if retryable, include details to allow LLM to reformulate
                history.append(f"Tool {tool_name} failed: {result.get('error')} - details: {result.get('details')}")
                record_event("agent_tool_fail", {"step": step, "tool": tool_name, "result": result, "user_id": user_id or "unknown"})
                yield {"type": "observation", "data": {"step": step, "tool": tool_name, "result": result}}
                # persist failure observation
                try:
                    if state_store is not None and user_id is not None:
                        text = f"tool {tool_name} failed: {result.get('error')}"
                        state_store.add_memory(
                            user_id=user_id,
                            mtype="agent_observation",
                            content={"step": step, "tool": tool_name, "result": result},
                            importance=0.6,
                            tags=["agent_observation"],
                            token_count=max(1, int(count_tokens(text, model="gpt-4o-mini"))),
                        )
                        try:
                            _compact_memories_if_needed(state_store, user_id)
                        except Exception:
                            pass
                except Exception:
                    pass
                continue

            # success
            observation = result.get("result")
            record_event("agent_tool_success", {"step": step, "tool": tool_name, "observation": str(observation), "user_id": user_id or "unknown"})
            yield {"type": "observation", "data": {"step": step, "tool": tool_name, "result": observation}}
            history.append(f"Observation from {tool_name}: {json.dumps(observation) if observation is not None else 'null'}")
            # persist observation
            try:
                if state_store is not None and user_id is not None:
                    txt = json.dumps(observation) if observation is not None else ""
                    state_store.add_memory(
                        user_id=user_id,
                        mtype="agent_observation",
                        content={"step": step, "tool": tool_name, "result": observation},
                        importance=0.7,
                        tags=["agent_observation"],
                        token_count=max(1, int(count_tokens(txt, model="gpt-4o-mini"))),
                    )
                    try:
                        _compact_memories_if_needed(state_store, user_id)
                    except Exception:
                        pass
            except Exception:
                pass
            continue

        # No tool_call or final_answer: add assistant thought to history and continue
        thought = parsed.get("thought") if isinstance(parsed, dict) else None
        history.append(f"Assistant: {thought if thought else str(parsed)[:200]}")

    # max steps reached
    record_event("agent_max_steps", {"attempted": max_steps, "user_id": user_id or "unknown"})
    yield {"type": "error", "data": {"message": "Max iterations reached without final answer"}}
