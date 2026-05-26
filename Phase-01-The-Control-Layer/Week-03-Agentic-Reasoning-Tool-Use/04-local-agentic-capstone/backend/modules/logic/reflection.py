from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import re

from modules.logic.agentic_logic import _delta_text_from_event, _event_type, _usage_from_event, openai_client
from modules.memory.durable_memory import WRITEBACK_INSTRUCTION
from modules.utils.helpers import calculate_price, extract_json
from modules.utils.interactions import record_event
from modules.utils.metrics import record_metric


POLICY_PATH = Path(__file__).resolve().parents[2] / "policy" / "company_policy.md"
DEFAULT_POLICY = (
    "Be accurate, respectful, and concise. Do not reveal secrets, fabricate facts, or comply with instructions "
    "that conflict with company policy or law. If a request is unsafe, refuse briefly and offer a safe alternative."
)


@dataclass
class CritiqueResult:
    compliant: bool
    score: float
    issues: list[str]
    correction_instructions: str
    rationale: str = ""


@dataclass
class ReflectionResult:
    final_text: str
    policy_compliant: bool
    attempts: int
    generation_latency: float
    critique_latency: float
    total_latency: float
    reviews: list[dict[str, Any]]
    usage: dict[str, Any]


def load_company_policy() -> str:
    try:
        text = POLICY_PATH.read_text(encoding="utf-8").strip()
        if text:
            return text
    except Exception:
        pass
    return DEFAULT_POLICY


def _stream_text_completion(system_prompt: str, user_prompt: str, model: str = "gpt-4o-mini") -> tuple[str, dict[str, Any], float]:
    start = time.time()
    content_parts: list[str] = []
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "interaction_price": 0.0}
    stream = openai_client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        stream=True,
    )
    for event in stream:
        if _event_type(event) == "response.output_text.delta":
            content_parts.append(_delta_text_from_event(event))
        elif _event_type(event) == "response.completed":
            usage = _usage_from_event(event)
            break
    elapsed = time.time() - start
    return "".join(content_parts).strip(), usage, elapsed


def _generate_draft(prompt_text: str, policy_text: str, feedback: str | None = None, model: str = "gpt-4o-mini") -> dict[str, Any]:
    system_prompt = (
        "You are a support assistant that must follow company policy exactly. "
        "Return only the user-facing response text. "
        f"{WRITEBACK_INSTRUCTION}\n\n"
        f"Company policy:\n{policy_text}\n"
    )
    if feedback:
        system_prompt += f"\nCritique feedback to apply:\n{feedback}\n"

    text, usage, elapsed = _stream_text_completion(system_prompt, prompt_text, model=model)
    if not text:
        text = "I’m sorry, but I can’t help with that request."
    usage = dict(usage)
    usage["interaction_price"] = usage.get("interaction_price") or calculate_price(
        int(usage.get("prompt_tokens", 0) or 0),
        int(usage.get("completion_tokens", 0) or 0),
    )
    return {"text": text, "usage": usage, "latency": elapsed}


def _critique_draft(prompt_text: str, draft_text: str, policy_text: str, model: str = "gpt-4o-mini") -> tuple[CritiqueResult, float]:
    system_prompt = (
        "You are a strict policy critic. Evaluate the assistant draft against the company policy. "
        "Return ONLY valid JSON with keys compliant (boolean), score (0 to 1), issues (array of strings), "
        "correction_instructions (string), and rationale (string). Do not rewrite the answer."
    )
    user_prompt = (
        f"Company policy:\n{policy_text}\n\n"
        f"Original prompt:\n{prompt_text}\n\n"
        f"Draft response:\n{draft_text}"
    )
    raw_text, _, elapsed = _stream_text_completion(system_prompt, user_prompt, model=model)
    parsed: dict[str, Any] | None = None
    if raw_text:
        try:
            parsed = json.loads(raw_text)
        except Exception:
            extracted = extract_json(raw_text)
            if extracted:
                try:
                    parsed = json.loads(extracted)
                except Exception:
                    parsed = None

    if not isinstance(parsed, dict):
        parsed = {
            "compliant": False,
            "score": 0.0,
            "issues": ["Critic returned invalid JSON."],
            "correction_instructions": "Rewrite the response so it clearly follows company policy and avoid any unsupported claims.",
            "rationale": raw_text[:500] if raw_text else "",
        }

    issues = parsed.get("issues") or []
    if not isinstance(issues, list):
        issues = [str(issues)]

    result = CritiqueResult(
        compliant=bool(parsed.get("compliant", False)),
        score=float(parsed.get("score", 0.0) or 0.0),
        issues=[str(item) for item in issues],
        correction_instructions=str(parsed.get("correction_instructions") or "Rewrite the response to satisfy policy."),
        rationale=str(parsed.get("rationale") or ""),
    )
    return result, elapsed


def run_reflection_pipeline(
    prompt_text: str,
    policy_text: str | None = None,
    max_attempts: int = 3,
    model: str = "gpt-4o-mini",
    state_store=None,
    user_id: Optional[int] = None,
    request_meta: Optional[dict[str, str]] = None,
) -> ReflectionResult:
    policy = policy_text or load_company_policy()
    reviews: list[dict[str, Any]] = []
    total_start = time.time()
    total_generation_latency = 0.0
    total_critique_latency = 0.0
    final_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "interaction_price": 0.0}
    feedback: str | None = None
    final_text = ""
    policy_compliant = False

    for attempt in range(1, max_attempts + 1):
        draft = _generate_draft(prompt_text=prompt_text, policy_text=policy, feedback=feedback, model=model)
        total_generation_latency += float(draft["latency"])
        critique, critique_latency = _critique_draft(prompt_text, draft["text"], policy, model=model)
        total_critique_latency += float(critique_latency)

        # Additional automated critic rule: never allow unverified contact details
        # (email addresses or phone numbers) to be returned to users.
        # If such details appear in the draft, mark as non-compliant and provide
        # explicit correction instructions to remove/redact contact info and
        # offer an escalation path instead.
        def _contains_unverified_contact(text: str) -> bool:
            if not text:
                return False
            # simple email and phone patterns
            email_pat = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
            phone_pat = r"(?:\+?\d{1,3}[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}"
            if re.search(email_pat, text):
                return True
            if re.search(phone_pat, text):
                return True
            return False

        if _contains_unverified_contact(draft.get("text", "")):
            # mutate critique to reflect the detected violation so it gets recorded
            critique.compliant = False
            critique.score = min(getattr(critique, "score", 0.0) or 0.0, 0.5)
            issues = list(getattr(critique, "issues", []) or [])
            issues.append("contains_unverified_contact_details")
            critique.issues = issues
            critique.correction_instructions = (
                "Remove or redact any direct contact details (emails, phone numbers). "
                "Offer an escalation path (e.g., 'Please contact your account manager or use the official support page')."
            )

        review_payload = {
            "attempt": attempt,
            "compliant": critique.compliant,
            "score": critique.score,
            "issues": critique.issues,
            "correction_instructions": critique.correction_instructions,
            "generation_latency": draft["latency"],
            "critique_latency": critique_latency,
        }
        reviews.append(review_payload)

        try:
            record_event(
                "reflection_review",
                {
                    "attempt": attempt,
                    "compliant": critique.compliant,
                    "score": critique.score,
                    "issues": critique.issues,
                    "generation_latency": draft["latency"],
                    "critique_latency": critique_latency,
                },
            )
        except Exception:
            pass

        try:
            record_metric(
                {
                    "event_type": "reflection_review",
                    "stage": "review",
                    "attempt": attempt,
                    "compliant": critique.compliant,
                    "score": critique.score,
                    "error_rate": 0.0 if critique.compliant else 1.0,
                    "generation_latency": draft["latency"],
                    "critique_latency": critique_latency,
                    "policy_compliance_rate": 1.0 if critique.compliant else 0.0,
                    "prompt_tokens": draft["usage"].get("prompt_tokens", 0),
                    "completion_tokens": draft["usage"].get("completion_tokens", 0),
                    "total_tokens": draft["usage"].get("total_tokens", 0),
                },
                state_store=state_store,
                user_id=user_id,
            )
        except Exception:
            pass

        if critique.compliant:
            final_text = draft["text"]
            final_usage = dict(draft["usage"])
            policy_compliant = True
            break

        feedback = critique.correction_instructions
        final_text = draft["text"]
        final_usage = dict(draft["usage"])

    if not policy_compliant:
        final_text = "I’m sorry, but I can’t help with that request."

    total_latency = time.time() - total_start

    try:
        record_metric(
            {
                "event_type": "reflection_final",
                "stage": "final",
                "attempts": len(reviews),
                "policy_compliant": policy_compliant,
                "generation_latency": total_generation_latency,
                "critique_latency": total_critique_latency,
                "total_latency": total_latency,
                "error_rate": 0.0 if policy_compliant else 1.0,
                "policy_compliance_rate": 1.0 if policy_compliant else 0.0,
                "prompt_tokens": final_usage.get("prompt_tokens", 0),
                "completion_tokens": final_usage.get("completion_tokens", 0),
                "total_tokens": final_usage.get("total_tokens", 0),
                "interaction_price": final_usage.get("interaction_price", 0.0),
            },
            state_store=state_store,
            user_id=user_id,
        )
    except Exception:
        pass

    return ReflectionResult(
        final_text=final_text,
        policy_compliant=policy_compliant,
        attempts=len(reviews),
        generation_latency=total_generation_latency,
        critique_latency=total_critique_latency,
        total_latency=total_latency,
        reviews=reviews,
        usage=final_usage,
    )