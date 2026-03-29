"""Pragmatic multi-agent orchestration for descriptive, predictive, and segmentation workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.kpi_registry import KPIRegistry, KPIRegistryEntry
from app.models.strategy_bundle import StrategyBundle
from app.services.charts.models import ChartSpecV1
from app.services.charts.spec_resolver import execute_chart_preview
from app.services.intelligence.data_access import (
    column_profiles,
    dimension_columns,
    load_mart_profile,
    measure_columns,
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
)
from app.services.intelligence.segmentation import run_segmentation
from app.services.intelligence.specs import (
    AnalysisContextSpec,
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
    SemanticContextSpec,
    SegmentSpec,
    SpecFilter,
    StrategyRiskSummary,
    StrategyContextSpec,
    StrategySpec,
    TaskType,
)
from app.services.strategy.evaluator import evaluate_kpi_formula
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


def _merge_unique(*values: list[str]) -> list[str]:
    output: list[str] = []
    for items in values:
        for item in items:
            trimmed = item.strip()
            if trimmed and trimmed not in output:
                output.append(trimmed)
    return output


def _coerce_time_grain(value: str | None) -> str | None:
    normalized = _normalize_text(value)
    return normalized if normalized in {"day", "week", "month", "quarter", "year"} else None


def _entity_candidates_for_family(semantic_family: str | None) -> list[str]:
    normalized = _normalize_text(semantic_family)
    if any(token in normalized for token in {"customer", "retention", "churn", "segment"}):
        return ["customer_id", "segment", "city"]
    if any(token in normalized for token in {"inventory", "stockout"}):
        return ["sku_id", "product_id", "store_id"]
    if any(token in normalized for token in {"product", "basket"}):
        return ["product_id", "sku_id", "category", "brand"]
    return ["store_id", "region", "city"]


def _entity_label(field: str | None) -> str | None:
    if not field:
        return None
    return " ".join(field.replace("_", " ").split()).title()


def _analysis_context_from_chart_spec(chart_spec: ChartSpecV1 | None) -> AnalysisContextSpec | None:
    if chart_spec is None:
        return None
    semantic = chart_spec.semantic_context
    if semantic and semantic.analysis_context:
        return AnalysisContextSpec.model_validate(semantic.analysis_context)
    if semantic is None:
        return None
    return AnalysisContextSpec(
        source="api",
        chart_family=semantic.chart_family or chart_spec.chart.type,
        chart_title=semantic.matched_kpi_label,
        table=chart_spec.table,
        semantic=SemanticContextSpec(
            matched_kpi_id=semantic.matched_kpi_id,
            matched_kpi_label=semantic.matched_kpi_label,
            semantic_family=semantic.semantic_family,
            preferred_drill_path=list(semantic.preferred_drill_path),
            mart_hierarchy=list(semantic.mart_hierarchy),
            terminal_dimensions=list(semantic.terminal_dimensions),
        ),
    )


def _analysis_context_from_request(request: AnalysisRequest) -> AnalysisContextSpec | None:
    return request.analysis_context or _analysis_context_from_chart_spec(request.chart_spec)


def _build_analysis_context(
    *,
    request: AnalysisRequest,
    matched_kpi: KPIRegistryEntry | None,
    table: str | None,
) -> AnalysisContextSpec | None:
    existing = _analysis_context_from_request(request)
    if existing is None and matched_kpi is None and table is None:
        return None

    semantic = existing.semantic.model_copy(deep=True) if existing and existing.semantic else SemanticContextSpec()
    if matched_kpi is not None:
        semantic = semantic.model_copy(
            update={
                "matched_kpi_id": semantic.matched_kpi_id or matched_kpi.id,
                "matched_kpi_label": semantic.matched_kpi_label or matched_kpi.display_name or matched_kpi.id,
                "semantic_family": semantic.semantic_family or matched_kpi.semantic_family,
                "marts": _merge_unique(semantic.marts, matched_kpi.marts),
                "required_columns": _merge_unique(semantic.required_columns, matched_kpi.required_columns),
                "dimensions": _merge_unique(semantic.dimensions, matched_kpi.dimensions),
                "metric_aliases": _merge_unique(semantic.metric_aliases, matched_kpi.metric_aliases),
                "business_concepts": _merge_unique(semantic.business_concepts, matched_kpi.business_concepts),
                "preferred_drill_path": _merge_unique(semantic.preferred_drill_path, matched_kpi.preferred_drill_path),
                "mart_hierarchy": _merge_unique(
                    semantic.mart_hierarchy,
                    matched_kpi.mart_drill_overrides.get(table or "", []) if table else [],
                    matched_kpi.preferred_drill_path,
                ),
                "terminal_dimensions": _merge_unique(semantic.terminal_dimensions, matched_kpi.terminal_dimensions),
                "disallowed_drill_dimensions": _merge_unique(
                    semantic.disallowed_drill_dimensions,
                    matched_kpi.disallowed_drill_dimensions,
                ),
                "preferred_chart_types": semantic.preferred_chart_types or list(matched_kpi.preferred_chart_types),
                "default_grain": semantic.default_grain or _coerce_time_grain(matched_kpi.default_grain),
                "metric_field_hint": semantic.metric_field_hint or (matched_kpi.required_columns[0] if matched_kpi.required_columns else None),
            }
        )

    if semantic.time_field_hint is None and request.chart_spec is not None:
        semantic.time_field_hint = request.chart_spec.encoding.x.field
    if semantic.entity_field_hint is None:
        entity_candidates = _entity_candidates_for_family(semantic.semantic_family)
        prioritized_entity_candidates = _merge_unique(
            semantic.terminal_dimensions,
            list(reversed(semantic.preferred_drill_path)),
            list(reversed(semantic.dimensions)),
        )
        semantic.entity_field_hint = next((item for item in prioritized_entity_candidates if item in entity_candidates), None)

    strategy_context = existing.strategy.model_copy(deep=True) if existing and existing.strategy else None
    return AnalysisContextSpec(
        source=existing.source if existing else "api",
        chart_title=(existing.chart_title if existing else None) or request.message or semantic.matched_kpi_label,
        chart_family=(existing.chart_family if existing else None)
        or (request.chart_spec.semantic_context.chart_family if request.chart_spec and request.chart_spec.semantic_context else None)
        or (request.chart_spec.chart.type if request.chart_spec else None),
        table=(existing.table if existing else None) or table,
        semantic=semantic,
        strategy=strategy_context,
    )


def _filters_from_chart_spec(chart_spec: ChartSpecV1 | None) -> list[SpecFilter]:
    if chart_spec is None:
        return []
    return [SpecFilter(field=item.field, op=item.op, value=item.value) for item in chart_spec.filters]


def query_spec_from_chart_spec(chart_spec: ChartSpecV1) -> QuerySpec:
    metric = chart_spec.encoding.y[0]
    x_field = chart_spec.encoding.x.field
    semantic = chart_spec.semantic_context
    analysis_context = _analysis_context_from_chart_spec(chart_spec)
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
        analysis_context=analysis_context,
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
    analysis_context: AnalysisContextSpec | None,
    kpis: list[KPIRegistryEntry],
    table: str | None,
) -> KPIRegistryEntry | None:
    if explicit_kpi_id:
        for kpi in kpis:
            if kpi.id == explicit_kpi_id:
                return kpi
    context_kpi_id = analysis_context.semantic.matched_kpi_id if analysis_context and analysis_context.semantic else None
    if context_kpi_id:
        for kpi in kpis:
            if kpi.id == context_kpi_id:
                return kpi
    persisted = chart_spec.semantic_context.matched_kpi_id if chart_spec and chart_spec.semantic_context else None
    if persisted:
        for kpi in kpis:
            if kpi.id == persisted:
                return kpi
    context_kpi_label = analysis_context.semantic.matched_kpi_label if analysis_context and analysis_context.semantic else None
    if context_kpi_label:
        normalized_label = _normalize_text(context_kpi_label)
        for kpi in kpis:
            if normalized_label in {_normalize_text(kpi.id), _normalize_text(kpi.display_name)}:
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
        if analysis_context and analysis_context.semantic:
            semantic = analysis_context.semantic
            if table and table in semantic.marts and table in kpi.marts:
                score += 4
            score += len(set(semantic.required_columns).intersection(kpi.required_columns)) * 3
            score += len(set(semantic.metric_aliases).intersection(kpi.metric_aliases)) * 2
            if semantic.semantic_family and semantic.semantic_family == kpi.semantic_family:
                score += 3
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
    analysis_context = _analysis_context_from_request(request)
    semantic = analysis_context.semantic if analysis_context else None
    return (
        request.table
        or (request.chart_spec.table if request.chart_spec else None)
        or (analysis_context.table if analysis_context else None)
        or (semantic.marts[0] if semantic and semantic.marts else None)
        or (matched_kpi.marts[0] if matched_kpi and matched_kpi.marts else None)
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
    analysis_context = _build_analysis_context(request=request, matched_kpi=matched_kpi, table=table)
    profile = load_mart_profile(dataset_id, table)
    available_measures = measure_columns(profile)
    semantic = analysis_context.semantic if analysis_context else None
    strategy_context = analysis_context.strategy if analysis_context else None
    formula = (
        request.prediction_spec.formula
        if request.prediction_spec and request.prediction_spec.formula
        else (matched_kpi.formula if matched_kpi else None)
    )
    metric_candidates = [
        request.metric,
        request.prediction_spec.metric if request.prediction_spec else None,
        base_query.measures[0] if base_query and base_query.measures else None,
        semantic.metric_field_hint if semantic else None,
        *(semantic.required_columns if semantic else []),
        *(matched_kpi.required_columns if matched_kpi else []),
    ]
    metric = next((candidate for candidate in metric_candidates if candidate and candidate in available_measures), None)
    if metric is None and available_measures:
        metric = available_measures[0]
    if not metric and not formula:
        raise HTTPException(status_code=422, detail="A metric is required for predictive analysis")

    time_field_candidates = [
        request.time_field,
        request.prediction_spec.time_field if request.prediction_spec else None,
        base_query.time_field if base_query else None,
        semantic.time_field_hint if semantic else None,
    ]
    time_field = None
    for candidate in time_field_candidates:
        if not candidate:
            continue
        resolved_candidate = resolve_time_field(profile, candidate)
        if resolved_candidate:
            time_field = resolved_candidate
            break
    if time_field is None:
        time_field = resolve_time_field(profile)
    if not time_field:
        raise HTTPException(status_code=422, detail="A temporal field is required for predictive analysis")

    target = strategy_bundle.targets.get(matched_kpi.id) if matched_kpi else None
    display_label = (
        request.prediction_spec.display_label if request.prediction_spec else None
    ) or (semantic.matched_kpi_label if semantic else None) or (matched_kpi.display_name if matched_kpi else None) or metric
    metric_source = "formula" if formula else (request.prediction_spec.metric_source if request.prediction_spec is not None else "field")
    supporting_fields = _merge_unique(
        request.prediction_spec.supporting_fields if request.prediction_spec else [],
        semantic.required_columns if semantic else [],
        matched_kpi.required_columns if matched_kpi else [],
    )
    return PredictionSpec(
        mode=mode,  # type: ignore[arg-type]
        dataset_id=dataset_id,
        table=table,
        metric=(matched_kpi.id if formula and matched_kpi else (metric or (matched_kpi.id if matched_kpi else "metric_value"))),
        display_label=display_label,
        metric_source=metric_source,  # type: ignore[arg-type]
        formula=formula,
        aggregation=(request.prediction_spec.aggregation if request.prediction_spec else None) or (
            base_query.aggregation if base_query else None
        ) or "sum",
        time_field=time_field,
        time_grain=request.time_grain or (request.prediction_spec.time_grain if request.prediction_spec else None) or (
            base_query.time_grain if base_query else None
        ) or (semantic.default_grain if semantic else None) or "month",
        filters=request.filters or (request.prediction_spec.filters if request.prediction_spec else None) or (
            base_query.filters if base_query else None
        ) or _filters_from_chart_spec(request.chart_spec),
        supporting_fields=supporting_fields,
        horizon=request.horizon or (request.prediction_spec.horizon if request.prediction_spec else None) or 6,
        kpi_id=matched_kpi.id if matched_kpi else None,
        target_value=(
            request.prediction_spec.target_value if request.prediction_spec else None
        )
        or (strategy_context.target_value if strategy_context else None)
        or (target.target if target else None),
        target_direction=(
            request.prediction_spec.target_direction if request.prediction_spec else None
        )
        or (strategy_context.target_direction if strategy_context else None)
        or (target.direction if target else None),
        analysis_context=analysis_context,
    )


def _build_segment_spec(
    request: AnalysisRequest,
    *,
    dataset_id: str,
    table: str,
    matched_kpi: KPIRegistryEntry | None,
) -> SegmentSpec:
    profile = load_mart_profile(dataset_id, table)
    base_query = request.query_spec or (query_spec_from_chart_spec(request.chart_spec) if request.chart_spec else None)
    analysis_context = _build_analysis_context(request=request, matched_kpi=matched_kpi, table=table)
    semantic = analysis_context.semantic if analysis_context else None
    entity_candidates = [
        request.entity_field,
        request.segment_spec.entity_field if request.segment_spec else None,
        semantic.entity_field_hint if semantic else None,
        *_entity_candidates_for_family(semantic.semantic_family if semantic else None),
    ]
    entity_field = None
    for candidate in entity_candidates:
        if not candidate:
            continue
        resolved_candidate = resolve_entity_field(profile, candidate)
        if resolved_candidate:
            entity_field = resolved_candidate
            break
    if entity_field is None:
        entity_field = resolve_entity_field(profile)
    if not entity_field:
        raise HTTPException(status_code=422, detail="An entity field is required for segmentation")
    preferred_features = _merge_unique(
        request.features,
        request.segment_spec.features if request.segment_spec else [],
        semantic.required_columns if semantic else [],
        [base_query.measures[0]] if base_query and base_query.measures else [],
        matched_kpi.required_columns if matched_kpi else [],
    )
    return SegmentSpec(
        dataset_id=dataset_id,
        table=table,
        entity_field=entity_field,
        entity_label=_entity_label(entity_field),
        features=preferred_features,
        filters=request.filters or (request.segment_spec.filters if request.segment_spec else None) or _filters_from_chart_spec(request.chart_spec),
        cluster_count=request.cluster_count or (request.segment_spec.cluster_count if request.segment_spec else None) or 4,
        metric_focus=request.metric
        or (request.segment_spec.metric_focus if request.segment_spec else None)
        or (semantic.metric_field_hint if semantic else None)
        or (base_query.measures[0] if base_query and base_query.measures else None),
        analysis_context=analysis_context,
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
    analysis_context = _build_analysis_context(request=request, matched_kpi=matched_kpi, table=table)
    strategy_context = analysis_context.strategy if analysis_context else None
    semantic = analysis_context.semantic if analysis_context else None
    return StrategySpec(
        dataset_id=dataset_id,
        kpi_id=matched_kpi.id,
        kpi_label=(request.strategy_spec.kpi_label if request.strategy_spec else None)
        or (semantic.matched_kpi_label if semantic else None)
        or matched_kpi.display_name
        or matched_kpi.id,
        table=table,
        target_value=(request.strategy_spec.target_value if request.strategy_spec else None)
        or (strategy_context.target_value if strategy_context else None)
        or (target.target if target else None),
        direction=(request.strategy_spec.direction if request.strategy_spec else None)
        or (strategy_context.target_direction if strategy_context else None)
        or (target.direction if target else None),
        target_horizon=(request.strategy_spec.target_horizon if request.strategy_spec else None)
        or (strategy_context.target_horizon if strategy_context else None)
        or (target.horizon if target else None),
        time_grain=request.time_grain
        or (request.strategy_spec.time_grain if request.strategy_spec else None)
        or (semantic.default_grain if semantic else None)
        or _coerce_time_grain(matched_kpi.default_grain)
        or "month",
        horizon=request.horizon or (request.strategy_spec.horizon if request.strategy_spec else None) or 6,
        filters=request.filters or (request.strategy_spec.filters if request.strategy_spec else None) or _filters_from_chart_spec(request.chart_spec),
        analysis_context=analysis_context,
    )


def create_plan(request: AnalysisRequest, *, dataset_id: str) -> tuple[PlanSpec, KPIRegistryEntry | None]:
    strategy_bundle, kpis = _load_strategy_runtime()
    table_hint = request.table or (request.chart_spec.table if request.chart_spec else None)
    request_context = _analysis_context_from_request(request)
    matched_kpi = _match_kpi(
        message=request.message,
        chart_spec=request.chart_spec,
        explicit_kpi_id=request.kpi_id or (request.strategy_spec.kpi_id if request.strategy_spec else None),
        analysis_context=request_context,
        kpis=kpis,
        table=table_hint,
    )
    task_type = _detect_task_type(request, matched_kpi)
    table = _resolve_table(request, matched_kpi)
    analysis_context = _build_analysis_context(request=request, matched_kpi=matched_kpi, table=table)
    if task_type != "strategy_risk" and not table:
        raise HTTPException(status_code=422, detail="A mart is required for this analysis request")

    tasks: list[AgentTaskSpec] = []
    if task_type in {"query", "insight"}:
        query_spec = request.query_spec or (query_spec_from_chart_spec(request.chart_spec) if request.chart_spec else None)
        if query_spec is None and table:
            query_spec = QuerySpec(dataset_id=dataset_id, table=table, analysis_context=analysis_context)
        elif query_spec is not None:
            query_spec = query_spec.model_copy(update={"analysis_context": query_spec.analysis_context or analysis_context})
        primary_task = AgentTaskSpec(
            task_type="query" if task_type == "query" else "insight",
            agent_role="viz_agent",
            title="Build descriptive view",
            query_spec=query_spec,
            insight_spec=InsightSpec(source_task=task_type),
        )
        tasks.append(primary_task)
    elif task_type == "profile":
        primary_task = AgentTaskSpec(
            task_type="profile",
            agent_role="profiling_agent",
            title="Profile mart capabilities",
            insight_spec=InsightSpec(source_task="profile"),
        )
        tasks.append(primary_task)
    elif task_type in {"forecast", "anomaly"}:
        primary_task = AgentTaskSpec(
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
        tasks.append(primary_task)
    elif task_type == "segment":
        primary_task = AgentTaskSpec(
            task_type="segment",
            agent_role="ml_agent",
            title="Run segmentation analysis",
            segment_spec=_build_segment_spec(request, dataset_id=dataset_id, table=table or "", matched_kpi=matched_kpi),
            insight_spec=InsightSpec(source_task="segment"),
        )
        tasks.append(primary_task)
    elif task_type == "strategy_risk":
        if matched_kpi is None:
            raise HTTPException(status_code=422, detail="A matched KPI is required for strategy risk analysis")
        risk_prediction_task: AgentTaskSpec | None = None
        if table:
            risk_prediction_task = AgentTaskSpec(
                task_type="strategy_risk",
                agent_role="ml_agent",
                title="Project KPI trend",
                prediction_spec=_build_prediction_spec(
                    request,
                    dataset_id=dataset_id,
                    table=table,
                    matched_kpi=matched_kpi,
                    strategy_bundle=strategy_bundle,
                    mode="risk",
                ),
            )
            tasks.append(risk_prediction_task)
        primary_task = AgentTaskSpec(
            task_type="strategy_risk",
            agent_role="strategy_agent",
            title="Estimate KPI target risk",
            depends_on_task_ids=[risk_prediction_task.task_id] if risk_prediction_task else [],
            strategy_spec=_build_strategy_spec(
                request=request,
                dataset_id=dataset_id,
                table=table,
                matched_kpi=matched_kpi,
                strategy_bundle=strategy_bundle,
            ),
            insight_spec=InsightSpec(source_task="strategy_risk", kpi_id=matched_kpi.id),
        )
        tasks.append(primary_task)
    else:
        primary_task = None

    tasks.append(
        AgentTaskSpec(
            task_type="insight",
            agent_role="insight_agent",
            title="Synthesize next-step insights",
            depends_on_task_ids=[primary_task.task_id] if primary_task else [],
            insight_spec=InsightSpec(source_task=task_type, kpi_id=matched_kpi.id if matched_kpi else None),
        )
    )
    plan = PlanSpec(
        dataset_id=dataset_id,
        table=table,
        user_message=request.message or task_type.replace("_", " "),
        primary_task=task_type,
        route_reason=(
            f"Primary task '{task_type}' routed from {(analysis_context.source if analysis_context else 'api')} context"
            f"{f' with KPI {matched_kpi.display_name or matched_kpi.id}' if matched_kpi else ''}."
        ),
        matched_kpi_id=matched_kpi.id if matched_kpi else None,
        matched_kpi_label=matched_kpi.display_name or matched_kpi.id if matched_kpi else None,
        analysis_context=analysis_context,
        tasks=tasks,
        suggested_follow_ups=[
            action
            for action in (
                "forecast" if task_type != "forecast" and table else None,
                "anomaly" if task_type not in {"anomaly", "strategy_risk"} and table else None,
                "segment" if task_type != "segment" and table else None,
                "strategy_risk" if matched_kpi and task_type != "strategy_risk" else None,
            )
            if action
        ],
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
                    "lower_bound": point.lower,
                    "upper_bound": point.upper,
                    "target_value": point.target_value,
                    "is_forecast": point.is_forecast,
                    "anomaly_flag": point.anomaly_flag,
                }
                for point in prediction.points
            ]
            chart_spec = None
            if task.prediction_spec.metric_source == "field" and not task.prediction_spec.formula:
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
                    analysis_context=task.prediction_spec.analysis_context,
                ),
                primary_view=NormalizedDataView(
                    chart_spec=chart_spec,
                    columns=[
                        task.prediction_spec.time_field,
                        task.prediction_spec.metric,
                        "actual_value",
                        "forecast_value",
                        "lower_bound",
                        "upper_bound",
                        "target_value",
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
                query_spec=QuerySpec(
                    dataset_id=dataset_id,
                    table=task.segment_spec.table,
                    dimensions=[task.segment_spec.entity_field],
                    measures=[task.segment_spec.metric_focus] if task.segment_spec.metric_focus else [],
                    filters=task.segment_spec.filters,
                    kpi_id=task.segment_spec.analysis_context.semantic.matched_kpi_id
                    if task.segment_spec.analysis_context and task.segment_spec.analysis_context.semantic
                    else None,
                    analysis_context=task.segment_spec.analysis_context,
                ),
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

    def execute(
        self,
        task: AgentTaskSpec,
        _: AnalysisRequest,
        db: Session,
        dataset_id: str,
        table: str | None,
        *,
        prediction: Any | None = None,
    ) -> AgentExecution:
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
        resolved_prediction = prediction if prediction is not None else self._predict_kpi_trend(
            dataset_id=dataset_id,
            kpi=kpi,
            strategy_spec=strategy_spec,
            db=db,
            target_value=strategy_spec.target_value if strategy_spec.target_value is not None else (target.target if target else None),
            target_direction=strategy_spec.direction if strategy_spec.direction is not None else (target.direction if target else None),
        )
        if not isinstance(current_value, (float, int)) and resolved_prediction is not None:
            observed_values = [
                point.actual
                for point in resolved_prediction.points
                if not point.is_forecast and point.actual is not None
            ]
            current_value = observed_values[-1] if observed_values else None
        strategy = build_strategy_risk_summary(
            kpi_id=kpi.id,
            kpi_label=strategy_spec.kpi_label or kpi.display_name or kpi.id,
            target_value=strategy_spec.target_value if strategy_spec.target_value is not None else (target.target if target else None),
            current_value=current_value if isinstance(current_value, (float, int)) else None,
            prediction=resolved_prediction,
            direction=strategy_spec.direction if strategy_spec.direction is not None else (target.direction if target else None),
            target_horizon=strategy_spec.target_horizon if strategy_spec.target_horizon is not None else (target.horizon if target else None),
            recommended_actions=[
                *(
                    strategy_spec.analysis_context.strategy.triggered_rule_actions
                    if strategy_spec.analysis_context and strategy_spec.analysis_context.strategy
                    else []
                ),
                "Inspect the KPI in analytics and compare the weakest business slices."
                if resolved_prediction is not None
                else "Review KPI coverage and historical trend inputs before relying on risk estimates.",
            ],
            supporting_details=[
                f"Primary mart: {strategy_spec.table}" if strategy_spec.table else "",
                f"Forecast basis: {resolved_prediction.observed_points} observed periods." if resolved_prediction is not None else "",
                *(
                    strategy_spec.analysis_context.strategy.triggered_rules
                    if strategy_spec.analysis_context and strategy_spec.analysis_context.strategy
                    else []
                ),
            ],
        )

        primary_view = None
        if resolved_prediction is not None:
            primary_view = NormalizedDataView(
                chart_spec=None,
                columns=[
                    resolved_prediction.time_field,
                    "metric_value",
                    "actual_value",
                    "forecast_value",
                    "lower_bound",
                    "upper_bound",
                    "is_forecast",
                    "target_value",
                ],
                rows=[
                    {
                        resolved_prediction.time_field: point.label,
                        "metric_value": point.actual if point.actual is not None else point.forecast,
                        "actual_value": point.actual,
                        "forecast_value": point.forecast,
                        "lower_bound": point.lower,
                        "upper_bound": point.upper,
                        "is_forecast": point.is_forecast,
                        "target_value": point.target_value,
                    }
                    for point in resolved_prediction.points
                ],
                summary=strategy.explanation,
            )
        return AgentExecution(strategy=strategy, prediction=resolved_prediction, primary_view=primary_view)

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
        mart = strategy_spec.table or (kpi.marts[0] if kpi.marts else None)
        if mart is None:
            return None
        profile = load_mart_profile(dataset_id, mart)
        time_field = resolve_time_field(profile)
        if not time_field:
            return None
        available_measures = set(measure_columns(profile))
        fallback_metric = next(
            (
                candidate
                for candidate in (
                    strategy_spec.analysis_context.semantic.metric_field_hint
                    if strategy_spec.analysis_context and strategy_spec.analysis_context.semantic
                    else None,
                    *(kpi.required_columns or []),
                )
                if candidate and candidate in available_measures
            ),
            None,
        )
        candidate_specs = [
            PredictionSpec(
                mode="risk",
                dataset_id=dataset_id,
                table=mart,
                metric=kpi.id,
                display_label=kpi.display_name or kpi.id,
                metric_source="formula",
                formula=kpi.formula,
                aggregation="sum",
                time_field=time_field,
                time_grain=strategy_spec.time_grain,
                supporting_fields=kpi.required_columns,
                horizon=strategy_spec.horizon,
                kpi_id=kpi.id,
                target_value=target_value,
                target_direction=target_direction if target_direction in {"up", "down"} else None,
                analysis_context=strategy_spec.analysis_context,
            )
        ]
        if fallback_metric:
            candidate_specs.append(
                PredictionSpec(
                    mode="risk",
                    dataset_id=dataset_id,
                    table=mart,
                    metric=fallback_metric,
                    display_label=kpi.display_name or kpi.id,
                    metric_source="field",
                    aggregation="sum",
                    time_field=time_field,
                    time_grain=strategy_spec.time_grain,
                    horizon=strategy_spec.horizon,
                    kpi_id=kpi.id,
                    target_value=target_value,
                    target_direction=target_direction if target_direction in {"up", "down"} else None,
                    analysis_context=strategy_spec.analysis_context,
                )
            )
        for candidate in candidate_specs:
            try:
                return run_prediction_analysis(candidate, db)
            except HTTPException:
                continue
        return None


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
    if query_spec is not None and query_spec.analysis_context is None:
        query_spec = query_spec.model_copy(update={"analysis_context": plan.analysis_context})
    primary_view: NormalizedDataView | None = None
    prediction = None
    segmentation = None
    strategy = None
    completed_task_ids: set[str] = set()
    execution_trace: list[dict[str, Any]] = []
    meta: dict[str, Any] = {
        "analysis_source": plan.analysis_context.source if plan.analysis_context else "api",
        "execution_trace": execution_trace,
    }

    for task in plan.tasks:
        unmet_dependencies = [task_id for task_id in task.depends_on_task_ids if task_id not in completed_task_ids]
        if unmet_dependencies:
            raise HTTPException(
                status_code=500,
                detail=f"Analysis plan dependency failure for task '{task.title}': {', '.join(unmet_dependencies)}",
            )
        if task.agent_role == "viz_agent":
            result = viz_agent.execute(task, request, db, dataset_id, plan.table)
        elif task.agent_role == "profiling_agent":
            result = profiling_agent.execute(task, request, db, dataset_id, plan.table)
        elif task.agent_role == "ml_agent":
            try:
                result = ml_agent.execute(task, request, db, dataset_id, plan.table)
            except HTTPException as exc:
                if task.task_type != "strategy_risk":
                    raise
                warning_key = f"{task.task_id}_warning"
                meta[warning_key] = exc.detail
                execution_trace.append(
                    {
                        "task_id": task.task_id,
                        "task_type": task.task_type,
                        "agent_role": task.agent_role,
                        "title": task.title,
                        "depends_on_task_ids": task.depends_on_task_ids,
                        "status": "skipped",
                        "detail": exc.detail,
                    }
                )
                completed_task_ids.add(task.task_id)
                continue
        elif task.agent_role == "strategy_agent":
            result = strategy_agent.execute(task, request, db, dataset_id, plan.table, prediction=prediction)
        else:
            if task.agent_role == "insight_agent":
                execution_trace.append(
                    {
                        "task_id": task.task_id,
                        "task_type": task.task_type,
                        "agent_role": task.agent_role,
                        "title": task.title,
                        "depends_on_task_ids": task.depends_on_task_ids,
                        "status": "completed",
                    }
                )
                completed_task_ids.add(task.task_id)
            continue

        query_spec = result.query_spec or query_spec
        primary_view = result.primary_view or primary_view
        prediction = result.prediction or prediction
        segmentation = result.segmentation or segmentation
        strategy = result.strategy or strategy
        meta.update(result.meta)
        execution_trace.append(
            {
                "task_id": task.task_id,
                "task_type": task.task_type,
                "agent_role": task.agent_role,
                "title": task.title,
                "depends_on_task_ids": task.depends_on_task_ids,
                "status": "completed",
            }
        )
        completed_task_ids.add(task.task_id)

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
