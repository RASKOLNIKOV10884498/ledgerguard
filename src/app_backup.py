import os
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px

from dash import Dash, dcc, html, Input, Output
from sqlalchemy import create_engine, text


# ============================================================
# DATABASE
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. "
        "Export your Supabase/PostgreSQL connection string first."
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


# ============================================================
# DASH APP
# ============================================================

app = Dash(
    __name__,
    title="LedgerGuard",
)

server = app.server


# ============================================================
# STYLES
# ============================================================

PAGE_STYLE = {
    "fontFamily": "Arial, sans-serif",
    "backgroundColor": "#f4f6f8",
    "minHeight": "100vh",
    "padding": "24px",
}

CARD_STYLE = {
    "backgroundColor": "#ffffff",
    "borderRadius": "10px",
    "padding": "18px",
    "boxShadow": "0 2px 8px rgba(0,0,0,0.08)",
}

STAT_LABEL_STYLE = {
    "fontSize": "14px",
    "color": "#666",
}

STAT_VALUE_STYLE = {
    "fontSize": "32px",
    "fontWeight": "700",
    "marginTop": "8px",
    "fontVariantNumeric": "tabular-nums",
}


# ============================================================
# KPI CARD
# ============================================================

def create_kpi_card(title, component_id, initial_value="0"):
    return html.Div(
        [
            html.Div(
                title,
                style=STAT_LABEL_STYLE,
            ),

            html.Div(
                initial_value,
                id=component_id,
                style=STAT_VALUE_STYLE,
            ),
        ],
        style=CARD_STYLE,
    )


# ============================================================
# LAYOUT
# ============================================================

app.layout = html.Div(
    style=PAGE_STYLE,
    children=[

        # ====================================================
        # HEADER
        # ====================================================

        html.Div(
            [
                html.H1(
                    "LedgerGuard",
                    style={
                        "margin": "0",
                        "fontSize": "32px",
                    },
                ),

                html.P(
                    "Real-time transaction monitoring & anomaly detection",
                    style={
                        "marginTop": "6px",
                        "color": "#666",
                    },
                ),

                html.Div(
                    id="last-updated",
                    children="Waiting for data...",
                    style={
                        "fontSize": "13px",
                        "color": "#888",
                    },
                ),
            ],
            style={
                "marginBottom": "24px",
            },
        ),

        # ====================================================
        # KPI SECTION
        #
        # THIS SECTION REFRESHES EVERY 1 SECOND
        # ====================================================

        html.Div(
            [
                create_kpi_card(
                    "Transactions",
                    "kpi-transactions",
                ),

                create_kpi_card(
                    "Posted",
                    "kpi-posted",
                ),

                create_kpi_card(
                    "Failed / Declined",
                    "kpi-failed",
                ),

                create_kpi_card(
                    "Anomalies",
                    "kpi-anomalies",
                ),

                create_kpi_card(
                    "Transactions / sec",
                    "kpi-rate",
                    "0.00",
                ),
            ],
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(5, 1fr)",
                "gap": "16px",
                "marginBottom": "24px",
            },
        ),

        # ====================================================
        # CHART ROW 1
        #
        # REFRESHES EVERY 5 SECONDS
        # ====================================================

        html.Div(
            [
                html.Div(
                    [
                        html.H3("Transaction Volume"),

                        dcc.Graph(
                            id="transaction-volume-chart",
                            config={
                                "displayModeBar": False,
                            },
                        ),
                    ],
                    style=CARD_STYLE,
                ),

                html.Div(
                    [
                        html.H3("Risk Distribution"),

                        dcc.Graph(
                            id="risk-chart",
                            config={
                                "displayModeBar": False,
                            },
                        ),
                    ],
                    style=CARD_STYLE,
                ),
            ],
            style={
                "display": "grid",
                "gridTemplateColumns": "2fr 1fr",
                "gap": "16px",
                "marginBottom": "24px",
            },
        ),

        # ====================================================
        # CHART ROW 2
        # ====================================================

        html.Div(
            [
                html.Div(
                    [
                        html.H3("Payment Methods"),

                        dcc.Graph(
                            id="payment-method-chart",
                            config={
                                "displayModeBar": False,
                            },
                        ),
                    ],
                    style=CARD_STYLE,
                ),

                html.Div(
                    [
                        html.H3("Transaction Status"),

                        dcc.Graph(
                            id="status-chart",
                            config={
                                "displayModeBar": False,
                            },
                        ),
                    ],
                    style=CARD_STYLE,
                ),
            ],
            style={
                "display": "grid",
                "gridTemplateColumns": "1fr 1fr",
                "gap": "16px",
                "marginBottom": "24px",
            },
        ),

        # ====================================================
        # RECENT TRANSACTIONS
        # ====================================================

        html.Div(
            [
                html.H3("Recent Transactions"),

                html.Div(
                    id="recent-transactions",
                    style={
                        "overflowX": "auto",
                    },
                ),
            ],
            style=CARD_STYLE,
        ),

        # ====================================================
        # KPI REFRESH
        #
        # EVERY 1 SECOND
        # ====================================================

        dcc.Interval(
            id="kpi-interval",
            interval=1000,
            n_intervals=0,
        ),

        # ====================================================
        # ANALYTICS REFRESH
        #
        # EVERY 5 SECONDS
        # ====================================================

        dcc.Interval(
            id="analytics-interval",
            interval=5000,
            n_intervals=0,
        ),
    ],
)


# ============================================================
# KPI QUERY
#
# Lightweight query specifically for the live KPI cards.
# ============================================================

def load_kpis():

    query = text(
        """
        SELECT
            COUNT(*) AS total_transactions,

            COUNT(*) FILTER (
                WHERE UPPER(status) = 'SUCCESS'
            ) AS posted,

            COUNT(*) FILTER (
                WHERE UPPER(status) IN ('FAILED', 'DECLINED')
            ) AS failed,

            COUNT(*) FILTER (
                WHERE COALESCE(anomaly_score, 0) > 0.5
            ) AS anomalies,

            COUNT(*) FILTER (
                WHERE occurred_at >= NOW() - INTERVAL '60 seconds'
            ) AS recent_transactions

        FROM transactions
        """
    )

    with engine.connect() as conn:

        result = conn.execute(query).mappings().first()

    return {
        "total": result["total_transactions"] or 0,
        "posted": result["posted"] or 0,
        "failed": result["failed"] or 0,
        "anomalies": result["anomalies"] or 0,
        "recent": result["recent_transactions"] or 0,
    }


# ============================================================
# KPI CALLBACK
#
# THIS CALLBACK ONLY UPDATES THE KPI CARDS.
#
# It runs every 1 second.
# ============================================================

@app.callback(
    Output("kpi-transactions", "children"),
    Output("kpi-posted", "children"),
    Output("kpi-failed", "children"),
    Output("kpi-anomalies", "children"),
    Output("kpi-rate", "children"),
    Input("kpi-interval", "n_intervals"),
)
def update_kpis(_):

    stats = load_kpis()

    total = stats["total"]
    posted = stats["posted"]
    failed = stats["failed"]
    anomalies = stats["anomalies"]
    recent = stats["recent"]

    # Transactions in the last 60 seconds
    transactions_per_second = recent / 60

    return (
        f"{total:,}",
        f"{posted:,}",
        f"{failed:,}",
        f"{anomalies:,}",
        f"{transactions_per_second:.2f}",
    )


# ============================================================
# TRANSACTION QUERY
#
# Used by charts and recent transaction table.
#
# This is deliberately NOT called every second.
# ============================================================

def load_transactions():

    query = text(
        """
        SELECT
            id,
            description,
            reference_id,
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

        FROM transactions

        ORDER BY occurred_at DESC

        LIMIT 500
        """
    )

    with engine.connect() as conn:

        df = pd.read_sql(
            query,
            conn,
        )

    return df


# ============================================================
# ANALYTICS CALLBACK
#
# Runs every 5 seconds.
#
# Updates:
#   - transaction chart
#   - risk chart
#   - payment method chart
#   - status chart
#   - recent transactions
# ============================================================

@app.callback(
    Output(
        "transaction-volume-chart",
        "figure",
    ),

    Output(
        "risk-chart",
        "figure",
    ),

    Output(
        "payment-method-chart",
        "figure",
    ),

    Output(
        "status-chart",
        "figure",
    ),

    Output(
        "recent-transactions",
        "children",
    ),

    Output(
        "last-updated",
        "children",
    ),

    Input(
        "analytics-interval",
        "n_intervals",
    ),
)
def update_analytics(_):

    df = load_transactions()

    # ========================================================
    # EMPTY DATABASE
    # ========================================================

    if df.empty:

        empty_fig = px.scatter(
            title="No transaction data yet"
        )

        return (
            empty_fig,
            empty_fig,
            empty_fig,
            empty_fig,
            html.P(
                "No transactions found."
            ),
            "Last updated: no data",
        )

    # ========================================================
    # CLEAN DATA
    # ========================================================

    df["occurred_at"] = pd.to_datetime(
        df["occurred_at"],
        utc=True,
    )

    df["amount"] = pd.to_numeric(
        df["amount"],
        errors="coerce",
    )

    # ========================================================
    # TRANSACTION VOLUME
    # ========================================================

    volume = (
        df.set_index("occurred_at")
        .resample("10s")
        .size()
        .reset_index(
            name="transactions"
        )
    )

    volume_fig = px.line(
        volume,
        x="occurred_at",
        y="transactions",
        markers=True,
        title="Transactions per 10-second interval",
    )

    volume_fig.update_layout(
        margin=dict(
            l=20,
            r=20,
            t=50,
            b=20,
        ),

        xaxis_title="Time",

        yaxis_title="Transactions",

        hovermode="x unified",
    )

    # ========================================================
    # RISK DISTRIBUTION
    # ========================================================

    risk = (
        df["risk_level"]
        .fillna("UNKNOWN")
        .value_counts()
        .reset_index()
    )

    risk.columns = [
        "risk_level",
        "count",
    ]

    risk_fig = px.pie(
        risk,
        names="risk_level",
        values="count",
        hole=0.45,
        title="Risk Levels",
    )

    risk_fig.update_layout(
        margin=dict(
            l=20,
            r=20,
            t=50,
            b=20,
        ),
    )

    # ========================================================
    # PAYMENT METHODS
    # ========================================================

    methods = (
        df["payment_method"]
        .fillna("UNKNOWN")
        .value_counts()
        .reset_index()
    )

    methods.columns = [
        "payment_method",
        "count",
    ]

    method_fig = px.bar(
        methods,
        x="payment_method",
        y="count",
        title="Transactions by Payment Method",
    )

    method_fig.update_layout(
        margin=dict(
            l=20,
            r=20,
            t=50,
            b=20,
        ),

        xaxis_title="Payment Method",

        yaxis_title="Transactions",
    )

    # ========================================================
    # STATUS
    # ========================================================

    status = (
        df["status"]
        .fillna("UNKNOWN")
        .value_counts()
        .reset_index()
    )

    status.columns = [
        "status",
        "count",
    ]

    status_fig = px.bar(
        status,
        x="status",
        y="count",
        title="Transaction Status",
    )

    status_fig.update_layout(
        margin=dict(
            l=20,
            r=20,
            t=50,
            b=20,
        ),

        xaxis_title="Status",

        yaxis_title="Transactions",
    )

    # ========================================================
    # RECENT TRANSACTIONS TABLE
    # ========================================================

    recent_df = df.head(15).copy()

    rows = []

    headers = [
        "Time",
        "Event",
        "Customer",
        "Amount",
        "Currency",
        "Method",
        "Status",
        "Risk",
        "Anomaly",
    ]

    # Header
    rows.append(
        html.Tr(
            [
                html.Th(
                    header,
                    style={
                        "padding": "10px",
                        "textAlign": "left",
                        "borderBottom": "1px solid #ddd",
                    },
                )

                for header in headers
            ]
        )
    )

    # Rows
    for _, row in recent_df.iterrows():

        anomaly_score = row["anomaly_score"]

        if pd.isna(anomaly_score):

            anomaly_display = "-"

        else:

            anomaly_display = (
                f"{float(anomaly_score):.2f}"
            )

        rows.append(
            html.Tr(
                [
                    html.Td(
                        row["occurred_at"].strftime(
                            "%H:%M:%S"
                        ),
                        style={
                            "padding": "9px"
                        },
                    ),

                    html.Td(
                        row["event_type"],
                        style={
                            "padding": "9px"
                        },
                    ),

                    html.Td(
                        row["customer_id"],
                        style={
                            "padding": "9px"
                        },
                    ),

                    html.Td(
                        f"{float(row['amount']):,.2f}",
                        style={
                            "padding": "9px"
                        },
                    ),

                    html.Td(
                        row["currency"],
                        style={
                            "padding": "9px"
                        },
                    ),

                    html.Td(
                        row["payment_method"],
                        style={
                            "padding": "9px"
                        },
                    ),

                    html.Td(
                        row["status"],
                        style={
                            "padding": "9px"
                        },
                    ),

                    html.Td(
                        row["risk_level"],
                        style={
                            "padding": "9px"
                        },
                    ),

                    html.Td(
                        anomaly_display,
                        style={
                            "padding": "9px"
                        },
                    ),
                ]
            )
        )

    table = html.Table(
        rows,
        style={
            "width": "100%",
            "borderCollapse": "collapse",
            "fontSize": "13px",
        },
    )

    # ========================================================
    # UPDATED TIMESTAMP
    # ========================================================

    updated = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

    return (
        volume_fig,
        risk_fig,
        method_fig,
        status_fig,
        table,
        f"Analytics updated: {updated}",
    )


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=8050,
    )