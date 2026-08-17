import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import initialize_pool, connection_context, close_pool


TRANSACTION_ID = "3916d16d-fea2-4d7d-b406-030408547e7d"


def main():
    initialize_pool()

    try:
        with connection_context() as conn:

            # --------------------------------------------------
            # TEST 1: Attempt to modify a transaction
            # --------------------------------------------------
            print("\nTEST 1: Attempt transaction modification")

            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE transactions
                        SET description = 'TAMPERED TRANSACTION'
                        WHERE id = %s;
                        """,
                        (TRANSACTION_ID,),
                    )

                conn.commit()

                print("❌ FAIL: Transaction was modified.")

            except Exception as exc:
                conn.rollback()

                print("✅ PASS: Transaction modification rejected.")
                print(f"   Reason: {exc}")

            # --------------------------------------------------
            # TEST 2: Attempt to delete a transaction
            # --------------------------------------------------
            print("\nTEST 2: Attempt transaction deletion")

            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        DELETE FROM transactions
                        WHERE id = %s;
                        """,
                        (TRANSACTION_ID,),
                    )

                conn.commit()

                print("❌ FAIL: Transaction was deleted.")

            except Exception as exc:
                conn.rollback()

                print("✅ PASS: Transaction deletion rejected.")
                print(f"   Reason: {exc}")

    finally:
        close_pool()


if __name__ == "__main__":
    main()