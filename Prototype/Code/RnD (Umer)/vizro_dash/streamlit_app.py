from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from sql_pipeline import SQLQueryPipeline

PIPELINE = SQLQueryPipeline()


def _blank_fig(text: str = "Send a message to generate insights."):
    fig = go.Figure()
    fig.update_layout(
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": text,
                "xref": "paper",
                "yref": "paper",
                "showarrow": False,
                "font": {"size": 16},
            }
        ],
    )
    return fig


def main():
    st.set_page_config(page_title="Vizro Streamlit Chat Demo", layout="wide")

    if "history" not in st.session_state:
        st.session_state.history = [
            {"sender": "Assistant", "text": "Ask me about sales figures to drive the visualization."}
        ]
    if "result" not in st.session_state:
        st.session_state.result = {"figure": _blank_fig(), "detail_figure": None, "sql": None, "summary": ""}

    chat_col, viz_col = st.columns([0.9, 2.1])

    with chat_col:
        st.markdown("### Conversational Filters")
        for message in st.session_state.history:
            st.markdown(f"**{message['sender']}:** {message['text']}")

        with st.form("chat_form", clear_on_submit=True):
            user_input = st.text_area(
                "Message",
                height=120,
                placeholder="e.g. Show software sales in the West",
            )
            submitted = st.form_submit_button("Send")

        if submitted and user_input.strip():
            st.session_state.history.append({"sender": "User", "text": user_input.strip()})
            result = PIPELINE.run(user_input)
            st.session_state.result = result
            st.session_state.history.append({"sender": "Assistant", "text": result.get("summary", "")})
            st.rerun()

    with viz_col:
        st.plotly_chart(st.session_state.result["figure"], width="stretch", key="main_chart")
        if st.session_state.result.get("detail_figure") is not None:
            st.plotly_chart(st.session_state.result["detail_figure"], width="stretch", key="detail_chart")
        st.caption(f"SQL: {st.session_state.result.get('sql')}")


if __name__ == "__main__":
    main()
