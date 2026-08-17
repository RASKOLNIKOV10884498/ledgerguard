from decimal import Decimal

from src.database import (
    close_pool,
    get_connection,
    initialize_pool,
    release_connection,
)

from src.ledger import post_transaction
from src.models import EntryDirection, LedgerEntry


def get_account_id(conn, account_name: str) -> str:

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


def main():

    initialize_pool()

    conn = get_connection()

    try:

        cash_account = get_account_id(
            conn,
            "1000 - Operating Cash",
        )

        revenue_account = get_account_id(
            conn,
            "4000 - Flight Booking Revenue",
        )

        transaction_id = post_transaction(
            conn,
            description="LedgerGuard test flight booking",
            reference_id="TEST-002",
            idempotency_key="ledgerguard-test-002",
            entries=[
                LedgerEntry(
                    account_id=cash_account,
                    amount=Decimal("500.00"),
                    direction=EntryDirection.DEBIT,
                ),
                LedgerEntry(
                    account_id=revenue_account,
                    amount=Decimal("500.00"),
                    direction=EntryDirection.CREDIT,
                ),
            ],
        )

        print(
            f"Transaction posted successfully: "
            f"{transaction_id}"
        )

    finally:

        release_connection(conn)
        close_pool()


if __name__ == "__main__":
    main()