"""Shared configuration and abstractions for the MidTownBank experiment."""

from .config import (
    REPO_ROOT,
    SRC_ROOT,
    load_env,
    get_llm,
    bank_mcp_stdio_config,
)
from .target import AgentTarget, AgentFactory

__all__ = [
    "REPO_ROOT",
    "SRC_ROOT",
    "load_env",
    "get_llm",
    "bank_mcp_stdio_config",
    "AgentTarget",
    "AgentFactory",
]
