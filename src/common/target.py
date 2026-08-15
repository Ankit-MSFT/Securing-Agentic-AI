"""Target abstraction so attacks talk to agent variants uniformly."""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable


@runtime_checkable
class AgentTarget(Protocol):
    """An agent target that can be driven by the attack harness."""

    async def ainvoke(self, messages: list) -> dict: ...


AgentFactory = Callable[[str], AgentTarget]
"""A callable that takes a model name and returns a ready-to-use agent."""
