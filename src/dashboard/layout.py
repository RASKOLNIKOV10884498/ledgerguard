from dash import dcc, html
import plotly.graph_objects as go

from dashboard.components import (
    create_kpi_card,
    create_status_badge,
)


def empty_transaction_figure():
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=[],
            y=[],
            mode="lines+markers",
            name="Transactions",
        )
    )

    fig.update_layout(
        template="plotly_dark",
        title="Transaction Activity",
        height=360,
        margin=dict(l=40, r=20, t=50, b=40),
    )

    return fig


def empty_risk_figure():
    fig = go.Figure()

    fig.add_trace(
        go.Pie(
            labels=["No data"],
            values=[1],
            hole=0.60,
        )
    )

    fig.update_layout(
        template="plotly_dark",
        title="Risk Distribution",
        height=360,
        margin=dict(l=20, r=20, t=50, b=20),
    )

    return fig


def create_layout():

    return html.Div(
        className="dashboard-container",
        children=[

            # ==================================================
            # HEADER
            # ==================================================

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

                    create_status_badge(),
                ],
            ),

            # ==================================================
            # KPI CARDS
            # ==================================================

            html.Div(
                className="kpi-grid",
                children=[

                    create_kpi_card(
                        "TRANSACTIONS",
                        "kpi-transactions",
                        "Total transaction events",
                        "↔",
                    ),

                    create_kpi_card(
                        "POSTED",
                        "kpi-posted",
                        "Successfully processed",
                        "✓",
                    ),

                    create_kpi_card(
                        "ANOMALIES",
                        "kpi-anomalies",
                        "Score >= 0.70",
                        "⚠",
                    ),

                    create_kpi_card(
                        "FAILED / DECLINED",
                        "kpi-failed",
                        "Not posted",
                        "×",
                    ),
                ],
            ),

            # ==================================================
            # TRANSACTION ACTIVITY
            # ==================================================

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
                        id="activity-status",
                        className="activity-status",
                    ),
                ],
            ),

            html.Div(
                className="chart-panel main-chart-panel",
                children=[

                    dcc.Graph(
                        id="transaction-chart",
                        figure=empty_transaction_figure(),
                        style={
                            "width": "100%",
                            "height": "360px",
                        },
                        config={
                            "displayModeBar": False,
                            "responsive": True,
                        },
                    ),
                ],
            ),

            # ==================================================
            # LOWER DASHBOARD
            # ==================================================

            html.Div(
                className="dashboard-grid",
                children=[

                    # ------------------------------
                    # RISK
                    # ------------------------------

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
                                id="risk-chart",
                                figure=empty_risk_figure(),
                                style={
                                    "width": "100%",
                                    "height": "360px",
                                },
                                config={
                                    "displayModeBar": False,
                                    "responsive": True,
                                },
                            ),
                        ],
                    ),

                    # ------------------------------
                    # ANOMALIES
                    # ------------------------------

                    html.Div(
                        className="chart-panel anomaly-panel",
                        children=[

                            html.Div(
                                className="panel-header",
                                children=[

                                    html.Div(
                                        "Recent Anomalies",
                                        className="panel-title",
                                    ),

                                    html.Div(
                                        "LATEST",
                                        className="panel-label",
                                    ),
                                ],
                            ),

                            html.Div(
                                id="anomaly-list",
                                className="anomaly-list",
                                children="Loading anomalies...",
                            ),
                        ],
                    ),
                ],
            ),

            # ==================================================
            # AUTO REFRESH
            # ==================================================

            dcc.Interval(
                id="dashboard-refresh",
                interval=1000,
                n_intervals=0,
            ),
        ],
    )
