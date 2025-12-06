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
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go

    # Copy + ensure datetime
    df = data_frame.copy()
    df["order_date"] = pd.to_datetime(df["order_date"])
    # month bucket as Timestamp at month start
    df["year_month"] = df["order_date"].dt.to_period("M").dt.to_timestamp()

    # Keep last 12 months relative to max available month
    max_month = df["year_month"].max()
    start_month = max_month - pd.DateOffset(months=11)
    df_12 = df[df["year_month"] >= start_month]

    # Aggregate revenue by month and channel
    monthly_channel = df_12.groupby(["year_month", "channel"], as_index=False)[
        "revenue"
    ].sum()
    monthly_channel = monthly_channel.sort_values(["channel", "year_month"])

    # Compute MoM percent change per channel
    monthly_channel["revenue_prev"] = monthly_channel.groupby("channel")[
        "revenue"
    ].shift(1)
    # avoid division-by-zero: compute pct only when previous > 0
    monthly_channel["mom_pct"] = None
    mask_prev_positive = monthly_channel["revenue_prev"] > 0
    monthly_channel.loc[mask_prev_positive, "mom_pct"] = (
        monthly_channel.loc[mask_prev_positive, "revenue"]
        / monthly_channel.loc[mask_prev_positive, "revenue_prev"]
        - 1
    )
    # Fill NaN for first-month or invalid with 0 (no growth computed)
    monthly_channel["mom_pct"] = monthly_channel["mom_pct"].fillna(0)

    # Build line chart of MoM % by channel
    fig = px.line(
        data_frame=monthly_channel,
        x="year_month",
        y="mom_pct",
        color="channel",
        markers=True,
        labels={"mom_pct": "MoM Growth", "year_month": "Month"},
    )
    # show percent ticks
    fig.update_yaxes(tickformat=".1%")

    # Compute Services category monthly MoM pct to find >15% drops and annotate
    services = (
        df_12[df_12["category"] == "Services"]
        .groupby("year_month", as_index=False)["revenue"]
        .sum()
        .sort_values("year_month")
    )
    services["revenue_prev"] = services["revenue"].shift(1)
    services["mom_pct"] = None
    mask_prev_positive_s = services["revenue_prev"] > 0
    services.loc[mask_prev_positive_s, "mom_pct"] = (
        services.loc[mask_prev_positive_s, "revenue"]
        / services.loc[mask_prev_positive_s, "revenue_prev"]
        - 1
    )
    services["mom_pct"] = services["mom_pct"].fillna(0)

    # Flag months where Services dropped > 15%
    flagged = services[services["mom_pct"] < -0.15]

    # Add a lightweight Services series + flagged markers for visibility on the same % scale
    # (This is a category-level overlay to highlight flagged months independent of channel segmentation.)
    if not services.empty:
        fig.add_trace(
            go.Scatter(
                x=services["year_month"],
                y=services["mom_pct"],
                mode="lines+markers",
                name="Services (category) MoM",
                marker=dict(color="black", size=6),
                line=dict(dash="dash"),
            )
        )
    # Add red markers for flagged months
    if not flagged.empty:
        fig.add_trace(
            go.Scatter(
                x=flagged["year_month"],
                y=flagged["mom_pct"],
                mode="markers",
                name="Services >15% drop",
                marker=dict(color="red", size=10, symbol="x"),
            )
        )

    # Ensure ordering of x-axis months (plotly usually handles timestamps, but keep it sorted)
    fig.update_xaxes(type="date", tickformat="%Y-%m")

    return fig


@capture("graph")
def returning_customer_cohort_sales_cycle_distribution(data_frame):
    # Prepare a working copy and ensure dates are datetimes
    df = data_frame.copy()
    df["first_purchase_date"] = pd.to_datetime(df["first_purchase_date"])

    # Create cohort month (YYYY-MM) based on first_purchase_date
    df["cohort_month"] = df["first_purchase_date"].dt.to_period("M").astype(str)

    # Limit to the most recent 12 months of first_purchase_date to keep the cohort view focused
    max_date = df["first_purchase_date"].max()
    cutoff = (max_date - pd.DateOffset(months=11)).replace(day=1)
    df = df[df["first_purchase_date"] >= cutoff]

    # Friendly labels for returning status
    df["returning_label"] = df["is_returning"].map({1: "Returning", 0: "New"})

    # Ensure cohorts are ordered chronologically on the x-axis
    cohort_order = sorted(df["cohort_month"].unique())

    # Build violin plot: distribution of sales_cycle_days by cohort, segmented by returning/new
    fig = px.violin(
        data_frame=df,
        x="cohort_month",
        y="sales_cycle_days",
        color="returning_label",
        box=True,
        points="outliers",
        labels={
            "cohort_month": "Cohort (first_purchase_month)",
            "sales_cycle_days": "Sales Cycle Days",
            "returning_label": "Customer Type",
        },
        category_orders={"cohort_month": cohort_order},
    )

    # Return the figure for rendering in the dashboard
    return fig


@capture("graph")
def salesperson_performance_bubble_chart(data_frame):
    # Compare each salesperson by total revenue, number of deals, avg sales_cycle_days, and AOV
    df = data_frame.copy()
    # ensure order_date is parsed if needed (not used in this aggregation but safe)
    df["order_date"] = pd.to_datetime(df["order_date"])

    # Aggregate per salesperson with unique column names
    agg_df = (
        df.groupby("salesperson")
        .agg(
            total_revenue=("revenue", "sum"),
            num_deals=("order_id", "nunique"),
            avg_sales_cycle_days=("sales_cycle_days", "mean"),
            avg_aov=("aov", "mean"),
        )
        .reset_index()
    )

    # Create bubble scatter: x=avg sales cycle days, y=avg AOV, size=total revenue, color=num_deals
    fig = px.scatter(
        data_frame=agg_df,
        x="avg_sales_cycle_days",
        y="avg_aov",
        size="total_revenue",
        color="num_deals",
        hover_data=[
            "salesperson",
            "total_revenue",
            "num_deals",
            "avg_sales_cycle_days",
            "avg_aov",
        ],
        labels={
            "avg_sales_cycle_days": "Avg Sales Cycle (days)",
            "avg_aov": "Average Order Value",
            "num_deals": "Number of Deals",
            "total_revenue": "Total Revenue",
        },
    )

    # Return the plotly figure for Vizro to render
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
                                    id="services_drop_flags_count_card",
                                    type="card",
                                    text="### Services >15% MoM drops: 3\nFlagged months: 2024-12, 2025-01, 2025-06",
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
                                    id="salesperson_high_value_recommendation_card",
                                    type="card",
                                    text="### Recommendation\nSalespeople with above-median AOV and non-declining recent monthly revenue.\n\nTop picks to focus on high-value products:\n- **Eve** — Recent AOV: $7,179, Recent revenue (90d): $452,252, Last-month change: 305%\n- **Bob** — Recent AOV: $6,929, Recent revenue (90d): $443,436, Last-month change: 173%\n- **Alice** — Recent AOV: $6,175, Recent revenue (90d): $494,006, Last-month change: 14%\n\nNotes: Consider pairing the recommended salespeople with premium product training and targeted high-value product bundles. If a recommended salesperson has a high sales cycle, ensure they have resources to accelerate decisioning for bigger deals.",
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
                                    id="cohort_shortest_avg_cycle_card_card",
                                    type="card",
                                    text="### Shortest average sales cycle\nCohort: **2025-01** (New)  \nAverage sales_cycle_days: **2.0 days**  \nOrders in cohort: **1**",
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
                                    id="salesperson_performance_bubble_chart_component",
                                    type="graph",
                                    figure=salesperson_performance_bubble_chart(
                                        data_frame="demo_sales.csv"
                                    ),
                                    title="Salesperson Performance Bubble Chart",
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
            controls=[
                vm.Filter(
                    id="filter_1_salesperson",
                    type="filter",
                    column="salesperson",
                    targets=["salesperson_performance_bubble_chart_component"],
                    selector=vm.Dropdown(
                        type="dropdown", multi=True, title="Salesperson filter"
                    ),
                    show_in_url=False,
                    visible=True,
                ),
                vm.Filter(
                    id="filter_2_product_name",
                    type="filter",
                    column="product_name",
                    targets=[
                        "mom_revenue_growth_by_channel_component",
                        "salesperson_performance_bubble_chart_component",
                        "returning_customer_cohort_sales_cycle_distribution_component",
                    ],
                    selector=vm.Dropdown(
                        type="dropdown", multi=True, title="Product Name filter"
                    ),
                    show_in_url=False,
                    visible=True,
                ),
            ],
        )
    ],
    theme="vizro_dark",
    title="My Vizro Dashboard",
)

Vizro().build(model).run(port=8051)