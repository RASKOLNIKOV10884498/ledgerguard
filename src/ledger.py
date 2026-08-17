from decimal import Decimal
from hashlib import sha256
from typing import Iterable

from psycopg2.extensions import connection

from src.models import LedgerEntry, SimulationEvent
from src.validation import (
    validate_description,
    validate_idempotency_key,
    validate_ledger_entries,
    validate_simulation_event,
)


class LedgerError(Exception):
    """Base exception for LedgerGuard ledger operations."""


def generate_request_hash(
    description: str,
    reference_id: str | None,
    entries: Iterable[LedgerEntry],
) -> str:

    entries = list(entries)

    entry_data = "|".join(
        f"{entry.account_id}:{entry.amount}:{entry.direction.value}"
        for entry in entries
    )

    raw_data = (
        f"{description}|"
        f"{reference_id or ''}|"
        f"{entry_data}"
    )

    return sha256(
        raw_data.encode("utf-8")
    ).hexdigest()


def post_transaction(
    conn: connection,
    *,
    description: str,
    idempotency_key: str,
    entries: Iterable[LedgerEntry],
    reference_id: str | None = None,
    event_type: str | None = None,
    customer_id: str | None = None,
    amount: Decimal | None = None,
    currency: str | None = None,
    payment_method: str | None = None,
    risk_level: str | None = None,
    anomaly_score: float | None = None,
    anomaly_reason: str | None = None,
    occurred_at=None,
) -> str:
    """
    Create an immutable POSTED transaction.

    All transaction metadata is written during the original
    INSERT. Nothing is updated afterward because LedgerGuard
    enforces ledger immutability at the database level.
    """

    description = validate_description(description)

    idempotency_key = validate_idempotency_key(
        idempotency_key
    )

    entries = list(
        validate_ledger_entries(entries)
    )

    request_hash = generate_request_hash(
        description,
        reference_id,
        entries,
    )

    try:

        with conn:

            with conn.cursor() as cursor:

                # ------------------------------------------------
                # Check idempotency
                # ------------------------------------------------

                cursor.execute(
                    """
                    SELECT id, request_hash
                    FROM public.transactions
                    WHERE idempotency_key = %s
                    """,
                    (idempotency_key,),
                )

                existing = cursor.fetchone()

                if existing:

                    existing_id = existing[0]
                    existing_hash = existing[1]

                    if existing_hash == request_hash:
                        return str(existing_id)

                    raise LedgerError(
                        "IDEMPOTENCY VIOLATION: "
                        "This idempotency key already exists "
                        "with different transaction data."
                    )

                # ------------------------------------------------
                # Create immutable transaction
                #
                # IMPORTANT:
                # All simulator/event metadata is inserted here.
                # We never UPDATE this row afterward.
                # ------------------------------------------------

                cursor.execute(
                    """
                    INSERT INTO public.transactions (
                        description,
                        reference_id,
                        idempotency_key,
                        request_hash,
                        status,
                        event_type,
                        customer_id,
                        amount,
                        currency,
                        payment_method,
                        risk_level,
                        anomaly_score,
                        anomaly_reason,
                        occurred_at
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        'POSTED',
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING id
                    """,
                    (
                        description,
                        reference_id,
                        idempotency_key,
                        request_hash,
                        event_type,
                        customer_id,
                        amount,
                        currency,
                        payment_method,
                        risk_level,
                        anomaly_score,
                        anomaly_reason,
                        occurred_at,
                    ),
                )

                transaction_id = cursor.fetchone()[0]

                # ------------------------------------------------
                # Create ledger entries
                # ------------------------------------------------

                for entry in entries:

                    cursor.execute(
                        """
                        INSERT INTO public.entries (
                            transaction_id,
                            account_id,
                            amount,
                            direction
                        )
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            transaction_id,
                            entry.account_id,
                            Decimal(entry.amount),
                            entry.direction.value,
                        ),
                    )

                return str(transaction_id)

    except LedgerError:
        raise

    except Exception as exc:

        raise LedgerError(
            f"Transaction failed and was rolled back: {exc}"
        ) from exc


def post_simulation_event(
    conn,
    event: SimulationEvent,
    entries: Iterable[LedgerEntry],
) -> str:

    event = validate_simulation_event(event)

    description = (
        f"{event.event_type.value} simulation event"
    )

    return post_transaction(
        conn,
        description=description,
        idempotency_key=event.reference_id,
        reference_id=event.reference_id,
        entries=entries,
    )