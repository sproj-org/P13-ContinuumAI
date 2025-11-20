from __future__ import annotations

from typing import Optional

from dash import Input, Output, State, dcc, html, no_update
import plotly.graph_objects as go
from vizro import Vizro
from vizro.models import Dashboard, Grid, Graph, Page

from sql_pipeline import SQLQueryPipeline

SQL_PIPELINE = SQLQueryPipeline()


def _blank_figure(title: str = "Awaiting query"):
    fig = go.Figure()
    fig.update_layout(
        title=title,
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": "Send a message to generate insights.",
                "xref": "paper",
                "yref": "paper",
                "showarrow": False,
                "font": {"size": 16},
            }
        ],
    )
    return fig


def build_dashboard() -> Dashboard:
    """Create a Vizro dashboard showcasing the pipeline-driven visuals."""
    return Dashboard(
        title="Vizro Conversational Demo",
        pages=[
            Page(
                title="Chat + Visualization",
                layout=Grid(grid=[[0]]),
                components=[
                    Graph(id="viz_chart", figure=_blank_figure()),
                ],
            )
        ],
    )


vizro_app = Vizro()
vizro_app.build(build_dashboard())
_vizro_base_layout = vizro_app.dash.layout


def _chat_panel() -> html.Div:
    return html.Div(
        id="chat_panel",
        style={
            "width": "320px",
            "background": "var(--bs-body-bg)",
            "border": "1px solid var(--bs-border-color)",
            "borderRadius": "8px",
            "padding": "16px",
            "position": "fixed",
            "top": "16px",
            "bottom": "16px",
            "left": "16px",
            "boxSizing": "border-box",
            "overflow": "auto",
            "zIndex": 1000,
            "boxShadow": "0 4px 20px rgba(0, 0, 0, 0.35)",
        },
        children=[
            html.H4("Conversational Filters", className="mb-3"),
            dcc.Markdown(
                id="chat_history",
                children="**Assistant:** Ask me about sales figures to drive the visuals on the right.",
                style={"whiteSpace": "pre-wrap"},
            ),
            dcc.Textarea(
                id="chat_input",
                placeholder="e.g. Show software sales in the West",
                style={"width": "100%", "minHeight": "120px", "marginTop": "12px"},
            ),
            html.Button(
                "Send",
                id="chat_send",
                className="btn btn-primary w-100 mt-3",
            ),
        ],
    )


def _with_chat_layout():
    base_content = _vizro_base_layout() if callable(_vizro_base_layout) else _vizro_base_layout
    return html.Div(
        [
            _chat_panel(),
            html.Div(
                base_content,
                style={
                    "marginLeft": "360px",
                    "padding": "1rem",
                },
            ),
        ]
    )


vizro_app.dash.layout = _with_chat_layout


@vizro_app.dash.callback(
    Output("chat_history", "children"),
    Output("chat_input", "value"),
    Output("viz_chart", "figure"),
    Input("chat_send", "n_clicks"),
    State("chat_input", "value"),
    State("chat_history", "children"),
    prevent_initial_call=True,
)
def handle_chat(
    _clicks: int,
    user_input: Optional[str],
    history: Optional[str],
):
    if not user_input or not user_input.strip():
        return no_update, no_update, no_update, no_update, no_update

    result = SQL_PIPELINE.run(user_input)
    summary = result.get("summary", "")
    new_history = (history or "") + f"\n\n**User:** {user_input.strip()}\n\n**Assistant:** {summary}"

    return (
        new_history,
        "",
        result["figure"],
    )


if __name__ == "__main__":
    vizro_app.run()
