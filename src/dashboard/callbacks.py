from dash import Input, Output

from dashboard.queries import (
    get_dashboard_metrics,
    get_transaction_activity,
    get_risk_distribution,
    get_recent_anomalies,
)


def register_callbacks(app):
    @app.callback(
        Output("kpi-transactions", "children"),
        Output("kpi-posted", "children"),
        Output("kpi-anomalies", "children"),
        Output("kpi-failed", "children"),
        Output("transaction-chart", "figure"),
        Output("risk-chart", "figure"),
        Output("anomaly-list", "children"),
        Input("dashboard-refresh", "n_intervals"),
    )
    def update_dashboard(_):
        try:
            metrics = get_dashboard_metrics()
            activity = get_transaction_activity()
            risk = get_risk_distribution()
            anomalies = get_recent_anomalies()

            return (
                f"{metrics['total_transactions']:,}",
                f"{metrics['posted_transactions']:,}",
                f"{metrics['anomalies']:,}",
                f"{metrics['failed_transactions']:,}",
                activity,
                risk,
                anomalies,
            )

        except Exception as exc:
            print(f"[DASHBOARD ERROR] {exc}")

            return (
                "—",
                "—",
                "—",
                "—",
                {},
                {},
                "Database unavailable",
            )