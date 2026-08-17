from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class EntryDirection(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class AccountType(str, Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class TransactionStatus(str, Enum):
    POSTED = "POSTED"
    VOID = "VOID"


@dataclass(frozen=True)
class LedgerEntry:
    account_id: str
    amount: Decimal
    direction: EntryDirection


@dataclass(frozen=True)
class TransactionRequest:
    description: str
    idempotency_key: str
    entries: tuple[LedgerEntry, ...]
    reference_id: Optional[str] = None


# ============================================================
# SIMULATION MODELS
# ============================================================

class EventType(str, Enum):
    FLIGHT_BOOKING = "FLIGHT_BOOKING"
    HOTEL_BOOKING = "HOTEL_BOOKING"
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"
    CANCELLATION = "CANCELLATION"
    EXPENSE = "EXPENSE"
    TRANSFER = "TRANSFER"
    PAYROLL = "PAYROLL"
    SUBSCRIPTION = "SUBSCRIPTION"


class PaymentMethod(str, Enum):
    CARD = "CARD"
    BANK_TRANSFER = "BANK_TRANSFER"
    MOBILE_MONEY = "MOBILE_MONEY"
    CASH = "CASH"
    DIGITAL_WALLET = "DIGITAL_WALLET"


class SimulationStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"
    REVERSED = "REVERSED"


@dataclass(frozen=True)
class SimulationEvent:
    event_type: EventType
    amount: Decimal
    currency: str
    customer_id: Optional[str]
    payment_method: Optional[PaymentMethod]
    status: SimulationStatus
    reference_id: str
    occurred_at: str


@dataclass(frozen=True)
class CustomerProfile:
    customer_id: str
    country: str
    customer_segment: str
    risk_score: Decimal


@dataclass(frozen=True)
class MerchantProfile:
    merchant_id: str
    merchant_name: str
    merchant_category: str
    country: str


@dataclass(frozen=True)
class AnomalySignal:
    event_id: str
    anomaly_type: str
    severity: str
    score: Decimal
    explanation: str