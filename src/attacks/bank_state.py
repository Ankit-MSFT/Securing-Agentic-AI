"""Snapshot/restore the bank SQLite DB between attack runs.

Uses SQLite's online backup API so restore works even while the MCP server
holds an open connection to the live DB.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from common import SRC_ROOT

BANK_DB_PATH: Path = SRC_ROOT / "bank" / "midtownbank.db"
BANK_DB_BACKUP: Path = BANK_DB_PATH.with_name(
    BANK_DB_PATH.stem + ".baseline" + BANK_DB_PATH.suffix
)


def _sqlite_backup(src: str | Path, dst: str | Path) -> None:
    src_conn = sqlite3.connect(str(src))
    try:
        dst_conn = sqlite3.connect(str(dst))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def snapshot() -> None:
    """Capture the current seeded DB as the per-run baseline."""
    _sqlite_backup(BANK_DB_PATH, BANK_DB_BACKUP)


def restore() -> None:
    """Restore the DB to the captured baseline. Called between runs."""
    if not BANK_DB_BACKUP.exists():
        raise RuntimeError(
            f"No baseline snapshot at {BANK_DB_BACKUP}. Call snapshot() first."
        )
    _sqlite_backup(BANK_DB_BACKUP, BANK_DB_PATH)
