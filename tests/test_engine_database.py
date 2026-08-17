import contextlib
import io

from src.database import (
    initialize_pool,
    get_connection,
    release_connection,
    close_pool,
)

from src.generator import (
    create_customer_pool,
    generate_event,
    process_event,
)


def main():
    initialize_pool()
    conn = get_connection()

    try:
        # ---------------------------------------------------------
        # 1. Generate synthetic customers and events
        # ---------------------------------------------------------

        create_customer_pool(100)

        events = [
            generate_event()
            for _ in range(100)
        ]

        generated = len(events)

        expected_anomalies = sum(
            event.anomaly_score >= 0.70
            for event in events
        )

        expected_declined = sum(
            event.status == "DECLINED"
            for event in events
        )

        expected_failed = sum(
            event.status == "FAILED"
            for event in events
        )

        expected_success = sum(
            event.status == "SUCCESS"
            for event in events
        )

        # ---------------------------------------------------------
        # 2. Process every event
        # ---------------------------------------------------------

        posted = 0
        not_posted = 0

        # Suppress normal event-by-event logging.
        with contextlib.redirect_stdout(io.StringIO()):

            for event in events:

                result = process_event(
                    conn,
                    event,
                )

                if result:
                    posted += 1
                else:
                    not_posted += 1

        # ---------------------------------------------------------
        # 3. Query PostgreSQL
        # ---------------------------------------------------------

        cur = conn.cursor()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM public.transactions
            """
        )

        database_transactions = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*)
            FROM public.transactions
            WHERE anomaly_score >= 0.70
            """
        )

        database_anomalies = cur.fetchone()[0]

        cur.execute(
            """
            SELECT status, COUNT(*)
            FROM public.transactions
            GROUP BY status
            ORDER BY status
            """
        )

        database_statuses = cur.fetchall()

        cur.execute(
            """
            SELECT
                COUNT(*),
                COALESCE(
                    SUM(
                        CASE
                            WHEN direction = 'DEBIT'
                            THEN amount
                            ELSE 0
                        END
                    ),
                    0
                ),
                COALESCE(
                    SUM(
                        CASE
                            WHEN direction = 'CREDIT'
                            THEN amount
                            ELSE 0
                        END
                    ),
                    0
                )
            FROM public.entries
            """

        )

        entry_count, total_debits, total_credits = cur.fetchone()

        cur.close()

        # ---------------------------------------------------------
        # 4. Display results
        # ---------------------------------------------------------

        print()
        print("=" * 60)
        print("LEDGERGUARD DATABASE ENGINE TEST")
        print("=" * 60)

        print(f"Generated events:       {generated}")
        print(f"Expected SUCCESS:       {expected_success}")
        print(f"Expected DECLINED:      {expected_declined}")
        print(f"Expected FAILED:        {expected_failed}")
        print(f"Expected anomalies:     {expected_anomalies}")

        print("-" * 60)

        print(f"Posted events:           {posted}")
        print(f"Not posted events:       {not_posted}")

        print("-" * 60)

        print(f"Database transactions:   {database_transactions}")
        print(f"Database anomalies:      {database_anomalies}")
        print(f"Database statuses:       {database_statuses}")

        print("-" * 60)

        print(f"Ledger entries:          {entry_count}")
        print(f"Total debits:            {total_debits}")
        print(f"Total credits:           {total_credits}")

        print("-" * 60)

        # ---------------------------------------------------------
        # 5. Basic integrity checks
        # ---------------------------------------------------------

        expected_not_posted = expected_declined + expected_failed

        checks_passed = True

        if posted != expected_success:
            print(
                f"WARNING: Expected {expected_success} posted events "
                f"but got {posted}."
            )
            checks_passed = False

        if not_posted != expected_not_posted:
            print(
                f"WARNING: Expected {expected_not_posted} "
                f"non-posted events but got {not_posted}."
            )
            checks_passed = False

        if total_debits != total_credits:
            print(
                "WARNING: Ledger is NOT balanced."
            )
            checks_passed = False

        if checks_passed:
            print("INTEGRATION TEST: PASS")
        else:
            print("INTEGRATION TEST: REVIEW REQUIRED")

        print("=" * 60)

    finally:
        release_connection(conn)
        close_pool()


if __name__ == "__main__":
    main()