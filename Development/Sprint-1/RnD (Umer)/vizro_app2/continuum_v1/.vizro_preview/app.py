# -*- coding: utf-8 -*-
############ Imports ##############
import vizro.plotly.express as px
import vizro.models as vm
from vizro.models.types import capture
from vizro import Vizro
import pandas as pd
from vizro.managers import data_manager
import vizro.plotly.express as px
import numpy as np
from vizro.models.types import capture


####### Function definitions ######
@capture("graph")
def returning_cohort_sales_cycle_distribution(data_frame):
    import pandas as pd
    import plotly.express as px

    # Work on a copy to avoid mutating the original
    df = data_frame.copy()

    # Ensure dates are parsed and build monthly cohort label
    df["first_purchase_date"] = pd.to_datetime(
        df["first_purchase_date"], errors="coerce"
    )
    df["cohort_month"] = df["first_purchase_date"].dt.to_period("M").astype(str)

    # Map is_returning (0/1) to human labels
    df["returning_label"] = df["is_returning"].map({1: "Returning", 0: "New"})

    # Ensure a chronological order for cohorts (helps plotting)
    cohort_values = df["cohort_month"].dropna().unique().tolist()
    try:
        cohort_order = sorted(cohort_values, key=lambda x: pd.Period(x, freq="M"))
    except Exception:
        cohort_order = cohort_values

    # Box plot showing distribution of sales_cycle_days per cohort, split by returning status
    fig = px.box(
        data_frame=df,
        x="cohort_month",
        y="sales_cycle_days",
        color="returning_label",
        category_orders={"cohort_month": cohort_order},
        points="outliers",
        labels={
            "cohort_month": "Cohort (first_purchase month)",
            "sales_cycle_days": "Sales cycle (days)",
            "returning_label": "Customer type",
        },
    )

    # Return the Plotly figure
    return fig


@capture("graph")
def salesperson_performance_bubble(data_frame):
    # data_frame: expects the demo_sales.csv loaded into a pandas DataFrame
    df = data_frame.copy()
    # parse dates
    df["order_date"] = pd.to_datetime(df["order_date"])

    # base aggregations per salesperson
    agg = (
        df.groupby("salesperson")
        .agg(
            total_revenue=("revenue", "sum"),
            deals=("order_id", "nunique"),
            avg_sales_cycle_days=("sales_cycle_days", "mean"),
            avg_aov=("aov", "mean"),
        )
        .reset_index()
    )

    # Define recent window (last 90 days) and previous 90-day window for trend
    max_date = df["order_date"].max()
    recent_start = max_date - pd.Timedelta(days=90)
    prev_start = recent_start - pd.Timedelta(days=90)

    recent = (
        df[(df["order_date"] > recent_start) & (df["order_date"] <= max_date)]
        .groupby("salesperson")["revenue"]
        .sum()
        .reset_index()
        .rename(columns={"revenue": "revenue_recent"})
    )

    prev = (
        df[(df["order_date"] > prev_start) & (df["order_date"] <= recent_start)]
        .groupby("salesperson")["revenue"]
        .sum()
        .reset_index()
        .rename(columns={"revenue": "revenue_prev"})
    )

    # Merge everything into one DataFrame for charting
    chart_df = agg.merge(recent, on="salesperson", how="left").merge(
        prev, on="salesperson", how="left"
    )
    chart_df["revenue_recent"] = chart_df["revenue_recent"].fillna(0)
    chart_df["revenue_prev"] = chart_df["revenue_prev"].fillna(0)

    # percent change vs previous window (NaN when previous is zero)
    chart_df["pct_change_recent"] = np.where(
        chart_df["revenue_prev"] > 0,
        (chart_df["revenue_recent"] - chart_df["revenue_prev"])
        / chart_df["revenue_prev"],
        np.nan,
    )

    # Build bubble scatter: x = avg sales cycle, y = avg AOV, size = total revenue, color = deals
    fig = px.scatter(
        data_frame=chart_df,
        x="avg_sales_cycle_days",
        y="avg_aov",
        size="total_revenue",
        color="deals",
        hover_data=[
            "salesperson",
            "total_revenue",
            "deals",
            "avg_sales_cycle_days",
            "avg_aov",
            "revenue_recent",
            "revenue_prev",
            "pct_change_recent",
        ],
        labels={
            "avg_sales_cycle_days": "Avg Sales Cycle (days)",
            "avg_aov": "Avg Order Value (AOV)",
            "total_revenue": "Total Revenue",
            "deals": "Number of Deals",
        },
    )

    # Improve marker styling
    fig.update_traces(
        marker=dict(opacity=0.85, line={"width": 0.5, "color": "DarkSlateGrey"})
    )

    # Add reference mean lines so viewers can quickly see above/below average for both axes
    mean_x = chart_df["avg_sales_cycle_days"].mean()
    mean_y = chart_df["avg_aov"].mean()
    fig.add_shape(
        type="line",
        x0=mean_x,
        x1=mean_x,
        y0=chart_df["avg_aov"].min(),
        y1=chart_df["avg_aov"].max(),
        line=dict(dash="dash", width=1),
    )
    fig.add_shape(
        type="line",
        x0=chart_df["avg_sales_cycle_days"].min(),
        x1=chart_df["avg_sales_cycle_days"].max(),
        y0=mean_y,
        y1=mean_y,
        line=dict(dash="dash", width=1),
    )

    # Axis titles
    fig.update_layout(
        xaxis_title="Average Sales Cycle (days)",
        yaxis_title="Average Order Value (AOV)",
        legend_title="Number of Deals",
    )

    return fig


####### Data Manager Settings #####
data_manager["demo_sales.csv"] = pd.read_csv(
    "C:/Users/Umer/Desktop/SPROJ/P13-ContinuumAI/Prototype/Code/vizro_app2/continuum_v1/data/demo_sales.csv"
)

########### Model code ############
model = vm.Dashboard(
    pages=[
        vm.Page(
            components=[
                vm.Container(
                    id="flex_wrapper",
                    type="container",
                    components=[
                        vm.Container(
                            id="kpi_card_wrap",
                            type="container",
                            components=[
                                vm.Card(
                                    id="shortest_avg_sales_cycle_cohort_card",
                                    type="card",
                                    text="### Shortest average sales cycle\n**Cohort:** 2025-01  \n**Customer type:** New  \n**Average sales cycle (days):** 2.00  \n**Orders in cohort:** 1",
                                    extra={
                                        "style": {
                                            "textAlign": "center",
                                            "display": "flex",
                                            "flexDirection": "column",
                                            "justifyContent": "center",
                                            "alignItems": "center",
                                            "minHeight": "140px",
                                            "flex": "1 1 calc(50% - 12px)",
                                            "minWidth": "240px",
                                        },
                                        "className": "text-center kpi-card",
                                    },
                                ),
                                vm.Card(
                                    id="recommended_high_value_rep_card",
                                    type="card",
                                    text="### Recommended rep to focus on high-value products\n**Bob** — Total revenue: $822,051, Avg AOV: $7,275, Deals: 113, Recent revenue change: 246.5%\n\nReason: High AOV (>=75th pct) and positive recent revenue trend (246.5%).",
                                    extra={
                                        "style": {
                                            "textAlign": "center",
                                            "display": "flex",
                                            "flexDirection": "column",
                                            "justifyContent": "center",
                                            "alignItems": "center",
                                            "minHeight": "140px",
                                            "flex": "1 1 calc(50% - 12px)",
                                            "minWidth": "240px",
                                        },
                                        "className": "text-center kpi-card",
                                    },
                                ),
                            ],
                            layout=vm.Flex(
                                type="flex", direction="row", gap="16px", wrap=True
                            ),
                        ),
                        vm.Container(
                            id="chart_wrap",
                            type="container",
                            components=[
                                vm.Graph(
                                    id="returning_cohort_sales_cycle_distribution_component",
                                    type="graph",
                                    figure=returning_cohort_sales_cycle_distribution(
                                        data_frame="demo_sales.csv"
                                    ),
                                    title="Returning Cohort Sales Cycle Distribution",
                                    extra={
                                        "style": {
                                            "flex": "1 1 100%",
                                            "width": "100%",
                                            "minWidth": "100%",
                                            "height": "100%",
                                        },
                                        "className": "stretch-graph",
                                    },
                                ),
                                vm.Graph(
                                    id="salesperson_performance_bubble_component",
                                    type="graph",
                                    figure=salesperson_performance_bubble(
                                        data_frame="demo_sales.csv"
                                    ),
                                    title="Salesperson Performance Bubble",
                                    extra={
                                        "style": {
                                            "flex": "1 1 100%",
                                            "width": "100%",
                                            "minWidth": "100%",
                                            "height": "100%",
                                        },
                                        "className": "stretch-graph",
                                    },
                                ),
                            ],
                            layout=vm.Flex(
                                type="flex", direction="column", gap="24px", wrap=False
                            ),
                        ),
                    ],
                    layout=vm.Flex(type="flex", direction="column", wrap=False),
                )
            ],
            title="Overview",
            controls=[],
        )
    ],
    theme="vizro_dark",
    title="My Vizro Dashboard",
)

Vizro().build(model).run(port=8051)