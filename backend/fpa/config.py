"""Env-driven configuration. Materiality knobs are data, not code."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load the repo-root .env once, wherever the process starts from.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

BACKEND_DIR = Path(__file__).resolve().parents[1]
STATE_DIR = BACKEND_DIR / ".fpa_state"
FIXTURES_DIR = BACKEND_DIR / "fixtures"


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "")
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Materiality:
    """Stop rules for the recursive drill. Absolute dollars rank branches —
    a $200M line at +20% outranks a $10M line at +100%."""

    min_share: float = field(default_factory=lambda: _env_float("MATERIALITY_MIN_SHARE", 0.05))
    min_abs_frac: float = field(default_factory=lambda: _env_float("MATERIALITY_MIN_ABS_FRAC", 0.01))
    stop_at_explained: float = field(
        default_factory=lambda: _env_float("MATERIALITY_STOP_AT_EXPLAINED", 0.80)
    )
    max_depth: int = field(default_factory=lambda: int(_env_float("MATERIALITY_MAX_DEPTH", 4)))
    top_n_customers: int = field(
        default_factory=lambda: int(_env_float("MATERIALITY_TOP_N_CUSTOMERS", 3))
    )

    def as_dict(self) -> dict:
        return {
            "min_share": self.min_share,
            "min_abs_frac": self.min_abs_frac,
            "stop_at_explained": self.stop_at_explained,
            "max_depth": self.max_depth,
            "top_n_customers": self.top_n_customers,
        }


SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
