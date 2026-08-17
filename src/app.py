from dash import Dash, html, dcc, Input, Output

from database import initialize_pool, close_pool
from dashboard.queries import (
    get_dashboard_metrics,
    get_transaction_activity,
    get_risk_distribution,
    get_recent_anomalies,
)


# ============================================================
# DATABASE
# ============================================================

initialize_pool()


# ============================================================
# DASH APP
# ============================================================

app = Dash(
    __name__,
    title="LedgerGuard",
)

server = app.server


# ============================================================
# HELPERS
# ============================================================

def metric_card(icon, title, value_id, subtitle):
    return html.Div(
        className="kpi-card",
        children=[
            html.Div(
                className="kpi-card-header",
                children=[
                    html.Div(
                        icon,
                        className="kpi-icon",
                    ),
                    html.Div(
                        title,
                        className="kpi-title",
                    ),
                ],
            ),
            html.Div(
                id=value_id,
                className="kpi-value",
                children="0",
            ),
            html.Div(
                subtitle,
                className="kpi-subtitle",
            ),
        ],
    )


# ============================================================
# LAYOUT
# ============================================================

app.layout = html.Div(
    className="dashboard-container",
    children=[

        # ====================================================
        # HEADER
        # ====================================================

        html.Div(
            className="dashboard-header",
            children=[

                html.Div(
                    className="brand-block",
                    children=[
                        html.H1(
                            "LedgerGuard",
                            className="brand-title",
                        ),
                        html.P(
                            "Real-time transaction monitoring & anomaly detection",
                            className="brand-subtitle",
                        ),
                    ],
                ),

                html.Div(
                    className="system-status",
                    children=[
                        html.Div(
                            className="status-dot",
                        ),
                        html.Div(
                            "SYSTEM LIVE",
                            className="status-text",
                        ),
                    ],
                ),
            ],
        ),

        # ====================================================
        # KPI CARDS
        # ====================================================

        html.Div(
            className="kpi-grid",
            children=[

                metric_card(
                    "↔",
                    "TRANSACTIONS",
                    "total-transactions",
                    "Total transaction events",
                ),

                metric_card(
                    "✓",
                    "POSTED",
                    "posted-transactions",
                    "Successfully processed",
                ),

                metric_card(
                    "⚠",
                    "ANOMALIES",
                    "anomaly-count",
                    "Score >= 0.70",
                ),

                metric_card(
                    "×",
                    "FAILED / DECLINED",
                    "failed-transactions",
                    "Not posted",
                ),
            ],
        ),

        # ====================================================
        # TRANSACTION ACTIVITY
        # ====================================================

        html.Div(
            className="section-header",
            children=[

                html.Div(
                    children=[
                        html.H2(
                            "Transaction Activity",
                            className="section-title",
                        ),
                        html.P(
                            "Live transaction throughput",
                            className="section-subtitle",
                        ),
                    ],
                ),

                html.Div(
                    "LIVE",
                    className="activity-status",
                ),
            ],
        ),

        html.Div(
            className="chart-panel main-chart-panel",
            children=[
                dcc.Graph(
                    id="transaction-activity-chart",
                    config={
                        "displayModeBar": False,
                        "responsive": True,
                    },
                ),
            ],
        ),

        # ====================================================
        # LOWER DASHBOARD
        # ====================================================

        html.Div(
            className="dashboard-grid",
            children=[

                # --------------------------------------------
                # RISK DISTRIBUTION
                # --------------------------------------------

                html.Div(
                    className="chart-panel",
                    children=[

                        html.Div(
                            className="panel-header",
                            children=[
                                html.Div(
                                    "Risk Distribution",
                                    className="panel-title",
                                ),
                                html.Div(
                                    "CURRENT",
                                    className="panel-label",
                                ),
                            ],
                        ),

                        dcc.Graph(
                            id="risk-distribution-chart",
                            config={
                                "displayModeBar": False,
                                "responsive": True,
                            },
                        ),
                    ],
                ),

                # --------------------------------------------
                # RECENT ANOMALIES
                # --------------------------------------------

                html.Div(
                    className="chart-panel",
                    children=[

                        html.Div(
                            className="panel-header",
                            children=[
                                html.Div(
                                    "Recent Anomalies",
                                    className="panel-title",
                                ),
                                html.Div(
                                    "LIVE",
                                    className="panel-label",
                                ),
                            ],
                        ),

                        html.Div(
                            id="recent-anomalies",
                            className="anomaly-list",
                        ),
                    ],
                ),
            ],
        ),

        # ====================================================
        # AUTO REFRESH
        # ====================================================

        dcc.Interval(
            id="dashboard-refresh",
            interval=1000,
            n_intervals=0,
        ),
    ],
)


# ============================================================
# DASHBOARD CALLBACK
# ============================================================

@app.callback(
    Output("total-transactions", "children"),
    Output("posted-transactions", "children"),
    Output("anomaly-count", "children"),
    Output("failed-transactions", "children"),
    Output("transaction-activity-chart", "figure"),
    Output("risk-distribution-chart", "figure"),
    Output("recent-anomalies", "children"),
    Input("dashboard-refresh", "n_intervals"),
)
def update_dashboard(n_intervals):

    metrics = get_dashboard_metrics()

    activity_figure = get_transaction_activity()

    risk_figure = get_risk_distribution()

    anomalies = get_recent_anomalies()

    return (
        f"{metrics['total_transactions']:,}",
        f"{metrics['posted_transactions']:,}",
        f"{metrics['anomalies']:,}",
        f"{metrics['failed_transactions']:,}",
        activity_figure,
        risk_figure,
        anomalies,
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:
        app.run(
            debug=True,
            host="127.0.0.1",
            port=8050,
        )

    finally:
        close_pool()