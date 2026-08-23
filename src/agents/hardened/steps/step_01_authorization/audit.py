"""JSON Lines security audit records for authorization decisions."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.hardened.steps.step_01_authorization.auth import EntraPrincipal

_write_lock = threading.Lock()


def write_authorization_event(
    principal: EntraPrincipal,
    *,
    tool: str,
    resource: str,
    decision: str,
    correlation_id: str,
) -> None:
    path = Path(
        os.getenv(
            "AUTHORIZATION_AUDIT_LOG",
            "data/attack-logs/hardened-step-01-authorization.jsonl",
        )
    )
    event: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "caller_oid": principal.object_id,
        "client_id": principal.client_id,
        "tool": tool,
        "resource": resource,
        "decision": decision,
        "correlation_id": correlation_id,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock, path.open("a", encoding="utf-8") as audit_file:
        audit_file.write(json.dumps(event, sort_keys=True) + "\n")