"use client";

import type { AnalysisContext, AnalysisResponse, DecisionTaskType } from "@/lib/types/analysis";
import type { ChartSemanticContext, ChartSpecV1 } from "@/lib/types/chartspec";
import type { ChatFocusContext } from "@/lib/types/chat";

type ChartFocusInput = {
  title: string;
  table?: string | null;
  kpiId?: string | null;
  chartSpec?: ChartSpecV1 | null;
  chartRows?: Array<Record<string, unknown>> | null;
  analysisContext?: AnalysisContext | null;
  semanticContext?: ChartSemanticContext | null;
  breadcrumbs?: string[];
};

type AnalysisFocusInput = ChartFocusInput & {
  analysis: AnalysisResponse;
  task: DecisionTaskType;
};

type KpiFocusInput = {
  title: string;
  table?: string | null;
  kpiId?: string | null;
  analysisContext?: AnalysisContext | null;
  breadcrumbs?: string[];
  summary?: string | null;
};

function firstNonEmpty(...values: Array<string | null | undefined>): string | null {
  for (const value of values) {
    const trimmed = value?.trim();
    if (trimmed) {
      return trimmed;
    }
  }
  return null;
}

function analysisSummary(analysis: AnalysisResponse | null | undefined): string | null {
  if (!analysis) {
    return null;
  }
  if (analysis.insight_cards[0]?.summary) {
    return analysis.insight_cards[0].summary;
  }
  if (analysis.prediction?.explanation) {
    return analysis.prediction.explanation;
  }
  if (analysis.strategy?.explanation) {
    return analysis.strategy.explanation;
  }
  if (analysis.segmentation?.comparison_highlights[0]) {
    return analysis.segmentation.comparison_highlights[0];
  }
  return analysis.primary_view?.summary ?? null;
}

export function buildChartFocusContext({
  title,
  table,
  kpiId,
  chartSpec,
  chartRows,
  analysisContext,
  semanticContext,
  breadcrumbs,
}: ChartFocusInput): ChatFocusContext {
  return {
    focus_type: "chart",
    title,
    table: table ?? chartSpec?.table ?? analysisContext?.table ?? null,
    kpi_id:
      kpiId ??
      analysisContext?.semantic?.matched_kpi_id ??
      chartSpec?.semantic_context?.matched_kpi_id ??
      semanticContext?.matched_kpi_id ??
      null,
    chart_spec: chartSpec ?? null,
    chart_rows: chartRows ?? [],
    analysis_context: analysisContext ?? chartSpec?.semantic_context?.analysis_context ?? null,
    semantic_context: semanticContext ?? chartSpec?.semantic_context ?? null,
    breadcrumbs: breadcrumbs ?? [],
    summary: firstNonEmpty(
      analysisContext?.semantic?.matched_kpi_label,
      chartSpec?.semantic_context?.matched_kpi_label,
      semanticContext?.matched_kpi_label,
    ),
  };
}

export function buildAnalysisFocusContext({
  title,
  table,
  kpiId,
  chartSpec,
  chartRows,
  analysisContext,
  semanticContext,
  analysis,
  task,
  breadcrumbs,
}: AnalysisFocusInput): ChatFocusContext {
  const base = buildChartFocusContext({
    title,
    table,
    kpiId,
    chartSpec,
    chartRows,
    analysisContext: analysisContext ?? analysis.plan_spec.analysis_context ?? null,
    semanticContext,
    breadcrumbs,
  });
  return {
    ...base,
    focus_type: "analysis_result",
    active_task: task,
    summary: analysisSummary(analysis),
  };
}

export function buildKpiFocusContext({
  title,
  table,
  kpiId,
  analysisContext,
  breadcrumbs,
  summary,
}: KpiFocusInput): ChatFocusContext {
  return {
    focus_type: "kpi",
    title,
    table: table ?? analysisContext?.table ?? null,
    kpi_id: kpiId ?? analysisContext?.semantic?.matched_kpi_id ?? null,
    analysis_context: analysisContext ?? null,
    semantic_context: null,
    breadcrumbs: breadcrumbs ?? [],
    summary: summary ?? analysisContext?.strategy?.status ?? null,
  };
}

export function contextualPromptSuggestions(focus: ChatFocusContext): string[] {
  if (focus.focus_type === "analysis_result") {
    if (focus.active_task === "forecast") {
      return [
        "Explain this forecast",
        "What is driving the projected change?",
        "Which slice should I inspect next?",
      ];
    }
    if (focus.active_task === "anomaly") {
      return [
        "What is driving this anomaly?",
        "Which entities should I compare next?",
        "Is this anomaly broad-based or isolated?",
      ];
    }
    if (focus.active_task === "segment") {
      return [
        "Compare the strongest cluster to the weakest",
        "What differentiates these clusters?",
        "Which cluster should I drill into first?",
      ];
    }
    if (focus.active_task === "strategy_risk") {
      return [
        "Why is this KPI at risk?",
        "What should I look at next?",
        "Which business slice is most likely driving the risk?",
      ];
    }
  }

  if (focus.focus_type === "kpi") {
    return [
      "Explain this KPI in business terms",
      "Why might this KPI move off target?",
      "What analysis should I run next?",
    ];
  }

  if (focus.focus_type === "drill_state") {
    return [
      "What changed after this drill?",
      "Which categories are driving this view?",
      "What should I drill into next?",
    ];
  }

  return [
    "Explain this chart",
    "What changed here?",
    "What should I look at next?",
  ];
}
