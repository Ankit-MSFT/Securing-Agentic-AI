"""Central config: env loading, LLM factory, and MCP launch settings.

Values are overridable via env vars so agents, attacks, tests, and future
container deployments all pull from the same place.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

SRC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SRC_ROOT.parent

_ENV_LOADED = False


def load_env() -> None:
    """Load the repo-root .env once. Safe to call from any entry point."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    load_dotenv(REPO_ROOT / ".env")
    _ENV_LOADED = True


MODEL_ALIASES = {
    "gpt-5.1": os.getenv("MODEL_GPT", "gpt-5.1"),
    "mistral": os.getenv("MODEL_MISTRAL", "Mistral-Large-3"),
    "deepseek": os.getenv("MODEL_DEEPSEEK", "DeepSeek-V4-Flash"),
}


def get_llm(model_name: str = "gpt-5.1"):
    """Build a ChatOpenAI bound to the configured Azure AI Foundry endpoint."""
    load_env()
    from langchain_openai import ChatOpenAI
    from azure.identity import AzureCliCredential, get_bearer_token_provider

    token_provider = get_bearer_token_provider(
        AzureCliCredential(), "https://ai.azure.com/.default"
    )
    return ChatOpenAI(
        base_url=os.getenv(
            "AZURE_OPENAI_ENDPOINT",
            "https://ankishar-4407-resource.services.ai.azure.com/openai/v1",
        ),
        api_key=token_provider,
        model=MODEL_ALIASES.get(model_name, model_name),
        temperature=0,
    )


def bank_mcp_stdio_config() -> dict:
    """Return the stdio launch config for the bank MCP server.

    The location can be overridden via MIDTOWN_MCP_COMMAND / MIDTOWN_MCP_ARGS
    (JSON list) so container deployments can point elsewhere.
    """
    load_env()
    command = os.getenv("MIDTOWN_MCP_COMMAND", sys.executable)
    args_env = os.getenv("MIDTOWN_MCP_ARGS")
    if args_env:
        import json
        args = json.loads(args_env)
    else:
        args = ["-m", "bank.mcp_server"]
    return {"command": command, "args": args, "transport": "stdio"}
