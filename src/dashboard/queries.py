from dash import html
import plotly.graph_objects as go

from database import connection_context


# ============================================================
# DASHBOARD METRICS
# ============================================================

def get_dashboard_metrics():
    """
    Return the main KPI values for the dashboard.
    """

    with connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total_transactions,

                    COUNT(*) FILTER (
                        WHERE status IN ('POSTED', 'SUCCESS')
                    ) AS posted_transactions,

                    COUNT(*) FILTER (
                        WHERE status IN ('FAILED', 'DECLINED')
                    ) AS failed_transactions,

                    COUNT(*) FILTER (
                        WHERE COALESCE(anomaly_score, 0) >= 0.70
                    ) AS anomalies

                FROM transactions;
                """
            )

            row = cur.fetchone()

    return {
        "total_transactions": row[0] or 0,
        "posted_transactions": row[1] or 0,
        "failed_transactions": row[2] or 0,
        "anomalies": row[3] or 0,
    }


# ============================================================
# TRANSACTION ACTIVITY
# ============================================================

def get_transaction_activity():
    """
    Build the transaction activity chart.

    Instead of looking only at the last 30 minutes,
    this uses the latest 30 minutes of transaction data.

    If the database contains no transactions in that window,
    it falls back to the latest transaction history so the
    dashboard never appears completely blank.
    """

    with connection_context() as conn:
        with conn.cursor() as cur:

            # ------------------------------------------------
            # First check the newest transaction timestamp
            # ------------------------------------------------

            cur.execute(
                """
                SELECT MAX(occurred_at)
                FROM transactions;
                """
            )

            latest_row = cur.fetchone()
            latest_transaction = latest_row[0] if latest_row else None

            # ------------------------------------------------
            # No transactions at all
            # ------------------------------------------------

            if latest_transaction is None:
                return _empty_activity_figure()

            # ------------------------------------------------
            # Build activity around the newest transaction.
            #
            # This is important because your simulator data
            # may not have occurred in the real current time.
            # ------------------------------------------------

            cur.execute(
                """
                WITH time_window AS (
                    SELECT
                        date_trunc(
                            'minute',
                            MAX(occurred_at)
                        ) - INTERVAL '29 minutes' AS start_time,

                        date_trunc(
                            'minute',
                            MAX(occurred_at)
                        ) AS end_time

                    FROM transactions
                ),

                minutes AS (
                    SELECT
                        generate_series(
                            start_time,
                            end_time,
                            INTERVAL '1 minute'
                        ) AS minute
                    FROM time_window
                ),

                activity AS (
                    SELECT
                        date_trunc(
                            'minute',
                            occurred_at
                        ) AS minute,

                        COUNT(*) AS transaction_count

                    FROM transactions

                    WHERE occurred_at >= (
                        SELECT start_time
                        FROM time_window
                    )

                    GROUP BY 1
                )

                SELECT
                    minutes.minute,
                    COALESCE(
                        activity.transaction_count,
                        0
                    ) AS transaction_count

                FROM minutes

                LEFT JOIN activity
                    ON activity.minute = minutes.minute

                ORDER BY minutes.minute;
                """
            )

            rows = cur.fetchall()

    x = [row[0] for row in rows]
    y = [row[1] for row in rows]

    if not x:
        return _empty_activity_figure()

    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            name="Transactions",
            line={
                "width": 3,
            },
            marker={
                "size": 6,
            },
            fill="tozeroy",
            hovertemplate=(
                "%{x|%H:%M}"
                "<br>Transactions: %{y}"
                "<extra></extra>"
            ),
        )
    )

    figure.update_layout(
        height=340,

        margin={
            "l": 55,
            "r": 20,
            "t": 20,
            "b": 50,
        },

        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",

        font={
            "color": "#94a3b8",
        },

        hovermode="x unified",

        showlegend=False,

        xaxis={
            "title": "Time",
            "showgrid": False,
            "zeroline": False,
        },

        yaxis={
            "title": "Transactions",
            "showgrid": True,
            "gridcolor": "rgba(148,163,184,0.12)",
            "zeroline": False,
            "rangemode": "tozero",
        },
    )

    return figure


def _empty_activity_figure():
    """
    Return a valid empty chart instead of crashing
    when the database contains no transaction history.
    """

    figure = go.Figure()

    figure.add_annotation(
        text="No transaction activity available",
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={
            "size": 14,
            "color": "#64748b",
        },
    )

    figure.update_layout(
        height=340,

        margin={
            "l": 20,
            "r": 20,
            "t": 20,
            "b": 20,
        },

        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,

        xaxis={
            "visible": False,
        },

        yaxis={
            "visible": False,
        },
    )

    return figure


# ============================================================
# RISK DISTRIBUTION
# ============================================================

def get_risk_distribution():
    """
    Return the distribution of transaction risk levels.

    Missing risk levels are shown as UNKNOWN so the dashboard
    accurately reflects the database instead of inventing data.
    """

    with connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(
                        NULLIF(TRIM(risk_level), ''),
                        'UNKNOWN'
                    ) AS risk_level,

                    COUNT(*) AS transaction_count

                FROM transactions

                GROUP BY
                    COALESCE(
                        NULLIF(TRIM(risk_level), ''),
                        'UNKNOWN'
                    )

                ORDER BY transaction_count DESC;
                """
            )

            rows = cur.fetchall()

    if not rows:
        return _empty_risk_figure()

    labels = [
        str(row[0])
        for row in rows
    ]

    values = [
        int(row[1])
        for row in rows
    ]

    figure = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,

                hole=0.58,

                textinfo="label+percent",

                hovertemplate=(
                    "<b>%{label}</b>"
                    "<br>Transactions: %{value}"
                    "<br>Share: %{percent}"
                    "<extra></extra>"
                ),
            )
        ]
    )

    figure.update_layout(
        height=340,

        margin={
            "l": 20,
            "r": 20,
            "t": 20,
            "b": 55,
        },

        paper_bgcolor="rgba(0,0,0,0)",

        font={
            "color": "#94a3b8",
        },

        showlegend=True,

        legend={
            "orientation": "h",
            "y": -0.08,
        },
    )

    return figure


def _empty_risk_figure():
    """
    Return an empty risk chart.
    """

    figure = go.Figure()

    figure.add_annotation(
        text="No risk data available",
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={
            "size": 14,
            "color": "#64748b",
        },
    )

    figure.update_layout(
        height=340,

        margin={
            "l": 20,
            "r": 20,
            "t": 20,
            "b": 20,
        },

        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,

        xaxis={
            "visible": False,
        },

        yaxis={
            "visible": False,
        },
    )

    return figure


# ============================================================
# RECENT ANOMALIES
# ============================================================

def get_recent_anomalies():
    """
    Return the most recent high-risk transactions.

    Anomaly threshold:
        anomaly_score >= 0.70
    """

    with connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    event_type,
                    amount,
                    currency,
                    anomaly_score,
                    anomaly_reason,
                    occurred_at

                FROM transactions

                WHERE COALESCE(anomaly_score, 0) >= 0.70

                ORDER BY occurred_at DESC

                LIMIT 8;
                """
            )

            rows = cur.fetchall()

    if not rows:
        return html.Div(
            children=[
                html.Div(
                    "No recent anomalies detected.",
                    className="no-anomalies",
                ),

                html.Div(
                    "The monitoring engine has not detected "
                    "any transactions with a risk score >= 0.70.",
                    className="no-anomalies",
                ),
            ]
        )

    items = []

    for (
        event_type,
        amount,
        currency,
        score,
        reason,
        occurred_at,
    ) in rows:

        score_value = (
            float(score)
            if score is not None
            else 0.0
        )

        amount_value = (
            float(amount)
            if amount is not None
            else 0.0
        )

        time_value = ""

        if occurred_at:
            time_value = occurred_at.strftime(
                "%H:%M:%S"
            )

        items.append(
            html.Div(
                className="anomaly-item",

                children=[

                    html.Div(
                        className="anomaly-score",
                        children=f"{score_value:.2f}",
                    ),

                    html.Div(
                        className="anomaly-content",

                        children=[

                            html.Div(
                                event_type or "Unknown event",
                                className="anomaly-event",
                            ),

                            html.Div(
                                reason or "Anomaly detected",
                                className="anomaly-reason",
                            ),

                            html.Div(
                                f"{currency or ''} "
                                f"{amount_value:,.2f}",
                                className="anomaly-amount",
                            ),

                            html.Div(
                                time_value,
                                className="anomaly-time",
                            ),

                        ],
                    ),
                ],
            )
        )

    return items