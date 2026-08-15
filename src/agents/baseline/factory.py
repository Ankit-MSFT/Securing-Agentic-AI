"""Baseline agent factory. Attacks and UIs consume this, not raw internals."""

from __future__ import annotations

from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from common import bank_mcp_stdio_config, get_llm

SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.txt"


def read_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


async def build_agent(model_name: str = "gpt-5.1"):
    """Instantiate the baseline agent wired to the bank MCP server."""
    client = MultiServerMCPClient({"midtownbank": bank_mcp_stdio_config()})
    tools = await client.get_tools()
    llm = get_llm(model_name)
    return create_react_agent(llm, tools, prompt=read_system_prompt())
