import random
import time
from datetime import datetime, timezone

from src.generator import (
    create_customer_pool,
    generate_event,
    process_event,
)
from src.database import (
    initialize_pool,
    get_connection,
    release_connection,
    close_pool,
)


# ============================================================
# LEDGERGUARD VARIABLE-RATE SIMULATOR
# ============================================================

CUSTOMER_POOL_SIZE = 1000

# Average transaction rates
QUIET_RATE = 0.3
NORMAL_RATE = 1.0
BUSY_RATE = 2.5
PEAK_RATE = 4.0

# Probability of entering a temporary peak/anomaly spike
SPIKE_PROBABILITY = 0.03

# How long a traffic regime lasts before recalculating
MIN_REGIME_SECONDS = 30
MAX_REGIME_SECONDS = 90


def choose_traffic_regime():
    """
    Choose the next traffic regime.

    Normal traffic is most common.
    Quiet and busy periods occur occasionally.
    Peak periods are less common.
    """

    regimes = [
        ("QUIET", QUIET_RATE, 0.15),
        ("NORMAL", NORMAL_RATE, 0.60),
        ("BUSY", BUSY_RATE, 0.20),
        ("PEAK", PEAK_RATE, 0.05),
    ]

    names = [r[0] for r in regimes]
    rates = [r[1] for r in regimes]
    weights = [r[2] for r in regimes]

    index = random.choices(
        range(len(regimes)),
        weights=weights,
        k=1,
    )[0]

    return names[index], rates[index]


def sleep_for_rate(rate):
    """
    Convert transactions/second into a delay.

    Example:
        1 transaction/sec  -> ~1 second
        4 transactions/sec -> ~0.25 seconds
    """

    if rate <= 0:
        return 1.0

    delay = 1.0 / rate

    # Add a small amount of randomness so the stream
    # doesn't look artificially perfectly timed.
    jitter = random.uniform(0.80, 1.20)

    return delay * jitter


def print_event_summary(event, result):
    """
    Print a compact simulator log.
    """

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

    anomaly = ""

    if event.anomaly_score > 0:
        anomaly = (
            f" | ANOMALY={event.anomaly_score:.2f}"
            f" | {event.anomaly_reason}"
        )

    if result:
        outcome = "POSTED"
    else:
        outcome = "NOT POSTED"

    print(
        f"[{timestamp}] "
        f"{event.event_type:<20} "
        f"{event.status:<8} "
        f"{event.currency:<3} "
        f"{str(event.amount):>10} "
        f"{event.payment_method:<15} "
        f"RISK={event.risk_level:<6} "
        f"{outcome}"
        f"{anomaly}"
    )


def run_simulator():
    """
    Run LedgerGuard continuously.

    The simulator automatically moves between:
        QUIET
        NORMAL
        BUSY
        PEAK

    It also occasionally creates a short traffic spike.
    """

    print()
    print("=" * 70)
    print("LEDGERGUARD VARIABLE-RATE TRANSACTION SIMULATOR")
    print("=" * 70)
    print("Press Ctrl+C to stop.")
    print()

    create_customer_pool(CUSTOMER_POOL_SIZE)
    initialize_pool()

    conn = get_connection()

    total_events = 0
    total_posted = 0
    total_not_posted = 0
    total_anomalies = 0

    current_regime = None
    current_rate = NORMAL_RATE
    regime_end_time = 0

    try:
        while True:

            # ------------------------------------------------
            # Choose a new traffic regime when the current one
            # expires.
            # ------------------------------------------------
            now = time.time()

            if now >= regime_end_time:

                current_regime, current_rate = choose_traffic_regime()

                duration = random.uniform(
                    MIN_REGIME_SECONDS,
                    MAX_REGIME_SECONDS,
                )

                regime_end_time = now + duration

                print()
                print(
                    f">>> TRAFFIC MODE: {current_regime} "
                    f"| ~{current_rate:.1f} transactions/sec "
                    f"| for ~{duration:.0f}s"
                )
                print()

            # ------------------------------------------------
            # Occasionally create a short traffic spike.
            # ------------------------------------------------
            actual_rate = current_rate

            if random.random() < SPIKE_PROBABILITY:

                spike_rate = random.uniform(3.0, 5.0)
                spike_duration = random.uniform(5.0, 12.0)

                print()
                print(
                    f">>> ⚠ TRAFFIC SPIKE: "
                    f"{spike_rate:.1f} transactions/sec "
                    f"for ~{spike_duration:.0f}s"
                )
                print()

                spike_end = time.time() + spike_duration

                while time.time() < spike_end:

                    event = generate_event()

                    total_events += 1

                    if event.anomaly_score > 0:
                        total_anomalies += 1

                    result = process_event(conn, event)

                    if result:
                        total_posted += 1
                    else:
                        total_not_posted += 1

                    print_event_summary(event, result)

                    time.sleep(sleep_for_rate(spike_rate))

                continue

            # ------------------------------------------------
            # Generate normal traffic.
            # ------------------------------------------------
            event = generate_event()

            total_events += 1

            if event.anomaly_score > 0:
                total_anomalies += 1

            result = process_event(conn, event)

            if result:
                total_posted += 1
            else:
                total_not_posted += 1

            print_event_summary(event, result)

            # ------------------------------------------------
            # Wait according to current traffic rate.
            # ------------------------------------------------
            time.sleep(sleep_for_rate(actual_rate))

    except KeyboardInterrupt:

        print()
        print()
        print("=" * 70)
        print("SIMULATOR STOPPED")
        print("=" * 70)
        print(f"Total events:     {total_events}")
        print(f"Posted:           {total_posted}")
        print(f"Not posted:       {total_not_posted}")
        print(f"Anomalies:        {total_anomalies}")
        print("=" * 70)

    finally:
        release_connection(conn)
        close_pool()


if __name__ == "__main__":
    run_simulator()