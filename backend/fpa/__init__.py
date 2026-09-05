"""Explain the Change — FP&A variance engine.

The layout mirrors the hard rule of the product: `engine/` is deterministic
arithmetic that emits evidence objects, `agent/` is the LLM narrator that only
turns evidence into sentences, `memory/` persists what runs learn, `api/`
streams beats to the console, `data/` owns storage.
"""
