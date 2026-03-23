"""Pragmatic multi-agent orchestration for descriptive, predictive, and segmentation workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.kpi_registry import KPIRegistry, KPIRegistryEntry
from app.models.strategy_bundle import StrategyBundle
from app.services.charts.models import ChartSpecV1
from app.services.charts.spec_resolver import execute_chart_preview
from app.services.intelligence.data_access import (
    aggregate_time_series,
    column_profiles,
    dimension_columns,
    fetch_frame,
    load_mart_profile,
    resolve_entity_field,
    resolve_time_field,
    temporal_columns,
)
from app.services.intelligence.insights import (
    build_prediction_insights,
    build_query_insights,
    build_segment_insights,
    build_strategy_risk_insights,
    build_suggested_actions,
)
from app.services.intelligence.predictive import (
    build_strategy_risk_summary,
    run_prediction_analysis,
    summarize_prediction_from_series,
)
from app.services.intelligence.segmentation import run_segmentation
from app.services.intelligence.specs import (
    AgentRole,
    AgentTaskSpec,
    AnalysisRequest,
    AnalysisResponse,
    InsightCard,
    InsightSpec,
    NormalizedDataView,
    PlanSpec,
    PredictionSpec,
    QuerySpec,
    SegmentSpec,
    SpecFilter,
    StrategyRiskSummary,
    StrategySpec,
    TaskType,
)
from app.services.strategy.evaluator import evaluate_kpi_formula, parse_formula
from app.services.strategy.storage import load_current_artifacts

PREDICTION_TOKENS = ("forecast", "predict", "projection", "projected", "outlook", "future", "next")
ANOMALY_TOKENS = ("anomaly", "outlier", "unusual", "spike", "dip", "drop", "deviation")
SEGMENT_TOKENS = ("segment", "cluster", "group customers", "group stores", "cohort")
RISK_TOKENS = ("risk", "target", "on track", "miss target", "attainment", "hit target")
PROFILE_TOKENS = ("columns", "schema", "fields", "what data", "what is in", "available metrics")
INSIGHT_TOKENS = ("why", "explain", "diagnose", "what happened", "drivers")


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").lower().replace("_", " ").split())


def _contains_token(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _tokenize(value: str | None) -> set[str]:
    text = _normalize_text(value)
    return {token for token in text.split() if len(token) >= 3}


def _load_strategy_runtime() -> tuple[StrategyBundle, list[KPIRegistryEntry]]:
    strategy_payload, kpi_payload, _ = load_current_artifacts()
    strategy_bundle = StrategyBundle.model_validate(strategy_payload)
    kpi_registry = KPIRegistry.model_validate(kpi_payload)
    return strategy_bundle, list(kpi_registry.kpis)


def _filters_from_chart_spec(chart_spec: ChartSpecV1 | None) -> list[SpecFilter]:
    if chart_spec is None:
        return []
    return [SpecFilter(field=item.field, op=item.op, value=item.value) for item in chart_spec.filters]


def query_spec_from_chart_spec(chart_spec: ChartSpecV1) -> QuerySpec:
    metric = chart_spec.encoding.y[0]
    x_field = chart_spec.encoding.x.field
    semantic = chart_spec.semantic_context
    return QuerySpec(
        dataset_id=chart_spec.dataset_id,
        table=chart_spec.table,
        chart_type=chart_spec.chart.type,
        measures=[metric.field],
        dimensions=[] if semantic and semantic.chart_family == "trend" else [x_field],
        time_field=x_field if chart_spec.chart.type == "line" else None,
        aggregation=metric.aggregation,
        filters=_filters_from_chart_spec(chart_spec),
        limit=chart_spec.limit,
        kpi_id=semantic.matched_kpi_id if semantic else None,
        semantic_family=semantic.semantic_family if semantic else None,
        drill_dimensions=list(semantic.preferred_drill_path) if semantic else [],
        recommendation_source=semantic.recommendation_source if semantic else None,
    )


def _query_spec_to_chart_spec(query_spec: QuerySpec, *, dataset_id: str, table: str) -> ChartSpecV1:
    metric = query_spec.measures[0] if query_spec.measures else "id"
    x_field = query_spec.time_field or (query_spec.dimensions[0] if query_spec.dimensions else "id")
    chart_type = query_spec.chart_type or ("line" if query_spec.time_field else "bar")
    return ChartSpecV1(
        dataset_id=dataset_id,
        table=table,
        chart={"type": chart_type},
        encoding={"x": {"field": x_field}, "y": [{"field": metric, "aggregation": query_spec.aggregation or "sum"}]},
        filters=[item.model_dump(mode="python") for item in query_spec.filters],
        sort=[{"field": metric, "direction": "desc"}],
        limit=query_spec.limit or 20,
    )


def _match_kpi(
    *,
    message: str | None,
    chart_spec: ChartSpecV1 | None,
    explicit_kpi_id: str | None,
    kpis: list[KPIRegistryEntry],
    table: str | None,
) -> KPIRegistryEntry | None:
    if explicit_kpi_id:
        for kpi in kpis:
            if kpi.id == explicit_kpi_id:
                return kpi
    persisted = chart_spec.semantic_context.matched_kpi_id if chart_spec and chart_spec.semantic_context else None
    if persisted:
        for kpi in kpis:
            if kpi.id == persisted:
                return kpi

    message_tokens = _tokenize(message)
    metric_field = chart_spec.encoding.y[0].field if chart_spec else None
    best: tuple[int, KPIRegistryEntry] | None = None
    for kpi in kpis:
        score = 0
        if table and table in kpi.marts:
            score += 4
        if metric_field and metric_field in kpi.required_columns:
            score += 6
        kpi_tokens = {
            *_tokenize(kpi.id),
            *_tokenize(kpi.display_name),
            *_tokenize(kpi.semantic_family),
            *{token for alias in kpi.metric_aliases for token in _tokenize(alias)},
            *{token for concept in kpi.business_concepts for token in _tokenize(concept)},
        }
        score += len(message_tokens.intersection(kpi_tokens)) * 2
        if best is None or score > best[0]:
            best = (score, kpi)
    return best[1] if best and best[0] >= 4 else None


def _detect_task_type(request: AnalysisRequest, matched_kpi: KPIRegistryEntry | None) -> TaskType:
    if request.task_type != "auto":
        return request.task_type  # type: ignore[return-value]
    text = _normalize_text(request.message)
    if _contains_token(text, SEGMENT_TOKENS):
        return "segment"
    if _contains_token(text, RISK_TOKENS) and matched_kpi is not None:
        return "strategy_risk"
    if _contains_token(text, ANOMALY_TOKENS):
        return "anomaly"
    if _contains_token(text, PREDICTION_TOKENS):
        return "forecast"
    if _contains_token(text, PROFILE_TOKENS):
        return "profile"
    if _contains_token(text, INSIGHT_TOKENS):
        return "insight"
    return "query"


def _resolve_table(request: AnalysisRequest, matched_kpi: KPIRegistryEntry | None) -> str | None:
    return request.table or (request.chart_spec.table if request.chart_spec else None) or (
        matched_kpi.marts[0] if matched_kpi and matched_kpi.marts else None
    )


def _build_prediction_spec(
    request: AnalysisRequest,
    *,
    dataset_id: str,
    table: str,
    matched_kpi: KPIRegistryEntry | None,
    strategy_bundle: StrategyBundle,
    mode: str,
) -> PredictionSpec:
    base_query = request.query_spec or (query_spec_from_chart_spec(request.chart_spec) if request.chart_spec else None)
    profile = load_mart_profile(dataset_id, table)
    metric = (
        request.metric
        or (request.prediction_spec.metric if request.prediction_spec else None)
        or (base_query.measures[0] if base_query and base_query.measures else None)
        or (matched_kpi.required_columns[0] if matched_kpi and matched_kpi.required_columns else None)
    )
    if not metric:
        raise HTTPException(status_code=422, detail="A metric is required for predictive analysis")

    time_field = request.time_field or (request.prediction_spec.time_field if request.prediction_spec else None) or (
        base_query.time_field if base_query else None
    ) or resolve_time_field(profile)
    if not time_field:
        raise HTTPException(status_code=422, detail="A temporal field is required for predictive analysis")

    target = strategy_bundle.targets.get(matched_kpi.id) if matched_kpi else None
    return PredictionSpec(
        mode=mode,  # type: ignore[arg-type]
        dataset_id=dataset_id,
        table=table,
        metric=metric,
        aggregation=(request.prediction_spec.aggregation if request.prediction_spec else None) or (
            base_query.aggregation if base_query else None
        ) or "sum",
        time_field=time_field,
        time_grain=request.time_grain or (request.prediction_spec.time_grain if request.prediction_spec else None) or (
            base_query.time_grain if base_query else None
        ) or "month",
        filters=request.filters or (request.prediction_spec.filters if request.prediction_spec else None) or (
            base_query.filters if base_query else None
        ) or _filters_from_chart_spec(request.chart_spec),
        horizon=request.horizon or (request.prediction_spec.horizon if request.prediction_spec else None) or 6,
        kpi_id=matched_kpi.id if matched_kpi else None,
        target_value=target.target if target else None,
        target_direction=target.direction if target else None,
    )


def _build_segment_spec(request: AnalysisRequest, *, dataset_id: str, table: str) -> SegmentSpec:
    profile = load_mart_profile(dataset_id, table)
    entity_field = request.entity_field or (request.segment_spec.entity_field if request.segment_spec else None) or resolve_entity_field(profile)
    if not entity_field:
        raise HTTPException(status_code=422, detail="An entity field is required for segmentation")
    return SegmentSpec(
        dataset_id=dataset_id,
        table=table,
        entity_field=entity_field,
        features=request.features or (request.segment_spec.features if request.segment_spec else None) or [],
        filters=request.filters or (request.segment_spec.filters if request.segment_spec else None) or _filters_from_chart_spec(request.chart_spec),
        cluster_count=request.cluster_count or (request.segment_spec.cluster_count if request.segment_spec else None) or 4,
        metric_focus=request.metric or (request.segment_spec.metric_focus if request.segment_spec else None),
    )


def _build_strategy_spec(
    *,
    request: AnalysisRequest,
    dataset_id: str,
    table: str | None,
    matched_kpi: KPIRegistryEntry,
    strategy_bundle: StrategyBundle,
) -> StrategySpec:
    target = strategy_bundle.targets.get(matched_kpi.id)
    return StrategySpec(
        dataset_id=dataset_id,
        kpi_id=matched_kpi.id,
        table=table,
        target_value=target.target if target else None,
        direction=target.direction if target else None,
        time_grain=request.time_grain or "month",
        horizon=request.horizon or 6,
        filters=request.filters or _filters_from_chart_spec(request.chart_spec),
    )


def create_plan(request: AnalysisRequest, *, dataset_id: str) -> tuple[PlanSpec, KPIRegistryEntry | None]:
    strategy_bundle, kpis = _load_strategy_runtime()
    table_hint = request.table or (request.chart_spec.table if request.chart_spec else None)
    matched_kpi = _match_kpi(
        message=request.message,
        chart_spec=request.chart_spec,
        explicit_kpi_id=request.kpi_id or (request.strategy_spec.kpi_id if request.strategy_spec else None),
        kpis=kpis,
        table=table_hint,
    )
    task_type = _detect_task_type(request, matched_kpi)
    table = _resolve_table(request, matched_kpi)
    if task_type != "strategy_risk" and not table:
        raise HTTPException(status_code=422, detail="A mart is required for this analysis request")

    tasks: list[AgentTaskSpec] = []
    if task_type in {"query", "insight"}:
        query_spec = request.query_spec or (query_spec_from_chart_spec(request.chart_spec) if request.chart_spec else None)
        if query_spec is None and table:
            query_spec = QuerySpec(dataset_id=dataset_id, table=table)
        tasks.append(
            AgentTaskSpec(
                task_type="query" if task_type == "query" else "insight",
                agent_role="viz_agent",
                title="Build descriptive view",
                query_spec=query_spec,
                insight_spec=InsightSpec(source_task=task_type),
            )
        )
    elif task_type == "profile":
        tasks.append(
            AgentTaskSpec(
                task_type="profile",
                agent_role="profiling_agent",
                title="Profile mart capabilities",
                insight_spec=InsightSpec(source_task="profile"),
            )
        )
    elif task_type in {"forecast", "anomaly"}:
        tasks.append(
            AgentTaskSpec(
                task_type=task_type,
                agent_role="ml_agent",
                title="Run predictive analysis",
                prediction_spec=_build_prediction_spec(
                    request,
                    dataset_id=dataset_id,
                    table=table or "",
                    matched_kpi=matched_kpi,
                    strategy_bundle=strategy_bundle,
                    mode=task_type,
                ),
            )
        )
    elif task_type == "segment":
        tasks.append(
            AgentTaskSpec(
                task_type="segment",
                agent_role="ml_agent",
                title="Run segmentation analysis",
                segment_spec=_build_segment_spec(request, dataset_id=dataset_id, table=table or ""),
                insight_spec=InsightSpec(source_task="segment"),
            )
        )
    elif task_type == "strategy_risk":
        if matched_kpi is None:
            raise HTTPException(status_code=422, detail="A matched KPI is required for strategy risk analysis")
        tasks.append(
            AgentTaskSpec(
                task_type="strategy_risk",
                agent_role="strategy_agent",
                title="Estimate KPI target risk",
                strategy_spec=_build_strategy_spec(
                    request=request,
                    dataset_id=dataset_id,
                    table=table,
                    matched_kpi=matched_kpi,
                    strategy_bundle=strategy_bundle,
                ),
                insight_spec=InsightSpec(source_task="strategy_risk", kpi_id=matched_kpi.id),
            )
        )

    tasks.append(
        AgentTaskSpec(
            task_type="insight",
            agent_role="insight_agent",
            title="Synthesize next-step insights",
            insight_spec=InsightSpec(source_task=task_type, kpi_id=matched_kpi.id if matched_kpi else None),
        )
    )
    plan = PlanSpec(
        dataset_id=dataset_id,
        table=table,
        user_message=request.message or task_type.replace("_", " "),
        primary_task=task_type,
        route_reason=f"Routed by explicit task type or intent heuristics for {task_type}.",
        matched_kpi_id=matched_kpi.id if matched_kpi else None,
        matched_kpi_label=matched_kpi.display_name or matched_kpi.id if matched_kpi else None,
        tasks=tasks,
        suggested_follow_ups=[],
    )
    return plan, matched_kpi


@dataclass
class AgentExecution:
    query_spec: QuerySpec | None = None
    primary_view: NormalizedDataView | None = None
    prediction: Any | None = None
    segmentation: Any | None = None
    strategy: StrategyRiskSummary | None = None
    insight_cards: list[InsightCard] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


class VizAgent:
    role: AgentRole = "viz_agent"

    def execute(self, task: AgentTaskSpec, request: AnalysisRequest, db: Session, dataset_id: str, table: str | None) -> AgentExecution:
        query_spec = task.query_spec or request.query_spec or (query_spec_from_chart_spec(request.chart_spec) if request.chart_spec else None)
        if request.chart_spec:
            chart_spec = request.chart_spec
        elif query_spec and table:
            chart_spec = _query_spec_to_chart_spec(query_spec, dataset_id=dataset_id, table=table)
        else:
            return AgentExecution(query_spec=query_spec)

        preview = execute_chart_preview(dataset_id=dataset_id, chart_spec=chart_spec, db=db)
        return AgentExecution(
            query_spec=query_spec or query_spec_from_chart_spec(chart_spec),
            primary_view=NormalizedDataView(
                chart_spec=ChartSpecV1.model_validate(preview["chart_spec"]),
                columns=list(preview.get("columns", [])),
                rows=list(preview.get("rows", [])),
                summary="Descriptive chart generated from the current chart/query context.",
            ),
            meta={"preview_meta": preview.get("meta", {})},
        )


class ProfilingAgent:
    role: AgentRole = "profiling_agent"

    def execute(self, _: AgentTaskSpec, __: AnalysisRequest, db: Session, dataset_id: str, table: str | None) -> AgentExecution:
        _ = db
        if not table:
            raise HTTPException(status_code=422, detail="A mart is required for profiling analysis")
        profile = load_mart_profile(dataset_id, table)
        measures = [
            name
            for name, item in column_profiles(profile).items()
            if str(item.get("effective_role") or item.get("base_role") or "").lower() == "measure"
        ]
        insights = [
            InsightCard(
                title=f"{table} mart profile",
                summary=f"{table} exposes {len(measures)} measures, {len(dimension_columns(profile))} dimensions, and {len(temporal_columns(profile))} temporal fields.",
                severity="info",
                recommended_action="Start with a descriptive chart, then forecast or segment once the core metric is chosen.",
            )
        ]
        return AgentExecution(insight_cards=insights, meta={"profile": {"measures": measures[:8]}})


class MLAgent:
    role: AgentRole = "ml_agent"

    def execute(self, task: AgentTaskSpec, _: AnalysisRequest, db: Session, dataset_id: str, table: str | None) -> AgentExecution:
        if task.prediction_spec:
            prediction = run_prediction_analysis(task.prediction_spec.model_copy(update={"dataset_id": dataset_id}), db)
            observed_rows = [
                {
                    task.prediction_spec.time_field: point.label,
                    task.prediction_spec.metric: point.actual if point.actual is not None else point.forecast,
                    "actual_value": point.actual,
                    "forecast_value": point.forecast,
                    "is_forecast": point.is_forecast,
                    "anomaly_flag": point.anomaly_flag,
                }
                for point in prediction.points
            ]
            chart_spec = ChartSpecV1(
                dataset_id=dataset_id,
                table=task.prediction_spec.table,
                chart={"type": "line"},
                encoding={
                    "x": {"field": task.prediction_spec.time_field},
                    "y": [{"field": task.prediction_spec.metric, "aggregation": task.prediction_spec.aggregation}],
                },
                filters=[item.model_dump(mode="python") for item in task.prediction_spec.filters],
                limit=max(len(observed_rows), 20),
            )
            return AgentExecution(
                query_spec=QuerySpec(
                    dataset_id=dataset_id,
                    table=task.prediction_spec.table,
                    chart_type="line",
                    measures=[task.prediction_spec.metric],
                    dimensions=[],
                    time_field=task.prediction_spec.time_field,
                    aggregation=task.prediction_spec.aggregation,
                    time_grain=task.prediction_spec.time_grain,
                    filters=task.prediction_spec.filters,
                    kpi_id=task.prediction_spec.kpi_id,
                ),
                primary_view=NormalizedDataView(
                    chart_spec=chart_spec,
                    columns=[
                        task.prediction_spec.time_field,
                        task.prediction_spec.metric,
                        "actual_value",
                        "forecast_value",
                        "is_forecast",
                        "anomaly_flag",
                    ],
                    rows=observed_rows,
                    summary=prediction.explanation,
                ),
                prediction=prediction,
            )

        if task.segment_spec:
            segmentation = run_segmentation(task.segment_spec.model_copy(update={"dataset_id": dataset_id}), db)
            cluster_rows = [
                {
                    "cluster_id": f"Cluster {profile.cluster_id}",
                    "entity_count": profile.entity_count,
                    "cluster_label": profile.label,
                }
                for profile in segmentation.profiles
            ]
            return AgentExecution(
                segmentation=segmentation,
                primary_view=NormalizedDataView(
                    chart_spec=None,
                    columns=["cluster_id", "entity_count", "cluster_label"],
                    rows=cluster_rows,
                    summary=f"Segmented {len(segmentation.assignments)} entities into {segmentation.cluster_count} clusters.",
                ),
            )

        raise HTTPException(status_code=422, detail="MLAgent requires a prediction or segmentation spec")


class StrategyAgent:
    role: AgentRole = "strategy_agent"

    def execute(self, task: AgentTaskSpec, _: AnalysisRequest, db: Session, dataset_id: str, table: str | None) -> AgentExecution:
        strategy_bundle, kpis = _load_strategy_runtime()
        strategy_spec = task.strategy_spec
        if strategy_spec is None:
            raise HTTPException(status_code=422, detail="StrategyAgent requires a strategy spec")
        kpi = next((item for item in kpis if item.id == strategy_spec.kpi_id), None)
        if kpi is None:
            raise HTTPException(status_code=404, detail=f"Unknown KPI '{strategy_spec.kpi_id}'")

        current_payload = evaluate_kpi_formula(
            dataset_id=dataset_id,
            kpi=kpi,
            db=db,
            filters=[item.model_dump(mode="python") for item in strategy_spec.filters],
        )
        current_value = current_payload.get("value")
        target = strategy_bundle.targets.get(kpi.id)
        prediction = self._predict_kpi_trend(
            dataset_id=dataset_id,
            kpi=kpi,
            strategy_spec=strategy_spec,
            db=db,
            target_value=target.target if target else None,
            target_direction=target.direction if target else None,
        )
        strategy = build_strategy_risk_summary(
            kpi_id=kpi.id,
            target_value=target.target if target else None,
            current_value=current_value if isinstance(current_value, (float, int)) else None,
            prediction=prediction,
            direction=target.direction if target else None,
        )

        primary_view = None
        if prediction is not None:
            metric_label = kpi.display_name or kpi.id
            primary_view = NormalizedDataView(
                chart_spec=ChartSpecV1(
                    dataset_id=dataset_id,
                    table=table or kpi.marts[0],
                    chart={"type": "line"},
                    encoding={"x": {"field": prediction.time_field}, "y": [{"field": metric_label, "aggregation": "sum"}]},
                    limit=max(len(prediction.points), 20),
                ),
                columns=[prediction.time_field, metric_label, "actual_value", "forecast_value", "is_forecast"],
                rows=[
                    {
                        prediction.time_field: point.label,
                        metric_label: point.actual if point.actual is not None else point.forecast,
                        "actual_value": point.actual,
                        "forecast_value": point.forecast,
                        "is_forecast": point.is_forecast,
                    }
                    for point in prediction.points
                ],
                summary=strategy.explanation,
            )
        return AgentExecution(strategy=strategy, prediction=prediction, primary_view=primary_view)

    def _predict_kpi_trend(
        self,
        *,
        dataset_id: str,
        kpi: KPIRegistryEntry,
        strategy_spec: StrategySpec,
        db: Session,
        target_value: float | None,
        target_direction: str | None,
    ):
        try:
            formula_plan = parse_formula(kpi.formula)
        except ValueError:
            return None

        mart = strategy_spec.table or (kpi.marts[0] if kpi.marts else None)
        if mart is None:
            return None
        profile = load_mart_profile(dataset_id, mart)
        time_field = resolve_time_field(profile)
        if not time_field:
            return None

        columns = [time_field, formula_plan.numerator.column]
        if formula_plan.denominator is not None:
            columns.append(formula_plan.denominator.column)
        frame = fetch_frame(
            dataset_id=dataset_id,
            table=mart,
            columns=columns,
            filters=strategy_spec.filters,
            db=db,
            limit=20000,
        )
        if frame.empty:
            return None

        numerator = aggregate_time_series(
            frame,
            time_field=time_field,
            metric=formula_plan.numerator.column,
            aggregation=formula_plan.numerator.fn,
            grain=strategy_spec.time_grain,
        )
        if numerator.empty:
            return None

        if formula_plan.denominator is None:
            series_frame = numerator
        else:
            denominator = aggregate_time_series(
                frame,
                time_field=time_field,
                metric=formula_plan.denominator.column,
                aggregation=formula_plan.denominator.fn,
                grain=strategy_spec.time_grain,
            )
            merged = numerator.merge(
                denominator[["period_start", "value"]].rename(columns={"value": "denominator_value"}),
                on="period_start",
                how="left",
            )
            merged["value"] = merged.apply(
                lambda row: float(row["value"]) / float(row["denominator_value"])
                if row.get("denominator_value") not in (None, 0, 0.0)
                else None,
                axis=1,
            )
            series_frame = merged.dropna(subset=["value"])
        if series_frame.empty:
            return None

        prediction_spec = PredictionSpec(
            mode="risk",
            dataset_id=dataset_id,
            table=mart,
            metric=kpi.display_name or kpi.id,
            aggregation="sum",
            time_field=time_field,
            time_grain=strategy_spec.time_grain,
            horizon=strategy_spec.horizon,
            kpi_id=kpi.id,
            target_value=target_value,
            target_direction=target_direction if target_direction in {"up", "down"} else None,
        )
        return summarize_prediction_from_series(
            labels=[str(item) for item in series_frame["period_label"].tolist()],
            values=[float(item) for item in series_frame["value"].tolist()],
            spec=prediction_spec,
            last_period=pd.Timestamp(series_frame["period_start"].iloc[-1]),
        )


class InsightAgent:
    role: AgentRole = "insight_agent"

    def synthesize(
        self,
        *,
        plan: PlanSpec,
        query_spec: QuerySpec | None,
        primary_view: NormalizedDataView | None,
        prediction: Any | None,
        segmentation: Any | None,
        strategy: StrategyRiskSummary | None,
    ) -> list[InsightCard]:
        cards: list[InsightCard] = []
        if prediction is not None:
            cards.extend(build_prediction_insights(prediction, kpi_label=plan.matched_kpi_label))
        if segmentation is not None:
            cards.extend(build_segment_insights(segmentation, metric_focus=query_spec.measures[0] if query_spec and query_spec.measures else None))
        if strategy is not None:
            cards.extend(build_strategy_risk_insights(strategy))
        if primary_view is not None:
            cards.extend(build_query_insights(primary_view.rows, query_spec))
        return cards


def run_analysis_request(*, dataset_id: str, request: AnalysisRequest, db: Session) -> AnalysisResponse:
    plan, matched_kpi = create_plan(request, dataset_id=dataset_id)
    viz_agent = VizAgent()
    profiling_agent = ProfilingAgent()
    ml_agent = MLAgent()
    strategy_agent = StrategyAgent()
    insight_agent = InsightAgent()

    query_spec: QuerySpec | None = request.query_spec or (query_spec_from_chart_spec(request.chart_spec) if request.chart_spec else None)
    primary_view: NormalizedDataView | None = None
    prediction = None
    segmentation = None
    strategy = None
    meta: dict[str, Any] = {}

    for task in plan.tasks:
        if task.agent_role == "viz_agent":
            result = viz_agent.execute(task, request, db, dataset_id, plan.table)
        elif task.agent_role == "profiling_agent":
            result = profiling_agent.execute(task, request, db, dataset_id, plan.table)
        elif task.agent_role == "ml_agent":
            result = ml_agent.execute(task, request, db, dataset_id, plan.table)
        elif task.agent_role == "strategy_agent":
            result = strategy_agent.execute(task, request, db, dataset_id, plan.table)
        else:
            continue

        query_spec = result.query_spec or query_spec
        primary_view = result.primary_view or primary_view
        prediction = result.prediction or prediction
        segmentation = result.segmentation or segmentation
        strategy = result.strategy or strategy
        meta.update(result.meta)

    insight_cards = insight_agent.synthesize(
        plan=plan,
        query_spec=query_spec,
        primary_view=primary_view,
        prediction=prediction,
        segmentation=segmentation,
        strategy=strategy,
    )
    suggested_actions = build_suggested_actions(
        task_type=plan.primary_task,
        table=plan.table,
        kpi_id=matched_kpi.id if matched_kpi else None,
        query_spec=query_spec,
        entity_field=segmentation.entity_field if segmentation else None,
    )

    return AnalysisResponse(
        task_type=plan.primary_task,
        agent_role=plan.tasks[0].agent_role if plan.tasks else "insight_agent",
        plan_spec=plan,
        query_spec=query_spec,
        primary_view=primary_view,
        insight_cards=insight_cards,
        prediction=prediction,
        segmentation=segmentation,
        strategy=strategy,
        suggested_actions=suggested_actions,
        meta=meta,
    )
