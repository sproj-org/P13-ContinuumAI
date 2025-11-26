# -*- coding: utf-8 -*-
############ Imports ##############
import vizro.plotly.express as px
import vizro.models as vm
from vizro.models.types import capture
from vizro import Vizro
import pandas as pd
from vizro.managers import data_manager
import vizro.plotly.express as px
from vizro.models.types import capture


####### Function definitions ######
@capture("graph")
def mom_revenue_growth_by_channel(data_frame):
    # Prepare data: month string (YYYY-MM), aggregate revenue by month and channel
    df = data_frame.copy()
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["month"] = df["order_date"].dt.to_period("M").astype(str)

    monthly = (
        df.groupby(["month", "channel"], as_index=False)["revenue"]
        .sum()
        .rename(columns={"revenue": "monthly_revenue"})
    )

    # Restrict to the most recent 12 months available in the data
    months_sorted = sorted(monthly["month"].unique())
    if len(months_sorted) == 0:
        raise ValueError("No monthly data available")
    last_months = months_sorted[-12:]
    monthly = monthly[monthly["month"].isin(last_months)].copy()

    # convert month to datetime for correct plotting order
    monthly["month"] = pd.to_datetime(monthly["month"])
    monthly = monthly.sort_values(["channel", "month"])

    # compute month-over-month percent change per channel (as percent)
    monthly["mom_pct"] = (
        monthly.groupby("channel")["monthly_revenue"].pct_change() * 100
    )

    # Build the line chart: x=month, y=MoM % change, color=channel
    fig = px.line(
        data_frame=monthly,
        x="month",
        y="mom_pct",
        color="channel",
        markers=True,
        labels={"month": "Month", "mom_pct": "MoM % Change", "channel": "Channel"},
    )

    # Ensure lines show markers and return the figure
    fig.update_traces(mode="lines+markers")
    return fig


@capture("graph")
def returning_customer_cohort_sales_cycle_distribution(data_frame):
    # Purpose: show distribution of sales_cycle_days for monthly cohorts (by first_purchase_date)
    # and split by returning status (is_returning). Uses last 12 months relative to the data.
    df = data_frame.copy()
    # Ensure dates
    df["first_purchase_date"] = pd.to_datetime(df["first_purchase_date"])
    # Limit to the most recent 12 months based on first_purchase_date
    max_date = df["first_purchase_date"].max()
    cutoff = max_date - pd.DateOffset(months=11)
    df = df[df["first_purchase_date"] >= cutoff].copy()
    # Create cohort label as YYYY-MM
    df["cohort"] = df["first_purchase_date"].dt.to_period("M").astype(str)
    # Map is_returning to readable label
    df["returning_label"] = df["is_returning"].map({1: "Returning", 0: "New"})
    # Order cohorts chronologically
    cohort_order = sorted(df["cohort"].unique(), key=lambda x: pd.Period(x))
    df["cohort"] = pd.Categorical(df["cohort"], categories=cohort_order, ordered=True)
    # Build box plot of sales_cycle_days by cohort, colored by returning status
    fig = px.box(
        data_frame=df,
        x="cohort",
        y="sales_cycle_days",
        color="returning_label",
        points="outliers",
        labels={
            "cohort": "Cohort (first_purchase month)",
            "sales_cycle_days": "Sales cycle (days)",
            "returning_label": "Customer type",
        },
        title="Sales cycle distribution by first-purchase cohort (last 12 months) and returning status",
    )
    # Keep legend title clear
    fig.update_layout(legend_title_text="Customer type")
    return fig


@capture("graph")
def salesperson_performance_scatter(data_frame):
    # Ensure dates are parsed and work on a copy
    df = data_frame.copy()
    df["order_date"] = pd.to_datetime(df["order_date"])

    # Aggregate metrics per salesperson
    chart_df = (
        df.groupby("salesperson")
        .agg(
            total_revenue=("revenue", "sum"),
            deals=("order_id", "nunique"),
            avg_sales_cycle_days=("sales_cycle_days", "mean"),
            avg_aov=("aov", "mean"),
        )
        .reset_index()
    )

    # Round numbers for cleaner display
    chart_df["total_revenue"] = chart_df["total_revenue"].round(2)
    chart_df["avg_sales_cycle_days"] = chart_df["avg_sales_cycle_days"].round(1)
    chart_df["avg_aov"] = chart_df["avg_aov"].round(2)

    # Create scatter: x = average sales cycle, y = total revenue, size = number of deals
    fig = px.scatter(
        data_frame=chart_df,
        x="avg_sales_cycle_days",
        y="total_revenue",
        size="deals",
        color="salesperson",
        hover_data=[
            "salesperson",
            "deals",
            "avg_aov",
            "avg_sales_cycle_days",
            "total_revenue",
        ],
        labels={
            "avg_sales_cycle_days": "Avg sales_cycle_days",
            "total_revenue": "Total revenue (USD)",
            "deals": "Number of deals",
        },
        title="Salesperson performance: revenue vs. sales cycle (point size = deals)",
    )

    # Keep axis ranges automatic; return figure for Vizro to render
    return fig


####### Data Manager Settings #####
data_manager["demo_sales.csv"] = pd.read_csv(
    "C:/Users/Umer/Desktop/SPROJ/P13-ContinuumAI/Development/Sprint-1/RnD (Umer)/vizro_app2/continuum_v1/data/demo_sales.csv"
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
                                    id="services_drop_flags_card",
                                    type="card",
                                    text="### Services revenue drop alerts\n- Count: 3\n- Months: 2024-12, 2025-01, 2025-06",
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
                                    id="recommend_high_value_salesperson_card_card",
                                    type="card",
                                    text="### Recommendation\nBob — recommended to focus on high-value products.\n\nReason: recent average AOV = $6,928.69, which is 24.5% higher than the prior 90-day window,\nand their overall average AOV ($7,274.79) is above the team median ($6,670.57).",
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
                                    id="shortest_avg_sales_cycle_cohort_card",
                                    type="card",
                                    text="### Cohort with shortest avg sales cycle\n**2025-10** — 8.8 days (average)",
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
                                    id="mom_revenue_growth_by_channel_component",
                                    type="graph",
                                    figure=mom_revenue_growth_by_channel(
                                        data_frame="demo_sales.csv"
                                    ),
                                    title="Mom Revenue Growth By Channel",
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
                                    id="salesperson_performance_scatter_component",
                                    type="graph",
                                    figure=salesperson_performance_scatter(
                                        data_frame="demo_sales.csv"
                                    ),
                                    title="Salesperson Performance Scatter",
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
                                    id="returning_customer_cohort_sales_cycle_distribution_component",
                                    type="graph",
                                    figure=returning_customer_cohort_sales_cycle_distribution(
                                        data_frame="demo_sales.csv"
                                    ),
                                    title="Returning Customer Cohort Sales Cycle Distribution",
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