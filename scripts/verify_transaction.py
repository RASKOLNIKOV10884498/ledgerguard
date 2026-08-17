import sys

from src.database import (
    close_pool,
    get_connection,
    initialize_pool,
    release_connection,
)


def main():
    if len(sys.argv) != 2:
        print("Usage:")
        print(
            "python -m scripts.verify_transaction "
            "<transaction_id>"
        )
        return

    transaction_id = sys.argv[1]

    initialize_pool()
    conn = get_connection()

    try:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    t.id,
                    t.description,
                    t.reference_id,
                    t.idempotency_key,
                    t.request_hash,
                    t.status,
                    t.created_at
                FROM public.transactions t
                WHERE t.id = %s
                """,
                (transaction_id,),
            )

            transaction = cursor.fetchone()

            if transaction is None:
                print("Transaction not found.")
                return

            (
                tx_id,
                description,
                reference_id,
                idempotency_key,
                request_hash,
                status,
                created_at,
            ) = transaction

            cursor.execute(
                """
                SELECT
                    a.name,
                    e.amount,
                    e.direction
                FROM public.entries e
                JOIN public.accounts a
                    ON a.id = e.account_id
                WHERE e.transaction_id = %s
                ORDER BY e.created_at
                """,
                (transaction_id,),
            )

            entries = cursor.fetchall()

            print()
            print("TRANSACTION VERIFIED")
            print("=" * 60)
            print(f"Transaction ID : {tx_id}")
            print(f"Description    : {description}")
            print(f"Reference ID   : {reference_id}")
            print(f"Idempotency    : {idempotency_key}")
            print(f"Request Hash   : {request_hash}")
            print(f"Status         : {status}")
            print(f"Created At     : {created_at}")

            print()
            print("LEDGER ENTRIES")
            print("-" * 60)

            total_debits = 0
            total_credits = 0

            for account_name, amount, direction in entries:

                print(
                    f"{direction:<7}"
                    f"{account_name:<35}"
                    f"{amount:>12.4f}"
                )

                if direction == "DEBIT":
                    total_debits += amount
                else:
                    total_credits += amount

            print("-" * 60)
            print(
                f"Total Debits  : {total_debits:.4f}"
            )
            print(
                f"Total Credits : {total_credits:.4f}"
            )

            print("=" * 60)

            if total_debits == total_credits:
                print("BALANCE CHECK: PASS")
            else:
                print("BALANCE CHECK: FAIL")

            print()

    finally:
        release_connection(conn)
        close_pool()


if __name__ == "__main__":
    main()