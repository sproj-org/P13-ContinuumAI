"use client";

import type { AnalysisContext, AnalysisResponse, DecisionTaskType } from "@/lib/types/analysis";
import type { ChartSemanticContext, ChartSpecV1 } from "@/lib/types/chartspec";
import type { ChatFocusContext, ChatQuickPrompt } from "@/lib/types/chat";

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
    analysis_result: null,
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
    analysis_result: analysis,
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
    analysis_result: null,
    breadcrumbs: breadcrumbs ?? [],
    summary: summary ?? analysisContext?.strategy?.status ?? null,
  };
}

function prompt(
  label: string,
  promptText: string,
  promptKind: ChatQuickPrompt["prompt_kind"],
  preferredRoute: ChatQuickPrompt["preferred_route"],
  focus: ChatFocusContext,
  options?: Partial<Pick<ChatQuickPrompt, "artifact_action" | "analysis_result_type" | "task_type">>,
): ChatQuickPrompt {
  return {
    label,
    prompt_text: promptText,
    prompt_kind: promptKind,
    preferred_route: preferredRoute,
    focus_type: focus.focus_type,
    analysis_result_type: focus.active_task ?? null,
    artifact_action: options?.artifact_action ?? null,
    task_type: options?.task_type ?? null,
  };
}

export function contextualPromptSuggestions(focus: ChatFocusContext): ChatQuickPrompt[] {
  if (focus.focus_type === "analysis_result") {
    if (focus.active_task === "forecast") {
      return [
        prompt("Explain this forecast", "Explain this forecast", "ask", "explain", focus, {
          artifact_action: "forecast_drivers",
        }),
        prompt("What is driving the projected change?", "What is driving the projected change?", "follow_up", "explain", focus, {
          artifact_action: "forecast_drivers",
        }),
        prompt("What should I inspect next?", "Which slice should I inspect next?", "follow_up", "guidance", focus, {
          artifact_action: "next_step",
        }),
      ];
    }
    if (focus.active_task === "anomaly") {
      return [
        prompt("What is driving this anomaly?", "What is driving this anomaly?", "follow_up", "explain", focus, {
          artifact_action: "anomaly_driver",
        }),
        prompt("Which entities should I compare next?", "Which entities should I compare next?", "follow_up", "guidance", focus, {
          artifact_action: "next_step",
        }),
        prompt("Is this anomaly broad-based or isolated?", "Is this anomaly broad-based or isolated?", "follow_up", "explain", focus, {
          artifact_action: "anomaly_scope",
        }),
      ];
    }
    if (focus.active_task === "segment") {
      return [
        prompt("Compare strongest vs weakest cluster", "Compare the strongest cluster to the weakest", "compare", "explain", focus, {
          artifact_action: "segment_compare_extremes",
        }),
        prompt("What differentiates these clusters?", "What differentiates these clusters?", "compare", "explain", focus, {
          artifact_action: "segment_differentiators",
        }),
        prompt("Which cluster should I drill into first?", "Which cluster should I drill into first?", "drill", "guidance", focus, {
          artifact_action: "segment_drill_priority",
        }),
      ];
    }
    if (focus.active_task === "strategy_risk") {
      return [
        prompt("Why is this KPI at risk?", "Why is this KPI at risk?", "follow_up", "explain", focus, {
          artifact_action: "risk_driver",
        }),
        prompt("What should I look at next?", "What should I look at next?", "follow_up", "guidance", focus, {
          artifact_action: "risk_next_step",
        }),
        prompt("Which business slice is driving the risk?", "Which business slice is most likely driving the risk?", "follow_up", "explain", focus, {
          artifact_action: "risk_slice",
        }),
      ];
    }
  }

  if (focus.focus_type === "kpi") {
    return [
      prompt("Explain this KPI", "Explain this KPI in business terms", "ask", "explain", focus, {
        artifact_action: "explain_kpi",
      }),
      prompt("Why might this KPI move off target?", "Why might this KPI move off target?", "follow_up", "guidance", focus, {
        artifact_action: "risk_driver",
      }),
      prompt("What analysis should I run next?", "What analysis should I run next?", "follow_up", "guidance", focus, {
        artifact_action: "next_step",
      }),
    ];
  }

  if (focus.focus_type === "drill_state") {
    return [
      prompt("What changed after this drill?", "What changed after this drill?", "follow_up", "explain", focus, {
        artifact_action: "chart_change",
      }),
      prompt("Which categories are driving this view?", "Which categories are driving this view?", "follow_up", "explain", focus, {
        artifact_action: "chart_change",
      }),
      prompt("What should I drill into next?", "What should I drill into next?", "drill", "guidance", focus, {
        artifact_action: "drill_next",
      }),
    ];
  }

  return [
    prompt("Explain this chart", "Explain this chart", "ask", "explain", focus, {
      artifact_action: "explain_chart",
    }),
    prompt("What changed here?", "What changed here?", "follow_up", "explain", focus, {
      artifact_action: "chart_change",
    }),
    prompt("What should I look at next?", "What should I look at next?", "follow_up", "guidance", focus, {
      artifact_action: "next_step",
    }),
  ];
}
