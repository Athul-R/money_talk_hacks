"""Provider-agnostic LLM completion. One function, three providers, zero SDKs —
plain HTTPS via httpx so swapping providers is an env-var change. Any failure
returns None and the templated narration ships instead; narration must never
take down a run."""

from __future__ import annotations

from contextvars import ContextVar

import httpx

from ..config import LLM_API_KEY, LLM_MODEL, LLM_PROVIDER
from .. import observe

SESSION_ID: ContextVar[str] = ContextVar("prism_session", default="delta-ledger-demo")

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "gemini": "gemini-2.0-flash",
}

TIMEOUT = 20.0


def available() -> bool:
    return bool(LLM_API_KEY)


def complete(system: str, user: str) -> str | None:
    return observe.timed_complete(
        lambda: _complete(system, user),
        session_id=SESSION_ID.get(),
        user=user,
        kind="narrate",
    )


def _complete(system: str, user: str) -> str | None:
    if not LLM_API_KEY:
        return None
    model = LLM_MODEL or DEFAULT_MODELS.get(LLM_PROVIDER, "gpt-4o-mini")
    try:
        if LLM_PROVIDER == "anthropic":
            r = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": LLM_API_KEY, "anthropic-version": "2023-06-01"},
                json={"model": model, "max_tokens": 700, "system": system,
                      "messages": [{"role": "user", "content": user}]},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            return r.json()["content"][0]["text"].strip()

        if LLM_PROVIDER == "gemini":
            r = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": LLM_API_KEY},
                json={"systemInstruction": {"parts": [{"text": system}]},
                      "contents": [{"parts": [{"text": user}]}]},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

        # default: openai-compatible chat completions
        r = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={"model": model, "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None
