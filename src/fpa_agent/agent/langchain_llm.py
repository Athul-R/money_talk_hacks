"""LangChain LLM helpers (Claude / Anthropic)."""

from __future__ import annotations

import os

from fpa_agent.env import load_env


def get_chat_model(*, temperature: float = 0.0, max_tokens: int = 1800):
    """Return a LangChain ChatAnthropic model using repo `.env` credentials."""
    load_env()
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY (or CLAUDE_API_KEY) required for LangChain agent loop"
        )
    model = (
        os.getenv("FPA_LLM_MODEL")
        or os.getenv("ANTHROPIC_MODEL")
        or "claude-haiku-4-5"
    )
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )
