"""MidTownBank — SQLite database schema and CRUD operations."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from bank.models import (
    Account,
    AgentMessage,
    ComplianceAlert,
    Customer,
    CustomerNote,
    ExternalTransfer,
    Lien,
    LoanApplication,
    Transaction,
)

DB_PATH = Path(__file__).parent / "midtownbank.db"


def get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    """Create all tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            risk_level TEXT NOT NULL DEFAULT 'low',
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            modified_by TEXT,
            modified_at TEXT
        );

        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL REFERENCES customers(id),
            account_type TEXT NOT NULL DEFAULT 'savings',
            balance REAL NOT NULL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'active',
            blocked_reason TEXT,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            modified_by TEXT,
            modified_at TEXT
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            from_account_id TEXT NOT NULL REFERENCES accounts(id),
            to_account_id TEXT NOT NULL REFERENCES accounts(id),
            amount REAL NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'completed',
            transferred_by TEXT NOT NULL,
            transferred_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS external_transfers (
            id TEXT PRIMARY KEY,
            from_account_id TEXT NOT NULL REFERENCES accounts(id),
            beneficiary_name TEXT NOT NULL,
            beneficiary_account TEXT NOT NULL,
            beneficiary_ifsc TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            transfer_mode TEXT NOT NULL DEFAULT 'NEFT',
            status TEXT NOT NULL DEFAULT 'completed',
            transferred_by TEXT NOT NULL,
            transferred_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS customer_notes (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL REFERENCES customers(id),
            note_text TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS liens (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL REFERENCES accounts(id),
            amount REAL NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            placed_by TEXT NOT NULL,
            placed_at TEXT NOT NULL,
            released_by TEXT,
            released_at TEXT
        );

        CREATE TABLE IF NOT EXISTS loan_applications (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL REFERENCES customers(id),
            amount REAL NOT NULL,
            purpose TEXT NOT NULL,
            loan_account_id TEXT UNIQUE REFERENCES accounts(id),
            status TEXT NOT NULL DEFAULT 'pending',
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            decided_by TEXT,
            decided_at TEXT,
            written_off_by TEXT,
            written_off_at TEXT,
            write_off_reason TEXT
        );

        CREATE TABLE IF NOT EXISTS compliance_alerts (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL REFERENCES accounts(id),
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'low',
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open',
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            reviewed_by TEXT,
            modified_by TEXT,
            modified_at TEXT
        );

        CREATE TABLE IF NOT EXISTS agent_messages (
            id TEXT PRIMARY KEY,
            from_agent TEXT NOT NULL,
            to_agent TEXT NOT NULL,
            message_type TEXT NOT NULL DEFAULT 'info',
            payload TEXT NOT NULL DEFAULT '{}',
            signature TEXT,
            created_at TEXT NOT NULL
        );
    """)

    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(loan_applications)")
    }
    if "loan_account_id" not in columns:
        conn.execute(
            "ALTER TABLE loan_applications ADD COLUMN loan_account_id TEXT REFERENCES accounts(id)"
        )
    conn.execute("UPDATE loan_applications SET status = 'rejected' WHERE status = 'denied'")
    _backfill_loan_accounts(conn)
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_loan_applications_account
           ON loan_applications(loan_account_id)
           WHERE loan_account_id IS NOT NULL"""
    )
    conn.commit()


def _new_loan_account_number(conn: sqlite3.Connection, customer_id: str) -> str:
    row = conn.execute(
        "SELECT id FROM accounts WHERE customer_id = ? ORDER BY created_at LIMIT 1",
        (customer_id,),
    ).fetchone()
    branch = row["id"][:3] if row and row["id"][:3].isdigit() else "000"
    while True:
        account_number = f"{branch}4001{uuid.uuid4().int % 100000000:08d}"
        if not conn.execute("SELECT 1 FROM accounts WHERE id = ?", (account_number,)).fetchone():
            return account_number


def _create_loan_account(
    conn: sqlite3.Connection,
    application_id: str,
    customer_id: str,
    amount: float,
    created_by: str,
    created_at: str,
) -> str:
    account_number = _new_loan_account_number(conn, customer_id)
    conn.execute(
        """INSERT INTO accounts
           (id, customer_id, account_type, balance, status, blocked_reason,
            created_by, created_at, modified_by, modified_at)
           VALUES (?, ?, 'loan', ?, 'active', NULL, ?, ?, NULL, NULL)""",
        (account_number, customer_id, amount, created_by, created_at),
    )
    conn.execute(
        "UPDATE loan_applications SET loan_account_id = ? WHERE id = ?",
        (account_number, application_id),
    )
    return account_number


def _backfill_loan_accounts(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """SELECT id, customer_id, amount, status, decided_by, decided_at,
                  written_off_at
           FROM loan_applications
           WHERE status IN ('approved', 'written_off') AND loan_account_id IS NULL"""
    ).fetchall()
    for row in rows:
        account_number = _create_loan_account(
            conn,
            row["id"],
            row["customer_id"],
            row["amount"],
            row["decided_by"] or "loan_operations",
            row["decided_at"] or datetime.now(timezone.utc).isoformat(),
        )
        if row["status"] == "written_off":
            conn.execute(
                "UPDATE accounts SET balance = 0, status = 'written_off', modified_at = ? WHERE id = ?",
                (row["written_off_at"], account_number),
            )
            conn.execute(
                "UPDATE loan_applications SET status = 'approved' WHERE id = ?",
                (row["id"],),
            )


# --- Customer CRUD ---

def get_customer(conn: sqlite3.Connection, customer_id: str) -> Optional[Customer]:
    row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if row:
        return Customer(**dict(row))
    return None


def search_customers(conn: sqlite3.Connection, query: str) -> list[Customer]:
    rows = conn.execute(
        "SELECT * FROM customers WHERE name LIKE ? OR email LIKE ? LIMIT 10",
        (f"%{query}%", f"%{query}%"),
    ).fetchall()
    return [Customer(**dict(r)) for r in rows]


# --- Account CRUD ---

def get_account(conn: sqlite3.Connection, account_id: str) -> Optional[Account]:
    row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if row:
        return Account(**dict(row))
    return None


def get_accounts_for_customer(conn: sqlite3.Connection, customer_id: str) -> list[Account]:
    rows = conn.execute(
        "SELECT * FROM accounts WHERE customer_id = ?", (customer_id,)
    ).fetchall()
    return [Account(**dict(r)) for r in rows]


def block_account(conn: sqlite3.Connection, account_id: str, reason: str) -> Optional[Account]:
    """Block (freeze) an account. Scenario 1A target."""
    conn.execute(
        "UPDATE accounts SET status = 'blocked', blocked_reason = ? WHERE id = ? AND status = 'active'",
        (reason, account_id),
    )
    conn.commit()
    return get_account(conn, account_id)


def unblock_account(conn: sqlite3.Connection, account_id: str) -> Optional[Account]:
    """Unblock a frozen account. Scenario 3A outcome."""
    conn.execute(
        "UPDATE accounts SET status = 'active', blocked_reason = NULL WHERE id = ? AND status = 'blocked'",
        (account_id,),
    )
    conn.commit()
    return get_account(conn, account_id)


# --- Transaction CRUD ---

def list_transactions(
    conn: sqlite3.Connection, account_id: str, limit: int = 10
) -> list[Transaction]:
    rows = conn.execute(
        """SELECT * FROM transactions
           WHERE from_account_id = ? OR to_account_id = ?
           ORDER BY transferred_at DESC LIMIT ?""",
        (account_id, account_id, limit),
    ).fetchall()
    return [Transaction(**dict(r)) for r in rows]


def create_transaction(
    conn: sqlite3.Connection,
    tx_id: str,
    from_account_id: str,
    to_account_id: str,
    amount: float,
    description: str,
    transferred_by: str = "midtown_assistant",
) -> Transaction:
    """Execute a fund transfer. Scenario 2A target — no guardrails in vulnerable version."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE accounts SET balance = balance - ? WHERE id = ?",
        (amount, from_account_id),
    )
    conn.execute(
        "UPDATE accounts SET balance = balance + ? WHERE id = ?",
        (amount, to_account_id),
    )
    conn.execute(
        """INSERT INTO transactions (id, from_account_id, to_account_id, amount, description, status, transferred_by, transferred_at)
           VALUES (?, ?, ?, ?, ?, 'completed', ?, ?)""",
        (tx_id, from_account_id, to_account_id, amount, description, transferred_by, now),
    )
    conn.commit()
    return Transaction(
        id=tx_id,
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        amount=amount,
        description=description,
        status="completed",
        transferred_by=transferred_by,
        transferred_at=now,
    )


def create_external_transfer(
    conn: sqlite3.Connection,
    tx_id: str,
    from_account_id: str,
    beneficiary_name: str,
    beneficiary_account: str,
    beneficiary_ifsc: str,
    amount: float,
    description: str,
    transfer_mode: str = "NEFT",
    transferred_by: str = "midtown_assistant",
) -> ExternalTransfer:
    """Execute an external fund transfer (NEFT/RTGS/IMPS). Scenario 2A target — no guardrails."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE accounts SET balance = balance - ? WHERE id = ?",
        (amount, from_account_id),
    )
    conn.execute(
        """INSERT INTO external_transfers
           (id, from_account_id, beneficiary_name, beneficiary_account, beneficiary_ifsc,
            amount, description, transfer_mode, status, transferred_by, transferred_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?)""",
        (tx_id, from_account_id, beneficiary_name, beneficiary_account,
         beneficiary_ifsc, amount, description, transfer_mode, transferred_by, now),
    )
    conn.commit()
    return ExternalTransfer(
        id=tx_id,
        from_account_id=from_account_id,
        beneficiary_name=beneficiary_name,
        beneficiary_account=beneficiary_account,
        beneficiary_ifsc=beneficiary_ifsc,
        amount=amount,
        description=description,
        transfer_mode=transfer_mode,
        status="completed",
        transferred_by=transferred_by,
        transferred_at=now,
    )


# --- Customer Notes CRUD ---

def get_customer_notes(conn: sqlite3.Connection, customer_id: str) -> list[CustomerNote]:
    rows = conn.execute(
        "SELECT * FROM customer_notes WHERE customer_id = ? ORDER BY created_at DESC",
        (customer_id,),
    ).fetchall()
    return [CustomerNote(**dict(r)) for r in rows]


def add_customer_note(
    conn: sqlite3.Connection, note_id: str, customer_id: str, note_text: str, created_by: str
) -> CustomerNote:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO customer_notes (id, customer_id, note_text, created_by, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (note_id, customer_id, note_text, created_by, now),
    )
    conn.commit()
    return CustomerNote(
        id=note_id, customer_id=customer_id, note_text=note_text,
        created_by=created_by, created_at=now,
    )


# --- Lien CRUD ---

def get_liens(conn: sqlite3.Connection, account_id: str) -> list[Lien]:
    rows = conn.execute(
        "SELECT * FROM liens WHERE account_id = ? ORDER BY placed_at DESC",
        (account_id,),
    ).fetchall()
    return [Lien(**dict(r)) for r in rows]


def mark_lien(
    conn: sqlite3.Connection, lien_id: str, account_id: str, amount: float, reason: str, placed_by: str
) -> Lien:
    """Place a lien (legal hold) on an account."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO liens (id, account_id, amount, reason, status, placed_by, placed_at)
           VALUES (?, ?, ?, ?, 'active', ?, ?)""",
        (lien_id, account_id, amount, reason, placed_by, now),
    )
    conn.commit()
    return Lien(
        id=lien_id, account_id=account_id, amount=amount, reason=reason,
        status="active", placed_by=placed_by, placed_at=now,
    )


def release_lien(conn: sqlite3.Connection, lien_id: str, released_by: str) -> Optional[Lien]:
    """Release a lien. Scenario 1B target — no verification in vulnerable version."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE liens SET status = 'released', released_by = ?, released_at = ? WHERE id = ? AND status = 'active'",
        (released_by, now, lien_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM liens WHERE id = ?", (lien_id,)).fetchone()
    if row:
        return Lien(**dict(row))
    return None


# --- Loan Application CRUD ---

def get_pending_loans(conn: sqlite3.Connection) -> list[LoanApplication]:
    rows = conn.execute(
        "SELECT * FROM loan_applications WHERE status = 'pending' ORDER BY created_at"
    ).fetchall()
    return [LoanApplication(**dict(r)) for r in rows]


def get_loan(conn: sqlite3.Connection, application_id: str) -> Optional[LoanApplication]:
    row = conn.execute(
        "SELECT * FROM loan_applications WHERE id = ?", (application_id,)
    ).fetchone()
    if row:
        return LoanApplication(**dict(row))
    return None


def approve_loan(
    conn: sqlite3.Connection, application_id: str, decided_by: str
) -> Optional[LoanApplication]:
    now = datetime.now(timezone.utc).isoformat()
    loan = get_loan(conn, application_id)
    if not loan or loan.status != "pending":
        return loan
    conn.execute(
        "UPDATE loan_applications SET status = 'approved', decided_by = ?, decided_at = ? WHERE id = ? AND status = 'pending'",
        (decided_by, now, application_id),
    )
    _create_loan_account(
        conn, application_id, loan.customer_id, loan.amount, decided_by, now
    )
    conn.commit()
    return get_loan(conn, application_id)


def deny_loan(
    conn: sqlite3.Connection, application_id: str, decided_by: str
) -> Optional[LoanApplication]:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE loan_applications SET status = 'rejected', decided_by = ?, decided_at = ? WHERE id = ? AND status = 'pending'",
        (decided_by, now, application_id),
    )
    conn.commit()
    return get_loan(conn, application_id)


def write_off_loan(
    conn: sqlite3.Connection, application_id: str, written_off_by: str, reason: str
) -> Optional[LoanApplication]:
    """Write off a loan (erase debt). Scenario 2B target — no role check in vulnerable version."""
    now = datetime.now(timezone.utc).isoformat()
    loan = get_loan(conn, application_id)
    if not loan or loan.status != "approved" or not loan.loan_account_id:
        return loan
    conn.execute(
        """UPDATE loan_applications
           SET written_off_by = ?, written_off_at = ?, write_off_reason = ?
           WHERE id = ? AND status = 'approved'""",
        (written_off_by, now, reason, application_id),
    )
    conn.execute(
        """UPDATE accounts
           SET balance = 0, status = 'written_off', modified_by = ?, modified_at = ?
           WHERE id = ? AND account_type = 'loan'""",
        (written_off_by, now, loan.loan_account_id),
    )
    conn.commit()
    return get_loan(conn, application_id)


# --- Compliance Alerts CRUD ---

def get_compliance_alerts(conn: sqlite3.Connection, status: Optional[str] = None) -> list[ComplianceAlert]:
    if status:
        rows = conn.execute(
            "SELECT * FROM compliance_alerts WHERE status = ? ORDER BY created_at DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM compliance_alerts ORDER BY created_at DESC"
        ).fetchall()
    return [ComplianceAlert(**dict(r)) for r in rows]


def create_compliance_alert(
    conn: sqlite3.Connection,
    alert_id: str,
    account_id: str,
    alert_type: str,
    severity: str,
    description: str,
) -> ComplianceAlert:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO compliance_alerts (id, account_id, alert_type, severity, description, status, created_at)
           VALUES (?, ?, ?, ?, ?, 'open', ?)""",
        (alert_id, account_id, alert_type, severity, description, now),
    )
    conn.commit()
    return ComplianceAlert(
        id=alert_id, account_id=account_id, alert_type=alert_type,
        severity=severity, description=description, status="open", created_at=now,
    )


def escalate_alert(
    conn: sqlite3.Connection, alert_id: str
) -> Optional[ComplianceAlert]:
    """Escalate alert to human reviewer. Scenario 3A target."""
    conn.execute(
        "UPDATE compliance_alerts SET status = 'escalated' WHERE id = ? AND status = 'open'",
        (alert_id,),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM compliance_alerts WHERE id = ?", (alert_id,)).fetchone()
    if row:
        return ComplianceAlert(**dict(row))
    return None


# --- Agent Messages CRUD ---

def send_agent_message(
    conn: sqlite3.Connection,
    msg_id: str,
    from_agent: str,
    to_agent: str,
    message_type: str,
    payload: dict,
    signature: Optional[str] = None,
) -> AgentMessage:
    now = datetime.now(timezone.utc).isoformat()
    payload_json = json.dumps(payload)
    conn.execute(
        """INSERT INTO agent_messages (id, from_agent, to_agent, message_type, payload, signature, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (msg_id, from_agent, to_agent, message_type, payload_json, signature, now),
    )
    conn.commit()
    return AgentMessage(
        id=msg_id, from_agent=from_agent, to_agent=to_agent,
        message_type=message_type, payload=payload_json, signature=signature, created_at=now,
    )


def get_agent_messages(
    conn: sqlite3.Connection, to_agent: str, limit: int = 5
) -> list[AgentMessage]:
    rows = conn.execute(
        """SELECT * FROM agent_messages WHERE to_agent = ?
           ORDER BY created_at DESC LIMIT ?""",
        (to_agent, limit),
    ).fetchall()
    return [AgentMessage(**dict(r)) for r in rows]


# --- Init ---

def init_db() -> sqlite3.Connection:
    """Initialize database and return connection."""
    conn = get_connection()
    create_schema(conn)
    return conn


if __name__ == "__main__":
    conn = init_db()
    print(f"Database created at {DB_PATH}")
    conn.close()
