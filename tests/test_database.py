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

        # Create a realistic customer population
        create_customer_pool(1000)

        # Generate 1,000 synthetic events
        events = [
            generate_event()
            for _ in range(1000)
        ]

        # Calculate what we expect to see
        expected_anomalies = sum(
            event.anomaly_score >= 0.70
            for event in events
        )

        expected_failed = sum(
            event.status != "SUCCESS"
            for event in events
        )

        posted = 0
        not_posted = 0

        # Send every event through the real LedgerGuard engine
        for event in events:

            result = process_event(
                conn,
                event,
            )

            if result:
                posted += 1
            else:
                not_posted += 1

        # ----------------------------------------------------
        # Query PostgreSQL
        # ----------------------------------------------------

        cur = conn.cursor()

        cur.execute(
            "SELECT COUNT(*) FROM public.transactions"
        )

        total = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*)
            FROM public.transactions
            WHERE anomaly_score >= 0.70
            """
        )

        db_anomalies = cur.fetchone()[0]

        cur.execute(
            """
            SELECT status, COUNT(*)
            FROM public.transactions
            GROUP BY status
            ORDER BY status
            """
        )

        statuses = cur.fetchall()

        cur.close()

        # ----------------------------------------------------
        # Results
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("LEDGERGUARD DATABASE ENGINE TEST")
        print("=" * 70)

        print(
            f"Generated events:         {len(events)}"
        )

        print(
            f"Expected anomalies:       {expected_anomalies}"
        )

        print(
            f"Expected failed/declined: {expected_failed}"
        )

        print(
            f"Posted during test:       {posted}"
        )

        print(
            f"Not posted during test:   {not_posted}"
        )

        print("-" * 70)

        print(
            f"Database transactions:    {total}"
        )

        print(
            f"Database anomalies:       {db_anomalies}"
        )

        print(
            f"Database statuses:        {statuses}"
        )

        print("=" * 70)

    finally:

        release_connection(conn)
        close_pool()


if __name__ == "__main__":
    main()