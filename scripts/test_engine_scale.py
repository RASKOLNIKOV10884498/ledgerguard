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


TEST_EVENTS = 1000


def main():

    initialize_pool()

    conn = get_connection()

    create_customer_pool(1000)

    generated = 0
    posted = 0
    not_posted = 0
    anomalies = 0

    try:

        for _ in range(TEST_EVENTS):

            event = generate_event()

            generated += 1

            if event.anomaly_score >= 0.70:
                anomalies += 1

            result = process_event(conn, event)

            if result:
                posted += 1
            else:
                not_posted += 1

        print()
        print("=" * 60)
        print("LEDGERGUARD ENGINE SCALE TEST")
        print("=" * 60)
        print(f"Generated:       {generated}")
        print(f"Posted:           {posted}")
        print(f"Not posted:      {not_posted}")
        print(f"Anomalies >= .70:{anomalies}")
        print("=" * 60)

    finally:

        release_connection(conn)
        close_pool()


if __name__ == "__main__":
    main()
