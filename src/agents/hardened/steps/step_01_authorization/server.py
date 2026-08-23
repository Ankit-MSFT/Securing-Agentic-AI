"""Entra-protected HTTP MCP server for authorization hardening step 1."""

from __future__ import annotations

import os
import json
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

from agents.hardened.steps.step_01_authorization.audit import (
    write_authorization_event,
)
from agents.hardened.steps.step_01_authorization.auth import (
    CREDIT_COMMITTEE_ROLE,
    AuthorizationError,
    EntraPrincipal,
    EntraTokenVerifier,
    require_role,
)
from bank.mcp_server import handle_call_tool
from bank.mcp_server import conn as bank_connection
from bank.database import get_loan as get_loan_record
from common import load_env


def _required_setting(name: str, alias: str | None = None) -> str:
    load_env()
    value = os.getenv(name) or (os.getenv(alias) if alias else None)
    if not value:
        raise RuntimeError(f"Required environment variable is not set: {name}")
    return value


def create_server() -> FastMCP:
    tenant_id = _required_setting("ENTRA_TENANT_ID")
    api_client_id = _required_setting(
        "ENTRA_MCP_API_CLIENT_ID", "MCP_API_CLIENT_ID"
    )
    resource_server_url = os.getenv(
        "MCP_SERVER_URL", "http://localhost:8000/mcp"
    )
    issuer_url = f"https://login.microsoftonline.com/{tenant_id}/v2.0"
    required_scope = "access_as_user"

    server = FastMCP(
        "MidtownBank Hardened MCP",
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("MCP_PORT", "8000")),
        stateless_http=True,
        token_verifier=EntraTokenVerifier(tenant_id, api_client_id),
        auth=AuthSettings(
            issuer_url=issuer_url,
            resource_server_url=resource_server_url,
            required_scopes=[required_scope],
        ),
    )

    async def call_baseline(name: str, arguments: dict[str, Any]) -> str:
        result = await handle_call_tool(name, arguments)
        return result[0].text

    @server.tool()
    async def get_customer(customer_id: int) -> str:
        """Get a bank customer by ID."""
        return await call_baseline("get_customer", {"customer_id": customer_id})

    @server.tool()
    async def list_customers() -> str:
        """List all bank customers."""
        return await call_baseline("list_customers", {})

    @server.tool()
    async def get_account(account_id: int) -> str:
        """Get a bank account by ID."""
        return await call_baseline("get_account", {"account_id": account_id})

    @server.tool()
    async def list_customer_accounts(customer_id: int) -> str:
        """List all accounts belonging to a customer."""
        return await call_baseline(
            "get_customer_accounts", {"customer_id": str(customer_id)}
        )

    @server.tool()
    async def get_loan(loan_id: str) -> str:
        """Get a loan by ID."""
        loan = get_loan_record(bank_connection, loan_id)
        if not loan:
            return json.dumps({"error": "Loan application not found"})
        return json.dumps(loan.model_dump(), default=str)

    @server.tool()
    async def get_pending_loans() -> str:
        """List loan applications awaiting a decision."""
        return await call_baseline("get_pending_loans", {})

    @server.tool()
    async def list_transactions(account_id: int, limit: int = 20) -> str:
        """List recent transactions for an account."""
        return await call_baseline(
            "list_transactions", {"account_id": account_id, "limit": limit}
        )

    @server.tool()
    async def write_off_loan(loan_id: str, reason: str) -> str:
        """Write off an outstanding loan when the caller is authorized."""
        access_token = get_access_token()
        if access_token is None:
            raise PermissionError("AUTHENTICATION_REQUIRED")

        principal = EntraPrincipal.from_access_token(access_token)
        correlation_id = str((access_token.claims or {}).get("jti", ""))
        try:
            require_role(principal, CREDIT_COMMITTEE_ROLE)
        except AuthorizationError:
            write_authorization_event(
                principal,
                tool="write_off_loan",
                resource=f"loan:{loan_id}",
                decision="denied",
                correlation_id=correlation_id,
            )
            raise AuthorizationError(
                "403 FORBIDDEN: INSUFFICIENT_PRIVILEGES"
            ) from None

        write_authorization_event(
            principal,
            tool="write_off_loan",
            resource=f"loan:{loan_id}",
            decision="allowed",
            correlation_id=correlation_id,
        )
        return await call_baseline(
            "write_off_loan", {"application_id": loan_id, "reason": reason}
        )

    return server


def main() -> None:
    create_server().run(transport="streamable-http")


if __name__ == "__main__":
    main()