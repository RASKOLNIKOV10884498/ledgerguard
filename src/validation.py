from decimal import Decimal, InvalidOperation
from typing import Iterable

from src.models import (
    EventType,
    LedgerEntry,
    PaymentMethod,
    SimulationEvent,
    SimulationStatus,
)


class ValidationError(ValueError):
    """Raised when LedgerGuard receives invalid data."""


# ============================================================
# BASIC VALIDATION
# ============================================================

def validate_amount(amount: Decimal) -> Decimal:
    """Validate a monetary amount."""

    try:
        value = Decimal(amount)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Amount must be a valid number.") from exc

    if value <= 0:
        raise ValidationError("Amount must be greater than zero.")

    return value.quantize(Decimal("0.0001"))


def validate_description(description: str) -> str:
    """Validate a transaction description."""

    if not isinstance(description, str):
        raise ValidationError("Description must be a string.")

    description = description.strip()

    if not description:
        raise ValidationError("Description cannot be empty.")

    if len(description) > 500:
        raise ValidationError(
            "Description cannot exceed 500 characters."
        )

    return description


def validate_idempotency_key(key: str) -> str:
    """Validate the transaction idempotency key."""

    if not isinstance(key, str):
        raise ValidationError(
            "Idempotency key must be a string."
        )

    key = key.strip()

    if not key:
        raise ValidationError(
            "Idempotency key cannot be empty."
        )

    if len(key) > 255:
        raise ValidationError(
            "Idempotency key cannot exceed 255 characters."
        )

    return key


# ============================================================
# LEDGER VALIDATION
# ============================================================

def validate_ledger_entries(
    entries: Iterable[LedgerEntry],
) -> list[LedgerEntry]:
    """
    Validate a complete double-entry transaction.

    Rules:

    1. At least two entries.
    2. Every amount must be positive.
    3. Debits must equal credits.
    """

    entries = list(entries)

    if len(entries) < 2:
        raise ValidationError(
            "A transaction must contain at least two ledger entries."
        )

    debit_total = Decimal("0")
    credit_total = Decimal("0")

    validated_entries = []

    for entry in entries:

        amount = validate_amount(entry.amount)

        if entry.direction.value == "DEBIT":
            debit_total += amount

        elif entry.direction.value == "CREDIT":
            credit_total += amount

        else:
            raise ValidationError(
                f"Invalid entry direction: {entry.direction}"
            )

        validated_entries.append(
            LedgerEntry(
                account_id=entry.account_id,
                amount=amount,
                direction=entry.direction,
            )
        )

    if debit_total != credit_total:
        raise ValidationError(
            f"Transaction is unbalanced: "
            f"debits={debit_total}, "
            f"credits={credit_total}."
        )

    return validated_entries


# ============================================================
# SIMULATION VALIDATION
# ============================================================

def validate_currency(currency: str) -> str:
    """Validate ISO-style three-letter currency code."""

    if not isinstance(currency, str):
        raise ValidationError(
            "Currency must be a string."
        )

    currency = currency.strip().upper()

    if len(currency) != 3 or not currency.isalpha():
        raise ValidationError(
            "Currency must be a three-letter code."
        )

    return currency


def validate_customer_id(
    customer_id: str | None,
) -> str | None:
    """Validate optional customer identifier."""

    if customer_id is None:
        return None

    if not isinstance(customer_id, str):
        raise ValidationError(
            "Customer ID must be a string."
        )

    customer_id = customer_id.strip()

    if not customer_id:
        raise ValidationError(
            "Customer ID cannot be empty."
        )

    return customer_id


def validate_reference_id(
    reference_id: str,
) -> str:
    """Validate an event reference identifier."""

    if not isinstance(reference_id, str):
        raise ValidationError(
            "Reference ID must be a string."
        )

    reference_id = reference_id.strip()

    if not reference_id:
        raise ValidationError(
            "Reference ID cannot be empty."
        )

    if len(reference_id) > 255:
        raise ValidationError(
            "Reference ID cannot exceed 255 characters."
        )

    return reference_id


def validate_simulation_event(
    event: SimulationEvent,
) -> SimulationEvent:
    """
    Validate and normalize a simulated financial event.
    """

    if not isinstance(event, SimulationEvent):
        raise ValidationError(
            "Expected a SimulationEvent."
        )

    amount = validate_amount(event.amount)

    currency = validate_currency(event.currency)

    customer_id = validate_customer_id(
        event.customer_id
    )

    reference_id = validate_reference_id(
        event.reference_id
    )

    if not isinstance(event.event_type, EventType):
        raise ValidationError(
            "Invalid simulation event type."
        )

    if event.payment_method is not None:
        if not isinstance(
            event.payment_method,
            PaymentMethod,
        ):
            raise ValidationError(
                "Invalid payment method."
            )

    if not isinstance(
        event.status,
        SimulationStatus,
    ):
        raise ValidationError(
            "Invalid simulation status."
        )

    if not isinstance(event.occurred_at, str):
        raise ValidationError(
            "Event timestamp must be a string."
        )

    if not event.occurred_at.strip():
        raise ValidationError(
            "Event timestamp cannot be empty."
        )

    return SimulationEvent(
        event_type=event.event_type,
        amount=amount,
        currency=currency,
        customer_id=customer_id,
        payment_method=event.payment_method,
        status=event.status,
        reference_id=reference_id,
        occurred_at=event.occurred_at.strip(),
    )