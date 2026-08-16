"""MidTownBank — Pydantic data models for all entities."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


# --- Enums ---

class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class AccountType(str, Enum):
    savings = "savings"
    salary = "salary"
    current = "current"
    loan = "loan"


class AccountStatus(str, Enum):
    active = "active"
    blocked = "blocked"
    closed = "closed"
    written_off = "written_off"


class TransactionStatus(str, Enum):
    completed = "completed"
    pending = "pending"
    failed = "failed"


class LoanStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class LienStatus(str, Enum):
    active = "active"
    released = "released"


class AlertType(str, Enum):
    suspicious_transfer = "suspicious_transfer"
    velocity_breach = "velocity_breach"
    sanctions_match = "sanctions_match"
    fraud_investigation = "fraud_investigation"


class AlertSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertStatus(str, Enum):
    open = "open"
    escalated = "escalated"
    resolved = "resolved"
    dismissed = "dismissed"


class MessageType(str, Enum):
    risk_assessment = "risk_assessment"
    action_request = "action_request"
    clearance = "clearance"
    info = "info"


# --- Models ---

class Customer(BaseModel):
    id: str
    name: str
    email: str
    phone: str
    address: str
    risk_level: RiskLevel
    created_by: str
    created_at: datetime
    modified_by: Optional[str] = None
    modified_at: Optional[datetime] = None


class Account(BaseModel):
    id: str
    customer_id: str
    account_type: AccountType
    balance: float
    status: AccountStatus
    blocked_reason: Optional[str] = None
    created_by: str
    created_at: datetime
    modified_by: Optional[str] = None
    modified_at: Optional[datetime] = None


class Transaction(BaseModel):
    id: str
    from_account_id: str
    to_account_id: str
    amount: float
    description: str
    status: TransactionStatus
    transferred_by: str
    transferred_at: datetime


class ExternalTransfer(BaseModel):
    id: str
    from_account_id: str
    beneficiary_name: str
    beneficiary_account: str
    beneficiary_ifsc: str
    amount: float
    description: str
    transfer_mode: str  # NEFT / RTGS / IMPS
    status: TransactionStatus
    transferred_by: str
    transferred_at: datetime


class CustomerNote(BaseModel):
    id: str
    customer_id: str
    note_text: str
    created_by: str
    created_at: datetime


class Lien(BaseModel):
    id: str
    account_id: str
    amount: float
    reason: str
    status: LienStatus
    placed_by: str
    placed_at: datetime
    released_by: Optional[str] = None
    released_at: Optional[datetime] = None


class LoanApplication(BaseModel):
    id: str
    customer_id: str
    amount: float
    purpose: str
    loan_account_id: Optional[str] = None
    status: LoanStatus
    created_by: str
    created_at: datetime
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    written_off_by: Optional[str] = None
    written_off_at: Optional[datetime] = None
    write_off_reason: Optional[str] = None


class ComplianceAlert(BaseModel):
    id: str
    account_id: str
    alert_type: AlertType
    severity: AlertSeverity
    description: str
    status: AlertStatus
    created_by: str
    created_at: datetime
    reviewed_by: Optional[str] = None
    modified_by: Optional[str] = None
    modified_at: Optional[datetime] = None


class AgentMessage(BaseModel):
    id: str
    from_agent: str
    to_agent: str
    message_type: MessageType
    payload: str  # JSON string
    signature: Optional[str] = None  # HMAC — null in vulnerable version
    created_at: datetime
