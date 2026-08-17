from decimal import Decimal

from src.database import (
    close_pool,
    get_connection,
    initialize_pool,
    release_connection,
)
from src.ledger import LedgerError, post_transaction
from src.models import EntryDirection, LedgerEntry


def get_account_id(conn, account_name):

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
                f"Account not found: {account_name}"
            )

        return str(result[0])


def test_unbalanced_transaction(conn, accounts):

    print()
    print("TEST 1: Reject unbalanced transaction")

    entries = [
        LedgerEntry(
            account_id=accounts["cash"],
            amount=Decimal("100.00"),
            direction=EntryDirection.DEBIT,
        ),
        LedgerEntry(
            account_id=accounts["revenue"],
            amount=Decimal("90.00"),
            direction=EntryDirection.CREDIT,
        ),
    ]

    try:

        post_transaction(
            conn,
            description="Security test - unbalanced",
            reference_id="SECURITY-UNBALANCED-001",
            idempotency_key="security-unbalanced-001",
            entries=entries,
        )

        print("❌ FAIL: Unbalanced transaction was accepted.")

    except Exception as exc:

        print("✅ PASS: Transaction rejected.")
        print(f"   Reason: {exc}")


def test_idempotency(conn, accounts):

    print()
    print("TEST 2: Idempotency protection")

    entries = [
        LedgerEntry(
            account_id=accounts["cash"],
            amount=Decimal("250.00"),
            direction=EntryDirection.DEBIT,
        ),
        LedgerEntry(
            account_id=accounts["revenue"],
            amount=Decimal("250.00"),
            direction=EntryDirection.CREDIT,
        ),
    ]

    idempotency_key = "security-idempotency-002"

    first_id = post_transaction(
        conn,
        description="Security idempotency test",
        reference_id="SECURITY-IDEMPOTENCY-002",
        idempotency_key=idempotency_key,
        entries=entries,
    )

    second_id = post_transaction(
        conn,
        description="Security idempotency test",
        reference_id="SECURITY-IDEMPOTENCY-002",
        idempotency_key=idempotency_key,
        entries=entries,
    )

    if first_id == second_id:

        print(
            "✅ PASS: Duplicate request returned "
            "the original transaction."
        )

        print(
            f"   Transaction ID: {first_id}"
        )

    else:

        print(
            "❌ FAIL: Duplicate request created "
            "a different transaction."
        )


def test_idempotency_tampering(conn, accounts):

    print()
    print(
        "TEST 3: Idempotency tampering protection"
    )

    entries_original = [
        LedgerEntry(
            account_id=accounts["cash"],
            amount=Decimal("300.00"),
            direction=EntryDirection.DEBIT,
        ),
        LedgerEntry(
            account_id=accounts["revenue"],
            amount=Decimal("300.00"),
            direction=EntryDirection.CREDIT,
        ),
    ]

    entries_modified = [
        LedgerEntry(
            account_id=accounts["cash"],
            amount=Decimal("9999.00"),
            direction=EntryDirection.DEBIT,
        ),
        LedgerEntry(
            account_id=accounts["revenue"],
            amount=Decimal("9999.00"),
            direction=EntryDirection.CREDIT,
        ),
    ]

    key = "security-tampering-001"

    post_transaction(
        conn,
        description="Original security transaction",
        reference_id="SECURITY-TAMPER-001",
        idempotency_key=key,
        entries=entries_original,
    )

    try:

        post_transaction(
            conn,
            description="Modified security transaction",
            reference_id="SECURITY-TAMPER-002",
            idempotency_key=key,
            entries=entries_modified,
        )

        print(
            "❌ FAIL: Modified transaction was accepted."
        )

    except LedgerError as exc:

        print(
            "✅ PASS: Modified transaction rejected."
        )

        print(
            f"   Reason: {exc}"
        )


def main():

    initialize_pool()

    conn = get_connection()

    try:

        accounts = {
            "cash": get_account_id(
                conn,
                "1000 - Operating Cash",
            ),
            "revenue": get_account_id(
                conn,
                "4000 - Flight Booking Revenue",
            ),
        }

        test_unbalanced_transaction(
            conn,
            accounts,
        )

        test_idempotency(
            conn,
            accounts,
        )

        test_idempotency_tampering(
            conn,
            accounts,
        )

    finally:

        release_connection(conn)
        close_pool()


if __name__ == "__main__":
    main()