from dash import html


def create_kpi_card(title, value_id, subtitle, icon):
    """
    Create a reusable KPI card.

    The value element has its own ID so Dash callbacks
    can update the number without rebuilding the card.
    """

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


def create_section_header(title, subtitle=None):
    """
    Create a reusable dashboard section heading.
    """

    children = [
        html.H2(
            title,
            className="section-title",
        )
    ]

    if subtitle:
        children.append(
            html.P(
                subtitle,
                className="section-subtitle",
            )
        )

    return html.Div(
        className="section-header",
        children=children,
    )


def create_status_badge():
    """
    Create the SYSTEM LIVE indicator.
    """

    return html.Div(
        className="system-status",
        children=[
            html.Span(
                className="status-dot",
            ),
            html.Span(
                "SYSTEM LIVE",
                className="status-text",
            ),
        ],
    )