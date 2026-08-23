"""Microsoft Entra token validation and operation-level authorization."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Callable

import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken

REQUIRED_SCOPE = "access_as_user"
CREDIT_COMMITTEE_ROLE = "CreditCommittee"
_logger = logging.getLogger(__name__)


class AuthenticationError(ValueError):
    """The caller did not present a valid MidTownBank API access token."""


class AuthorizationError(PermissionError):
    """The authenticated caller is not permitted to perform an operation."""


@dataclass(frozen=True)
class EntraPrincipal:
    object_id: str
    client_id: str
    scopes: frozenset[str]
    roles: frozenset[str]

    @classmethod
    def from_access_token(cls, access_token: AccessToken) -> EntraPrincipal:
        claims = access_token.claims or {}
        return cls(
            object_id=access_token.subject or "",
            client_id=access_token.client_id,
            scopes=frozenset(access_token.scopes),
            roles=frozenset(claims.get("roles", [])),
        )


def require_role(principal: EntraPrincipal, required_role: str) -> None:
    if required_role not in principal.roles:
        raise AuthorizationError("INSUFFICIENT_PRIVILEGES")


class EntraTokenVerifier:
    """Validate single-tenant Entra v2 access tokens issued for the MCP API."""

    def __init__(
        self,
        tenant_id: str | None = None,
        audience: str | None = None,
        signing_key_resolver: Callable[[str], Any] | None = None,
    ) -> None:
        self.tenant_id = tenant_id or os.environ.get("ENTRA_TENANT_ID", "")
        self.audience = audience or os.environ.get(
            "ENTRA_MCP_API_CLIENT_ID", os.environ.get("MCP_API_CLIENT_ID", "")
        )
        if not self.tenant_id or not self.audience:
            raise RuntimeError(
                "ENTRA_TENANT_ID and ENTRA_MCP_API_CLIENT_ID must be configured"
            )

        self.issuer = f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"
        self.legacy_issuer = (
            f"https://sts.windows.net/{self.tenant_id}/"
        )
        jwks_url = (
            f"https://login.microsoftonline.com/{self.tenant_id}/"
            "discovery/v2.0/keys"
        )
        self._jwks_client = PyJWKClient(jwks_url)
        self._signing_key_resolver = (
            signing_key_resolver or self._jwks_client.get_signing_key_from_jwt
        )

    def _decode(self, token: str) -> dict[str, Any]:
        signing_key = self._signing_key_resolver(token)
        key = getattr(signing_key, "key", signing_key)
        return jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=[self.audience, f"api://{self.audience}"],
            issuer=[self.issuer, self.legacy_issuer],
            options={"require": ["exp", "iat", "iss", "aud", "tid", "oid"]},
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = await asyncio.to_thread(self._decode, token)
        except Exception as error:
            try:
                unverified_claims = jwt.decode(
                    token, options={"verify_signature": False}
                )
                _logger.warning(
                    "Entra token rejected during signature validation: %s; "
                    "aud=%r iss=%r tid=%r scp=%r oid_present=%s",
                    type(error).__name__,
                    unverified_claims.get("aud"),
                    unverified_claims.get("iss"),
                    unverified_claims.get("tid"),
                    unverified_claims.get("scp"),
                    bool(unverified_claims.get("oid")),
                )
            except Exception:
                _logger.warning(
                    "Entra token rejected and could not inspect its claims: %s",
                    type(error).__name__,
                )
            return None

        if claims.get("tid") != self.tenant_id:
            _logger.warning("Entra token rejected: tenant mismatch")
            return None

        scopes = str(claims.get("scp", "")).split()
        if REQUIRED_SCOPE not in scopes:
            _logger.warning("Entra token rejected: required scope is absent")
            return None

        client_id = claims.get("azp") or claims.get("appid")
        if not client_id:
            _logger.warning("Entra token rejected: client ID claim is absent")
            return None

        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=claims.get("exp"),
            resource=self.audience,
            subject=claims["oid"],
            claims=claims,
        )