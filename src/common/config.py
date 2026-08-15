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


MODEL_ALIAS_ENV = {
    "gpt-5.1": ("MODEL_GPT", "gpt-5.1"),
    "mistral": ("MODEL_MISTRAL", "Mistral-Large-3"),
    "deepseek": ("MODEL_DEEPSEEK", "DeepSeek-V4-Flash"),
}


def _resolve_model(model_name: str) -> str:
    env_var, default = MODEL_ALIAS_ENV.get(model_name, (None, model_name))
    return os.getenv(env_var, default) if env_var else model_name


def get_llm(model_name: str = "gpt-5.1"):
    """Build a ChatOpenAI bound to the configured Azure AI Foundry endpoint."""
    load_env()
    from langchain_openai import ChatOpenAI
    from azure.identity import AzureCliCredential, get_bearer_token_provider

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "AZURE_OPENAI_ENDPOINT is not set. Add it to the repo-root .env."
        )

    token_provider = get_bearer_token_provider(
        AzureCliCredential(), "https://ai.azure.com/.default"
    )
    return ChatOpenAI(
        base_url=endpoint,
        api_key=token_provider,
        model=_resolve_model(model_name),
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
