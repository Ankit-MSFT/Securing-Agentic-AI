"""Focused tests for the Step 1 authorization boundary."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from mcp.server.auth.provider import AccessToken
from mcp.server.fastmcp.exceptions import ToolError

from agents.hardened.steps.step_01_authorization.auth import (
    AuthorizationError,
    CREDIT_COMMITTEE_ROLE,
    EntraPrincipal,
    require_role,
)


def _principal(*roles: str) -> EntraPrincipal:
    return EntraPrincipal.from_access_token(_token(*roles))


def _token(*roles: str) -> AccessToken:
    return AccessToken(
        token="test-token",
        client_id="agent-client-id",
        scopes=["access_as_user"],
        subject="synthetic-user-object-id",
        claims={"roles": list(roles), "jti": "synthetic-correlation-id"},
    )


class AuthorizationTests(unittest.TestCase):
    def test_teller_cannot_write_off_loan(self) -> None:
        with self.assertRaisesRegex(AuthorizationError, "INSUFFICIENT_PRIVILEGES"):
            require_role(_principal("Teller"), CREDIT_COMMITTEE_ROLE)

    def test_credit_committee_can_write_off_loan(self) -> None:
        require_role(_principal(CREDIT_COMMITTEE_ROLE), CREDIT_COMMITTEE_ROLE)

    def test_prompt_cannot_supply_a_role(self) -> None:
        principal = _principal("Teller")

        with self.assertRaises(AuthorizationError):
            require_role(principal, "CreditCommittee")


class HardenedToolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        environment = {
            "ENTRA_TENANT_ID": "00000000-0000-0000-0000-000000000001",
            "MCP_API_CLIENT_ID": "00000000-0000-0000-0000-000000000002",
        }
        self.environment_patch = patch.dict("os.environ", environment)
        self.environment_patch.start()

        from agents.hardened.steps.step_01_authorization.server import create_server

        self.server = create_server()
        self.write_off_tool = self.server._tool_manager.get_tool("write_off_loan")
        self.account_tool = self.server._tool_manager.get_tool(
            "list_customer_accounts"
        )
        assert self.write_off_tool is not None
        assert self.account_tool is not None

    def tearDown(self) -> None:
        self.environment_patch.stop()

    async def test_teller_denial_precedes_mutation(self) -> None:
        with (
            patch(
                "agents.hardened.steps.step_01_authorization.server.get_access_token",
                return_value=_token("Teller"),
            ),
            patch(
                "agents.hardened.steps.step_01_authorization.server.handle_call_tool",
                new_callable=AsyncMock,
            ) as baseline_handler,
            patch(
                "agents.hardened.steps.step_01_authorization.server.write_authorization_event"
            ) as audit_writer,
        ):
            with self.assertRaisesRegex(
                ToolError,
                "403 FORBIDDEN: INSUFFICIENT_PRIVILEGES$",
            ):
                await self.write_off_tool.run(
                    {"loan_id": "LOAN-2B-001", "reason": "synthetic attack"}
                )

        baseline_handler.assert_not_awaited()
        self.assertEqual(audit_writer.call_args.kwargs["decision"], "denied")

    async def test_credit_committee_reaches_mutation(self) -> None:
        with (
            patch(
                "agents.hardened.steps.step_01_authorization.server.get_access_token",
                return_value=_token(CREDIT_COMMITTEE_ROLE),
            ),
            patch(
                "agents.hardened.steps.step_01_authorization.server.handle_call_tool",
                new_callable=AsyncMock,
                return_value=[SimpleNamespace(text="Loan written off")],
            ) as baseline_handler,
            patch(
                "agents.hardened.steps.step_01_authorization.server.write_authorization_event"
            ) as audit_writer,
        ):
            result = await self.write_off_tool.run(
                {"loan_id": "LOAN-2B-001", "reason": "approved test"}
            )

        self.assertEqual(result, "Loan written off")
        baseline_handler.assert_awaited_once_with(
            "write_off_loan",
            {"application_id": "LOAN-2B-001", "reason": "approved test"},
        )
        self.assertEqual(audit_writer.call_args.kwargs["decision"], "allowed")

    async def test_account_lookup_uses_baseline_tool_name(self) -> None:
        with patch(
            "agents.hardened.steps.step_01_authorization.server.handle_call_tool",
            new_callable=AsyncMock,
            return_value=[SimpleNamespace(text="[]")],
        ) as baseline_handler:
            result = await self.account_tool.run({"customer_id": 10002})

        self.assertEqual(result, "[]")
        baseline_handler.assert_awaited_once_with(
            "get_customer_accounts", {"customer_id": "10002"}
        )

    async def test_loan_lookup_does_not_use_missing_baseline_dispatcher(self) -> None:
        with patch(
            "agents.hardened.steps.step_01_authorization.server.get_loan_record",
            return_value=SimpleNamespace(
                model_dump=lambda: {"id": "LOAN-2B-001"}
            ),
        ) as loan_lookup:
            result = await self.server._tool_manager.get_tool("get_loan").run(
                {"loan_id": "LOAN-2B-001"}
            )

        self.assertEqual(result, '{"id": "LOAN-2B-001"}')
        loan_lookup.assert_called_once()


if __name__ == "__main__":
    unittest.main()