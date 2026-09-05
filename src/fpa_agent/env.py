"""Load repo-local .env (preferred over shell / zshrc for secrets)."""

from __future__ import annotations

from pathlib import Path

_LOADED = False


def repo_root() -> Path:
    """Return the hackathon repo root (directory containing pyproject.toml or .env)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() or (parent / ".env").exists():
            return parent
        if (parent / "data" / "given").exists() and (parent / "src").exists():
            return parent
    # src/fpa_agent/env.py → parents[2] is repo root in the standard layout
    return here.parents[2]


def load_env(*, override: bool = False) -> Path | None:
    """Load `.env` from the hackathon repo root.

    `override=False` means existing shell exports win (zshrc still works if set).
    """
    global _LOADED
    if _LOADED:
        return None

    try:
        from dotenv import load_dotenv
    except ImportError:
        return None

    env_path = repo_root() / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=override)
        _LOADED = True
        return env_path

    _LOADED = True
    return None
