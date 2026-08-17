from __future__ import annotations

import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256

from src.database import (
    close_pool,
    get_connection,
    initialize_pool,
    release_connection,
)
from src.ledger import post_transaction
from src.models import EntryDirection, LedgerEntry


# ============================================================
# LEDGERGUARD ADVANCED SYNTHETIC DATA ENGINE
# ============================================================

EVENT_TYPES = [
    "FLIGHT_BOOKING",
    "HOTEL_BOOKING",
    "PAYMENT",
    "REFUND",
    "PROCESSING_FEE",
    "CORPORATE_BOOKING",
]

PAYMENT_METHODS = [
    "CARD",
    "BANK_TRANSFER",
    "MOBILE_MONEY",
    "DIGITAL_WALLET",
]

CURRENCIES = [
    "USD",
    "EUR",
    "GBP",
    "GHS",
]

STATUSES = [
    "SUCCESS",
    "FAILED",
    "DECLINED",
]


# ============================================================
# CUSTOMER BEHAVIOR
# ============================================================

@dataclass
class CustomerProfile:
    customer_id: str
    preferred_currency: str
    preferred_payment_method: str
    risk_level: str

    average_transaction: Decimal

    transaction_frequency: float

    lifetime_value: Decimal

    transactions_today: int = 0

    last_transaction_at: datetime | None = None


# ============================================================
# SYNTHETIC EVENT
# ============================================================

@dataclass
class SyntheticEvent:
    event_type: str
    customer_id: str
    amount: Decimal
    currency: str
    payment_method: str
    status: str
    reference_id: str
    occurred_at: datetime
    risk_level: str

    anomaly_score: float = 0.0

    anomaly_reason: str | None = None


# ============================================================
# GLOBAL CUSTOMER STATE
# ============================================================

CUSTOMERS: list[CustomerProfile] = []


# ============================================================
# CUSTOMER CREATION
# ============================================================

def create_customer_pool(
    count: int = 250,
) -> None:

    CUSTOMERS.clear()

    for _ in range(count):

        risk_level = random.choices(
            ["LOW", "MEDIUM", "HIGH"],
            weights=[72, 23, 5],
            k=1,
        )[0]

        # --------------------------------------------------------
        # LOW RISK
        # --------------------------------------------------------

        if risk_level == "LOW":

            average_transaction = Decimal(
                str(
                    round(
                        random.uniform(
                            100,
                            800,
                        ),
                        2,
                    )
                )
            )

            frequency = random.uniform(
                0.05,
                1.5,
            )

        # --------------------------------------------------------
        # MEDIUM RISK
        # --------------------------------------------------------

        elif risk_level == "MEDIUM":

            average_transaction = Decimal(
                str(
                    round(
                        random.uniform(
                            500,
                            3000,
                        ),
                        2,
                    )
                )
            )

            frequency = random.uniform(
                0.2,
                3.0,
            )

        # --------------------------------------------------------
        # HIGH RISK
        # --------------------------------------------------------

        else:

            average_transaction = Decimal(
                str(
                    round(
                        random.uniform(
                            1500,
                            10000,
                        ),
                        2,
                    )
                )
            )

            frequency = random.uniform(
                1.0,
                8.0,
            )

        CUSTOMERS.append(
            CustomerProfile(
                customer_id=(
                    f"CUST-"
                    f"{random.randint(100000, 999999)}"
                ),
                preferred_currency=random.choice(
                    CURRENCIES
                ),
                preferred_payment_method=random.choice(
                    PAYMENT_METHODS
                ),
                risk_level=risk_level,
                average_transaction=average_transaction,
                transaction_frequency=frequency,
                lifetime_value=Decimal("0.00"),
            )
        )


# ============================================================
# CUSTOMER SELECTION
# ============================================================

def choose_customer() -> CustomerProfile:

    if not CUSTOMERS:

        create_customer_pool()

    weights = []

    for customer in CUSTOMERS:

        weight = 1.0

        # Medium-risk customers are somewhat more active.
        if customer.risk_level == "MEDIUM":

            weight *= 1.5

        # High-risk customers are more active.
        elif customer.risk_level == "HIGH":

            weight *= 3.0

        # Customers who already transacted today
        # are slightly more likely to transact again.
        if customer.transactions_today > 0:

            weight *= 1.2

        weights.append(weight)

    return random.choices(
        CUSTOMERS,
        weights=weights,
        k=1,
    )[0]


# ============================================================
# EVENT TYPE MODEL
# ============================================================

def choose_event_type(
    customer: CustomerProfile,
) -> str:

    # --------------------------------------------------------
    # HIGH RISK
    # --------------------------------------------------------

    if customer.risk_level == "HIGH":

        return random.choices(
            EVENT_TYPES,
            weights=[
                25,  # FLIGHT_BOOKING
                12,  # HOTEL_BOOKING
                25,  # PAYMENT
                15,  # REFUND
                8,   # PROCESSING_FEE
                15,  # CORPORATE_BOOKING
            ],
            k=1,
        )[0]

    # --------------------------------------------------------
    # MEDIUM RISK
    # --------------------------------------------------------

    if customer.risk_level == "MEDIUM":

        return random.choices(
            EVENT_TYPES,
            weights=[
                35,
                18,
                20,
                8,
                12,
                7,
            ],
            k=1,
        )[0]

    # --------------------------------------------------------
    # LOW RISK
    # --------------------------------------------------------

    return random.choices(
        EVENT_TYPES,
        weights=[
            38,
            20,
            20,
            6,
            12,
            4,
        ],
        k=1,
    )[0]


# ============================================================
# ANOMALY DECISION
# ============================================================

def should_create_anomaly(
    customer: CustomerProfile,
) -> bool:

    if customer.risk_level == "HIGH":

        return random.random() < 0.25

    if customer.risk_level == "MEDIUM":

        return random.random() < 0.08

    return random.random() < 0.02


# ============================================================
# AMOUNT GENERATION
# ============================================================

def generate_amount(
    customer: CustomerProfile,
    event_type: str,
    anomaly: bool,
) -> tuple[Decimal, str | None]:

    base = float(
        customer.average_transaction
    )

    anomaly_reason = None

    # --------------------------------------------------------
    # PROCESSING FEE
    # --------------------------------------------------------

    if event_type == "PROCESSING_FEE":

        amount = random.uniform(
            5,
            150,
        )

    # --------------------------------------------------------
    # REFUND
    # --------------------------------------------------------

    elif event_type == "REFUND":

        amount = base * random.uniform(
            0.2,
            1.0,
        )

    # --------------------------------------------------------
    # CORPORATE BOOKING
    # --------------------------------------------------------

    elif event_type == "CORPORATE_BOOKING":

        amount = random.uniform(
            5000,
            50000,
        )

    # --------------------------------------------------------
    # NORMAL TRANSACTION
    # --------------------------------------------------------

    else:

        amount = base * random.uniform(
            0.4,
            1.8,
        )

    # --------------------------------------------------------
    # ANOMALOUS TRANSACTION
    # --------------------------------------------------------

    if anomaly:

        multiplier = random.uniform(
            4.0,
            15.0,
        )

        amount *= multiplier

        anomaly_reason = (
            "UNUSUALLY_LARGE_TRANSACTION"
        )

    return (
        Decimal(
            str(
                round(
                    max(amount, 1),
                    2,
                )
            )
        ),
        anomaly_reason,
    )


# ============================================================
# STATUS GENERATION
# ============================================================

def generate_status(
    customer: CustomerProfile,
) -> str:

    # --------------------------------------------------------
    # HIGH RISK
    # --------------------------------------------------------

    if customer.risk_level == "HIGH":

        return random.choices(
            STATUSES,
            weights=[
                72,  # SUCCESS
                18,  # FAILED
                10,  # DECLINED
            ],
            k=1,
        )[0]

    # --------------------------------------------------------
    # MEDIUM RISK
    # --------------------------------------------------------

    if customer.risk_level == "MEDIUM":

        return random.choices(
            STATUSES,
            weights=[
                86,
                9,
                5,
            ],
            k=1,
        )[0]

    # --------------------------------------------------------
    # LOW RISK
    # --------------------------------------------------------

    return random.choices(
        STATUSES,
        weights=[
            94,
            4,
            2,
        ],
        k=1,
    )[0]


# ============================================================
# CURRENCY
# ============================================================

def generate_currency(
    customer: CustomerProfile,
) -> str:

    if random.random() < 0.80:

        return customer.preferred_currency

    return random.choice(
        CURRENCIES
    )


# ============================================================
# PAYMENT METHOD
# ============================================================

def generate_payment_method(
    customer: CustomerProfile,
) -> str:

    if random.random() < 0.80:

        return customer.preferred_payment_method

    return random.choice(
        PAYMENT_METHODS
    )


# ============================================================
# REFERENCE ID
# ============================================================

def generate_reference_id() -> str:

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d")

    random_component = (
        uuid.uuid4()
        .hex[:12]
        .upper()
    )

    return (
        f"SIM-{timestamp}-"
        f"{random_component}"
    )


# ============================================================
# EVENT HASH
# ============================================================

def generate_event_hash(
    event: SyntheticEvent,
) -> str:

    raw_data = "|".join(
        [
            event.event_type,
            event.customer_id,
            str(event.amount),
            event.currency,
            event.payment_method,
            event.status,
            event.reference_id,
            event.occurred_at.isoformat(),
            event.risk_level,
            str(event.anomaly_score),
            event.anomaly_reason or "",
        ]
    )

    return sha256(
        raw_data.encode("utf-8")
    ).hexdigest()


# ============================================================
# EVENT GENERATOR
# ============================================================

def generate_event() -> SyntheticEvent:

    customer = choose_customer()

    event_type = choose_event_type(
        customer
    )

    anomaly = should_create_anomaly(
        customer
    )

    amount, anomaly_reason = (
        generate_amount(
            customer,
            event_type,
            anomaly,
        )
    )

    status = generate_status(
        customer
    )

    currency = generate_currency(
        customer
    )

    payment_method = (
        generate_payment_method(
            customer
        )
    )

    occurred_at = datetime.now(
        timezone.utc
    )

    reference_id = (
        generate_reference_id()
    )

    # --------------------------------------------------------
    # UPDATE CUSTOMER STATE
    # --------------------------------------------------------

    customer.transactions_today += 1

    customer.last_transaction_at = (
        occurred_at
    )

    if status == "SUCCESS":

        customer.lifetime_value += amount

    # --------------------------------------------------------
    # CALCULATE ANOMALY SCORE
    # --------------------------------------------------------

    anomaly_score = 0.0

    if anomaly:

        anomaly_score += 0.70

    if customer.risk_level == "HIGH":

        anomaly_score += 0.15

    if customer.transactions_today >= 5:

        anomaly_score += 0.10

    if amount > (
        customer.average_transaction * 5
    ):

        anomaly_score += 0.20

    anomaly_score = min(
        anomaly_score,
        1.0,
    )

    return SyntheticEvent(
        event_type=event_type,
        customer_id=customer.customer_id,
        amount=amount,
        currency=currency,
        payment_method=payment_method,
        status=status,
        reference_id=reference_id,
        occurred_at=occurred_at,
        risk_level=customer.risk_level,
        anomaly_score=round(
            anomaly_score,
            3,
        ),
        anomaly_reason=anomaly_reason,
    )


# ============================================================
# ACCOUNT LOOKUP
# ============================================================

def get_account_id(
    conn,
    account_name: str,
) -> str:

    with conn.cursor() as cursor:

        cursor.execute(
            """
            SELECT id
            FROM public.accounts
            WHERE name = %s
            """,
            (account_name,),
        )

        result = cursor.fetchone()

        if result is None:

            raise RuntimeError(
                f"Account not found: "
                f"{account_name}"
            )

        return str(result[0])


# ============================================================
# LEDGER ENTRY FACTORY
# ============================================================

def create_ledger_entries(
    conn,
    event: SyntheticEvent,
) -> list[LedgerEntry] | None:

    # --------------------------------------------------------
    # FAILED / DECLINED EVENTS
    #
    # These remain transaction events in the database,
    # but they do NOT create financial ledger entries.
    # --------------------------------------------------------

    if event.status != "SUCCESS":

        return None

    cash = get_account_id(
        conn,
        "1000 - Operating Cash",
    )

    revenue = get_account_id(
        conn,
        "4000 - Flight Booking Revenue",
    )

    expense = get_account_id(
        conn,
        "5000 - Transaction Processing Expense",
    )

    # --------------------------------------------------------
    # REVENUE TRANSACTIONS
    # --------------------------------------------------------

    if event.event_type in {
        "FLIGHT_BOOKING",
        "HOTEL_BOOKING",
        "PAYMENT",
        "CORPORATE_BOOKING",
    }:

        return [
            LedgerEntry(
                account_id=cash,
                amount=event.amount,
                direction=(
                    EntryDirection.DEBIT
                ),
            ),
            LedgerEntry(
                account_id=revenue,
                amount=event.amount,
                direction=(
                    EntryDirection.CREDIT
                ),
            ),
        ]

    # --------------------------------------------------------
    # REFUND
    # --------------------------------------------------------

    if event.event_type == "REFUND":

        return [
            LedgerEntry(
                account_id=revenue,
                amount=event.amount,
                direction=(
                    EntryDirection.DEBIT
                ),
            ),
            LedgerEntry(
                account_id=cash,
                amount=event.amount,
                direction=(
                    EntryDirection.CREDIT
                ),
            ),
        ]

    # --------------------------------------------------------
    # PROCESSING FEE
    # --------------------------------------------------------

    if event.event_type == "PROCESSING_FEE":

        return [
            LedgerEntry(
                account_id=expense,
                amount=event.amount,
                direction=(
                    EntryDirection.DEBIT
                ),
            ),
            LedgerEntry(
                account_id=cash,
                amount=event.amount,
                direction=(
                    EntryDirection.CREDIT
                ),
            ),
        ]

    return None


# ============================================================
# RECORD FAILED / DECLINED EVENT
# ============================================================

def record_non_posted_event(
    conn,
    event: SyntheticEvent,
) -> str:

    request_hash = generate_event_hash(
        event
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
                    (event.reference_id,),
                )

                existing = cursor.fetchone()

                if existing:

                    existing_id = existing[0]
                    existing_hash = existing[1]

                    if existing_hash == request_hash:

                        return str(
                            existing_id
                        )

                    raise RuntimeError(
                        "IDEMPOTENCY VIOLATION: "
                        "This event reference already "
                        "exists with different data."
                    )

                # ------------------------------------------------
                # Insert failed / declined event.
                #
                # This is INSERT-only.
                # No UPDATE will ever be performed.
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
                        %s,
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
                        (
                            f"Automated "
                            f"{event.event_type.lower()}"
                        ),
                        event.reference_id,
                        event.reference_id,
                        request_hash,
                        event.status,
                        event.event_type,
                        event.customer_id,
                        event.amount,
                        event.currency,
                        event.payment_method,
                        event.risk_level,
                        event.anomaly_score,
                        event.anomaly_reason,
                        event.occurred_at,
                    ),
                )

                transaction_id = (
                    cursor.fetchone()[0]
                )

                return str(
                    transaction_id
                )

    except Exception as exc:

        raise RuntimeError(
            "Failed to record "
            f"{event.status.lower()} event: {exc}"
        ) from exc


# ============================================================
# EVENT PROCESSOR
# ============================================================

def process_event(
    conn,
    event: SyntheticEvent,
) -> str | None:

    anomaly_marker = ""

    if event.anomaly_score >= 0.70:

        anomaly_marker = (
            f" ⚠ ANOMALY "
            f"{event.anomaly_score:.2f}"
        )

    print(
        f"[EVENT] "
        f"{event.event_type:<20} "
        f"{event.status:<9} "
        f"{event.currency:<4} "
        f"{event.amount:>12} "
        f"{event.payment_method:<16} "
        f"{event.customer_id:<12} "
        f"RISK={event.risk_level}"
        f"{anomaly_marker}"
    )

    if event.anomaly_reason:

        print(
            f"    ├── "
            f"REASON: "
            f"{event.anomaly_reason}"
        )

    # --------------------------------------------------------
    # FAILED / DECLINED
    #
    # Store the event metadata but do not create ledger entries.
    # --------------------------------------------------------

    if event.status != "SUCCESS":

        transaction_id = (
            record_non_posted_event(
                conn,
                event,
            )
        )

        print(
            f"    └── NOT POSTED "
            f"({event.status}) "
            f"transaction={transaction_id}"
        )

        return None

    # --------------------------------------------------------
    # SUCCESS
    #
    # Create balanced ledger entries.
    # --------------------------------------------------------

    entries = create_ledger_entries(
        conn,
        event,
    )

    if entries is None:

        print(
            "    └── NOT POSTED "
            "(NO LEDGER ENTRIES)"
        )

        return None

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # ALL EVENT METADATA IS INSERTED INTO transactions
    # DURING THE ORIGINAL POST.
    #
    # We DO NOT call UPDATE afterward.
    #
    # This is required because the database enforces
    # ledger immutability.
    # --------------------------------------------------------

    transaction_id = post_transaction(
        conn,
        description=(
            f"Automated "
            f"{event.event_type.lower()}"
        ),
        reference_id=event.reference_id,
        idempotency_key=event.reference_id,
        entries=entries,
        event_type=event.event_type,
        customer_id=event.customer_id,
        amount=event.amount,
        currency=event.currency,
        payment_method=event.payment_method,
        risk_level=event.risk_level,
        anomaly_score=event.anomaly_score,
        anomaly_reason=event.anomaly_reason,
        occurred_at=event.occurred_at,
    )

    print(
        f"    └── POSTED "
        f"transaction={transaction_id}"
    )

    return transaction_id


# ============================================================
# CUSTOMER STATISTICS
# ============================================================

def print_customer_statistics() -> None:

    if not CUSTOMERS:

        return

    total_lifetime_value = sum(
        (
            customer.lifetime_value
            for customer in CUSTOMERS
        ),
        Decimal("0.00"),
    )

    high_risk_customers = sum(
        1
        for customer in CUSTOMERS
        if customer.risk_level == "HIGH"
    )

    medium_risk_customers = sum(
        1
        for customer in CUSTOMERS
        if customer.risk_level == "MEDIUM"
    )

    low_risk_customers = sum(
        1
        for customer in CUSTOMERS
        if customer.risk_level == "LOW"
    )

    print()
    print(
        "CUSTOMER STATE"
    )
    print("-" * 60)

    print(
        f"Low risk customers       : "
        f"{low_risk_customers}"
    )

    print(
        f"Medium risk customers    : "
        f"{medium_risk_customers}"
    )

    print(
        f"High risk customers      : "
        f"{high_risk_customers}"
    )

    print(
        f"Simulated lifetime value: "
        f"{total_lifetime_value:.2f}"
    )

    print()


# ============================================================
# REAL-TIME STREAM
# ============================================================

def run_generator(
    interval_min: float = 0.5,
    interval_max: float = 3.0,
    customer_count: int = 250,
) -> None:

    initialize_pool()

    conn = get_connection()

    create_customer_pool(
        customer_count
    )

    generated = 0
    posted = 0
    rejected = 0
    anomalies = 0
    high_risk = 0

    print()
    print("=" * 115)

    print(
        "LEDGERGUARD ADVANCED "
        "BEHAVIORAL TRANSACTION ENGINE"
    )

    print("=" * 115)

    print(
        f"Customers loaded : "
        f"{customer_count}"
    )

    print(
        "Mode             : "
        "REAL-TIME SYNTHETIC STREAM"
    )

    print(
        "Behavior         : "
        "STATEFUL CUSTOMER SIMULATION"
    )

    print(
        "Risk engine      : "
        "ENABLED"
    )

    print(
        "Anomaly engine   : "
        "ENABLED"
    )

    print(
        "Press CTRL+C to stop."
    )

    print("=" * 115)
    print()

    try:

        while True:

            event = generate_event()

            generated += 1

            if event.risk_level == "HIGH":

                high_risk += 1

            if event.anomaly_score >= 0.70:

                anomalies += 1

            try:

                transaction_id = (
                    process_event(
                        conn,
                        event,
                    )
                )

                if transaction_id:

                    posted += 1

                else:

                    # A FAILED / DECLINED event
                    # was successfully recorded,
                    # but it was not posted to the
                    # financial ledger.
                    rejected += 1

            except Exception as exc:

                conn.rollback()

                rejected += 1

                print(
                    f"    └── ERROR: "
                    f"{exc}"
                )

            print(
                f"    COUNTERS | "
                f"generated={generated} | "
                f"posted={posted} | "
                f"rejected={rejected} | "
                f"high-risk={high_risk} | "
                f"anomalies={anomalies}"
            )

            print()

            # Variable timing creates a more realistic
            # transaction stream.

            time.sleep(
                random.uniform(
                    interval_min,
                    interval_max,
                )
            )

    except KeyboardInterrupt:

        print()
        print("=" * 115)

        print(
            "SIMULATION STOPPED"
        )

        print("=" * 115)

        print(
            f"Generated events : "
            f"{generated}"
        )

        print(
            f"Posted events    : "
            f"{posted}"
        )

        print(
            f"Rejected events  : "
            f"{rejected}"
        )

        print(
            f"High-risk events : "
            f"{high_risk}"
        )

        print(
            f"Anomalies        : "
            f"{anomalies}"
        )

        print("=" * 115)

        print_customer_statistics()

    finally:

        release_connection(conn)

        close_pool()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    run_generator()