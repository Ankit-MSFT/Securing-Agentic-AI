"""Hardened agent factory using an authenticated HTTP MCP connection."""

from __future__ import annotations

import os

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from common import get_llm, load_env

SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "system_prompt.txt")


def bank_mcp_http_config(access_token: str) -> dict:
    load_env()
    return {
        "url": os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp"),
        "transport": "streamable_http",
        "headers": {"Authorization": f"Bearer {access_token}"},
    }


async def build_agent(access_token: str, model_name: str = "gpt-5.1"):
    """Build an agent whose MCP calls carry the employee's access token."""
    client = MultiServerMCPClient(
        {"midtownbank": bank_mcp_http_config(access_token)}
    )
    tools = await client.get_tools()
    with open(SYSTEM_PROMPT_PATH, encoding="utf-8") as prompt_file:
        system_prompt = prompt_file.read()
    return create_react_agent(get_llm(model_name), tools, prompt=system_prompt)