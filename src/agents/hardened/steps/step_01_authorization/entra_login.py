"""Microsoft Entra authorization-code login helpers for Streamlit."""

from __future__ import annotations

import os
import threading
import time

import msal

from common import load_env

_AUTH_FLOW_TTL_SECONDS = 600
_pending_flows: dict[str, tuple[float, dict]] = {}
_pending_flows_lock = threading.Lock()


def _required_setting(name: str) -> str:
    load_env()
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable is not set: {name}")
    return value


def create_client() -> msal.ConfidentialClientApplication:
    tenant_id = _required_setting("ENTRA_TENANT_ID")
    return msal.ConfidentialClientApplication(
        _required_setting("ENTRA_AGENT_CLIENT_ID"),
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=_required_setting("ENTRA_AGENT_CLIENT_SECRET"),
    )


def delegated_scope() -> str:
    load_env()
    configured_scope = os.getenv("ENTRA_MCP_SCOPE")
    if configured_scope:
        return configured_scope
    api_client_id = os.getenv("ENTRA_MCP_API_CLIENT_ID") or _required_setting(
        "MCP_API_CLIENT_ID"
    )
    return f"api://{api_client_id}/access_as_user"


def redirect_uri() -> str:
    load_env()
    return os.getenv("ENTRA_REDIRECT_URI", "http://localhost:8501")


def begin_login() -> dict:
    flow = create_client().initiate_auth_code_flow(
        scopes=[delegated_scope()], redirect_uri=redirect_uri()
    )
    with _pending_flows_lock:
        _pending_flows[flow["state"]] = (time.monotonic(), flow)
    return flow


def take_pending_flow(state: str) -> dict | None:
    """Consume a pending PKCE flow from any Streamlit browser session."""
    now = time.monotonic()
    with _pending_flows_lock:
        expired_states = [
            key
            for key, (created_at, _) in _pending_flows.items()
            if now - created_at > _AUTH_FLOW_TTL_SECONDS
        ]
        for key in expired_states:
            _pending_flows.pop(key, None)

        pending = _pending_flows.pop(state, None)
    return pending[1] if pending else None


def complete_login(flow: dict, query_parameters: dict[str, str]) -> dict:
    return create_client().acquire_token_by_auth_code_flow(
        flow, query_parameters, scopes=[delegated_scope()]
    )