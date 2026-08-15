"""Baseline (intentionally vulnerable) MidTown Assistant."""

from .factory import build_agent, SYSTEM_PROMPT_PATH, read_system_prompt

__all__ = ["build_agent", "SYSTEM_PROMPT_PATH", "read_system_prompt"]
