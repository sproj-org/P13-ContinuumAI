"use client";

import { useEffect, useEffectEvent, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  BrainCircuit,
  Loader2,
  Radar,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";

import ContextualAssistant from "@/components/workspace/ContextualAssistant";
import { ApiRequestError, apiClient } from "@/lib/api";
import { mergeChartSemanticContext } from "@/lib/chart-display";
import { buildAnalysisFocusContext, buildChartFocusContext, buildKpiFocusContext, contextualPromptSuggestions } from "@/lib/contextual-focus";
import type {
  AnalysisContext,
  AnalysisRequest,
  AnalysisResponse,
  AnalysisSource,
  DecisionTaskType,
  PredictionSummary,
  SemanticContextSpec,
  StrategyContextSpec,
} from "@/lib/types/analysis";
import type { ChartSemanticContext, ChartSpecV1 } from "@/lib/types/chartspec";

interface DecisionIntelligencePanelProps {
  datasetId: string;
  martId?: string | null;
  chartSpec?: ChartSpecV1 | null;
  chartRows?: Array<Record<string, unknown>> | null;
  chartTitle?: string | null;
  kpiId?: string | null;
  analysisSource?: AnalysisSource;
  analysisContext?: AnalysisContext | null;
  onChartSpecChange?: (nextChartSpec: ChartSpecV1) => void;
}

type TaskRunState = {
  runId: number;
  isLoading: boolean;
  analysis: AnalysisResponse | null;
  error: string | null;
};

type TaskPanelState = {
  selectedTask: DecisionTaskType;
  displayedTask: DecisionTaskType;
  runningTask: DecisionTaskType | null;
  lastCompletedTask: DecisionTaskType | null;
  tasks: Record<DecisionTaskType, TaskRunState>;
};

const TASK_CONFIG: Record<DecisionTaskType, { label: string; description: string; icon: LucideIcon; accent: string }> = {
  forecast: {
    label: "Forecast",
    description: "Project the KPI or metric trend across the next horizon.",
    icon: TrendingUp,
    accent: "text-indigo-700",
  },
  anomaly: {
    label: "Anomalies",
    description: "Surface spikes, dips, and unusual breaks in the current metric.",
    icon: AlertTriangle,
    accent: "text-rose-700",
  },
  segment: {
    label: "Segments",
    description: "Cluster the most relevant entities into explainable cohorts.",
    icon: BrainCircuit,
    accent: "text-violet-700",
  },
  strategy_risk: {
    label: "KPI Risk",
    description: "Estimate target-attainment risk with strategy and forecast context.",
    icon: Radar,
    accent: "text-amber-700",
  },
};

function createTaskState(): Record<DecisionTaskType, TaskRunState> {
  return {
    forecast: { runId: 0, isLoading: false, analysis: null, error: null },
    anomaly: { runId: 0, isLoading: false, analysis: null, error: null },
    segment: { runId: 0, isLoading: false, analysis: null, error: null },
    strategy_risk: { runId: 0, isLoading: false, analysis: null, error: null },
  };
}

function createPanelState(defaultTask: DecisionTaskType): TaskPanelState {
  return {
    selectedTask: defaultTask,
    displayedTask: defaultTask,
    runningTask: null,
    lastCompletedTask: null,
    tasks: createTaskState(),
  };
}

function mergeUnique(values: Array<string[] | undefined | null>): string[] {
  const output: string[] = [];
  for (const list of values) {
    for (const item of list ?? []) {
      const trimmed = item.trim();
      if (trimmed && !output.includes(trimmed)) {
        output.push(trimmed);
      }
    }
  }
  return output;
}

function formatMetric(value: unknown): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
}

function formatPercent(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return `${value.toFixed(1)}%`;
}

function buildSemanticContext(
  chartSpec: ChartSpecV1 | null | undefined,
  chartTitle: string | null | undefined,
  table: string | null,
  kpiId: string | null,
): SemanticContextSpec {
  const semantic = chartSpec?.semantic_context;
  const chartMetric = chartSpec?.encoding.y[0]?.field ?? null;
  const chartDimension = chartSpec?.encoding.x.field ?? null;
  return {
    matched_kpi_id: kpiId ?? semantic?.matched_kpi_id ?? null,
    matched_kpi_label: semantic?.matched_kpi_label ?? chartTitle ?? null,
    semantic_family: semantic?.semantic_family ?? null,
    marts: mergeUnique([[table ?? ""], semantic?.analysis_context?.semantic?.marts, [chartSpec?.table ?? ""]]),
    required_columns: mergeUnique([
      semantic?.analysis_context?.semantic?.required_columns,
      chartMetric ? [chartMetric] : [],
    ]),
    dimensions: mergeUnique([
      semantic?.analysis_context?.semantic?.dimensions,
      chartDimension ? [chartDimension] : [],
      semantic?.preferred_drill_path,
    ]),
    metric_aliases: mergeUnique([semantic?.analysis_context?.semantic?.metric_aliases]),
    business_concepts: mergeUnique([semantic?.analysis_context?.semantic?.business_concepts]),
    preferred_drill_path: mergeUnique([
      semantic?.analysis_context?.semantic?.preferred_drill_path,
      semantic?.preferred_drill_path,
    ]),
    mart_hierarchy: mergeUnique([
      semantic?.analysis_context?.semantic?.mart_hierarchy,
      semantic?.mart_hierarchy,
    ]),
    terminal_dimensions: mergeUnique([
      semantic?.analysis_context?.semantic?.terminal_dimensions,
      semantic?.terminal_dimensions,
    ]),
    disallowed_drill_dimensions: mergeUnique([semantic?.analysis_context?.semantic?.disallowed_drill_dimensions]),
    preferred_chart_types: mergeUnique([
      semantic?.analysis_context?.semantic?.preferred_chart_types as string[] | undefined,
      chartSpec?.chart.type ? [chartSpec.chart.type] : [],
    ]) as SemanticContextSpec["preferred_chart_types"],
    default_grain: semantic?.analysis_context?.semantic?.default_grain ?? null,
    metric_field_hint: semantic?.analysis_context?.semantic?.metric_field_hint ?? chartMetric,
    entity_field_hint: semantic?.analysis_context?.semantic?.entity_field_hint ?? null,
    time_field_hint:
      semantic?.analysis_context?.semantic?.time_field_hint ??
      (chartSpec?.chart.type === "line" ? chartDimension : null),
  };
}

function mergeStrategyContext(
  base: StrategyContextSpec | null | undefined,
  override: StrategyContextSpec | null | undefined,
): StrategyContextSpec | null {
  if (!base && !override) {
    return null;
  }
  return {
    target_value: override?.target_value ?? base?.target_value ?? null,
    target_direction: override?.target_direction ?? base?.target_direction ?? null,
    target_horizon: override?.target_horizon ?? base?.target_horizon ?? null,
    current_value: override?.current_value ?? base?.current_value ?? null,
    variance: override?.variance ?? base?.variance ?? null,
    status: override?.status ?? base?.status ?? null,
    triggered_rules: mergeUnique([base?.triggered_rules, override?.triggered_rules]),
    triggered_rule_actions: mergeUnique([base?.triggered_rule_actions, override?.triggered_rule_actions]),
    provenance: { ...(base?.provenance ?? {}), ...(override?.provenance ?? {}) },
  };
}

function formatError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    return error.hint ? `${error.message} ${error.hint}` : error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Analysis request failed.";
}

function buildSemanticPatch(
  response: AnalysisResponse,
  resolvedContext: AnalysisContext,
  resolvedKpiId: string | null,
): Partial<ChartSemanticContext> {
  const semanticContext = response.plan_spec.analysis_context?.semantic ?? resolvedContext.semantic ?? null;
  const patch: Partial<ChartSemanticContext> = {
    matched_kpi_id: response.plan_spec.matched_kpi_id ?? resolvedKpiId ?? semanticContext?.matched_kpi_id ?? null,
    matched_kpi_label: response.plan_spec.matched_kpi_label ?? semanticContext?.matched_kpi_label ?? null,
    semantic_family: semanticContext?.semantic_family ?? null,
    preferred_drill_path: semanticContext?.preferred_drill_path ?? [],
    mart_hierarchy: semanticContext?.mart_hierarchy ?? [],
    terminal_dimensions: semanticContext?.terminal_dimensions ?? [],
    analysis_context: response.plan_spec.analysis_context ?? resolvedContext,
  };

  if (response.prediction) {
    patch.prediction_context = {
      mode: response.prediction.mode,
      metric: response.prediction.metric,
      display_label: response.prediction.display_label ?? null,
      time_field: response.prediction.time_field,
      time_grain: response.prediction.time_grain,
      horizon: response.prediction.horizon,
      risk_band: response.prediction.risk_band ?? null,
      kpi_id: resolvedKpiId,
    };
  }
  if (response.segmentation) {
    patch.segmentation_context = {
      entity_field: response.segmentation.entity_field,
      entity_label: response.segmentation.entity_label ?? null,
      features: response.segmentation.features,
      cluster_count: response.segmentation.cluster_count,
    };
  }
  return patch;
}

function PredictionBars({ prediction }: { prediction: PredictionSummary }) {
  const values = prediction.points
    .slice(-8)
    .map((point) => point.forecast ?? point.actual)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));

  if (values.length === 0) {
    return null;
  }

  const maxValue = Math.max(...values, 1);
  return (
    <div className="mt-3 flex h-16 items-end gap-1 rounded-xl bg-slate-50 px-3 py-2">
      {prediction.points.slice(-8).map((point) => {
        const value = point.forecast ?? point.actual;
        const height = typeof value === "number" ? Math.max((value / maxValue) * 100, 8) : 8;
        return (
          <div key={`${point.label}-${point.forecast ?? point.actual ?? "empty"}`} className="flex flex-1 flex-col items-center gap-1">
            <div
              className={`w-full rounded-t-md ${
                point.anomaly_flag
                  ? "bg-rose-400"
                  : point.is_forecast
                    ? "bg-indigo-400"
                    : "bg-slate-400"
              }`}
              style={{ height: `${height}%` }}
            />
            <span className="text-[10px] text-slate-500">{point.label}</span>
          </div>
        );
      })}
    </div>
  );
}

export default function DecisionIntelligencePanel({
  datasetId,
  martId,
  chartSpec,
  chartRows,
  chartTitle,
  kpiId,
  analysisSource = "api",
  analysisContext,
  onChartSpecChange,
}: DecisionIntelligencePanelProps) {
  const [panelStateByContext, setPanelStateByContext] = useState<Record<string, TaskPanelState>>({});
  const [horizon, setHorizon] = useState(6);
  const [clusterCount, setClusterCount] = useState(4);
  const runIdRef = useRef(0);
  const autoRunSeedRef = useRef<string | null>(null);

  const resolvedTable = martId || chartSpec?.table || analysisContext?.table || chartSpec?.semantic_context?.analysis_context?.table || null;
  const resolvedKpiId =
    kpiId ||
    analysisContext?.semantic?.matched_kpi_id ||
    chartSpec?.semantic_context?.analysis_context?.semantic?.matched_kpi_id ||
    chartSpec?.semantic_context?.matched_kpi_id ||
    null;
  const stableKpiId = kpiId ?? analysisContext?.semantic?.matched_kpi_id ?? null;
  const stableXAxisField = chartSpec?.encoding.x.field ?? "x";
  const stableMetricField = chartSpec?.encoding.y[0]?.field ?? "metric";
  const stableContextKey = useMemo(
    () =>
      [
        analysisSource,
        martId ?? chartSpec?.table ?? analysisContext?.table ?? "none",
        stableKpiId ?? "none",
        stableXAxisField,
        stableMetricField,
        chartTitle ?? "untitled",
      ].join("|"),
    [analysisContext?.table, analysisSource, chartSpec?.table, chartTitle, martId, stableKpiId, stableMetricField, stableXAxisField],
  );

  const resolvedAnalysisContext = useMemo<AnalysisContext>(() => {
    const persistedContext = chartSpec?.semantic_context?.analysis_context ?? null;
    const mergedSemantic = buildSemanticContext(chartSpec, chartTitle, resolvedTable, resolvedKpiId);
    return {
      source: analysisContext?.source ?? persistedContext?.source ?? analysisSource,
      chart_title: analysisContext?.chart_title ?? persistedContext?.chart_title ?? chartTitle ?? null,
      chart_family:
        analysisContext?.chart_family ??
        persistedContext?.chart_family ??
        chartSpec?.semantic_context?.chart_family ??
        chartSpec?.chart.type ??
        null,
      table: analysisContext?.table ?? persistedContext?.table ?? resolvedTable,
      semantic: {
        ...mergedSemantic,
        ...(persistedContext?.semantic ?? {}),
        ...(analysisContext?.semantic ?? {}),
        matched_kpi_id: resolvedKpiId ?? mergedSemantic.matched_kpi_id ?? null,
        matched_kpi_label:
          analysisContext?.semantic?.matched_kpi_label ??
          persistedContext?.semantic?.matched_kpi_label ??
          chartSpec?.semantic_context?.matched_kpi_label ??
          chartTitle ??
          null,
      },
      strategy: mergeStrategyContext(persistedContext?.strategy ?? null, analysisContext?.strategy ?? null),
    };
  }, [analysisContext, analysisSource, chartSpec, chartTitle, resolvedKpiId, resolvedTable]);

  const disabledTasks = useMemo<Record<DecisionTaskType, boolean>>(
    () => ({
      forecast: !Boolean(resolvedTable),
      anomaly: !Boolean(resolvedTable),
      segment: !Boolean(resolvedTable),
      strategy_risk: !Boolean(resolvedKpiId),
    }),
    [resolvedKpiId, resolvedTable],
  );

  const defaultTask: DecisionTaskType = analysisSource === "strategy" && resolvedKpiId ? "strategy_risk" : "forecast";
  const currentPanelState = panelStateByContext[stableContextKey] ?? createPanelState(defaultTask);
  const selectedTask = currentPanelState.selectedTask;
  const displayedTask = currentPanelState.displayedTask;
  const runningTask = currentPanelState.runningTask;
  const lastCompletedTask = currentPanelState.lastCompletedTask;
  const taskStates = currentPanelState.tasks;
  const activeTaskState = taskStates[displayedTask];
  const activeAnalysis = activeTaskState.analysis;
  const activePrediction = activeAnalysis?.prediction ?? null;
  const activeSegmentation = activeAnalysis?.segmentation ?? null;
  const activeStrategy = activeAnalysis?.strategy ?? null;
  const baseSemanticContext = useMemo(
    () => buildSemanticContext(chartSpec, chartTitle, resolvedTable, resolvedKpiId),
    [chartSpec, chartTitle, resolvedKpiId, resolvedTable],
  );

  const runAnalysis = async (task: DecisionTaskType) => {
    const table = resolvedTable;
    if (!table && task !== "strategy_risk") {
      setPanelStateByContext((previous) => {
        const current = previous[stableContextKey] ?? createPanelState(defaultTask);
        return {
          ...previous,
          [stableContextKey]: {
            ...current,
            selectedTask: task,
            displayedTask: task,
            runningTask: null,
            tasks: {
              ...current.tasks,
              [task]: {
                ...current.tasks[task],
                isLoading: false,
                analysis: null,
                error: "Select a mart or chart before running advanced analysis.",
              },
            },
          },
        };
      });
      return;
    }
    if (task === "strategy_risk" && !resolvedKpiId) {
      setPanelStateByContext((previous) => {
        const current = previous[stableContextKey] ?? createPanelState(defaultTask);
        return {
          ...previous,
          [stableContextKey]: {
            ...current,
            selectedTask: task,
            displayedTask: task,
            runningTask: null,
            tasks: {
              ...current.tasks,
              [task]: {
                ...current.tasks[task],
                isLoading: false,
                analysis: null,
                error: "A matched KPI is required for strategy risk analysis.",
              },
            },
          },
        };
      });
      return;
    }

    const runId = ++runIdRef.current;
    const requestContextKey = stableContextKey;
    setPanelStateByContext((previous) => {
      const current = previous[stableContextKey] ?? createPanelState(defaultTask);
      return {
        ...previous,
        [stableContextKey]: {
          ...current,
          selectedTask: task,
          displayedTask: task,
          runningTask: task,
          tasks: {
            ...current.tasks,
            [task]: { runId, isLoading: true, analysis: null, error: null },
          },
        },
      };
    });

    const requestSemanticContext: SemanticContextSpec = {
      ...baseSemanticContext,
      ...(resolvedAnalysisContext.semantic ?? {}),
      matched_kpi_id: resolvedKpiId ?? resolvedAnalysisContext.semantic?.matched_kpi_id ?? null,
      matched_kpi_label:
        resolvedAnalysisContext.semantic?.matched_kpi_label ??
        chartSpec?.semantic_context?.matched_kpi_label ??
        chartTitle ??
        null,
      marts: resolvedAnalysisContext.semantic?.marts ?? baseSemanticContext.marts,
      required_columns:
        resolvedAnalysisContext.semantic?.required_columns ?? baseSemanticContext.required_columns,
      dimensions: resolvedAnalysisContext.semantic?.dimensions ?? baseSemanticContext.dimensions,
      metric_aliases:
        resolvedAnalysisContext.semantic?.metric_aliases ?? baseSemanticContext.metric_aliases,
      business_concepts:
        resolvedAnalysisContext.semantic?.business_concepts ?? baseSemanticContext.business_concepts,
      preferred_drill_path:
        resolvedAnalysisContext.semantic?.preferred_drill_path ?? baseSemanticContext.preferred_drill_path,
      mart_hierarchy:
        resolvedAnalysisContext.semantic?.mart_hierarchy ?? baseSemanticContext.mart_hierarchy,
      terminal_dimensions:
        resolvedAnalysisContext.semantic?.terminal_dimensions ?? baseSemanticContext.terminal_dimensions,
      disallowed_drill_dimensions:
        resolvedAnalysisContext.semantic?.disallowed_drill_dimensions ?? baseSemanticContext.disallowed_drill_dimensions,
      preferred_chart_types:
        resolvedAnalysisContext.semantic?.preferred_chart_types ?? baseSemanticContext.preferred_chart_types,
      default_grain: resolvedAnalysisContext.semantic?.default_grain ?? baseSemanticContext.default_grain,
      metric_field_hint:
        resolvedAnalysisContext.semantic?.metric_field_hint ?? baseSemanticContext.metric_field_hint,
      entity_field_hint:
        resolvedAnalysisContext.semantic?.entity_field_hint ?? baseSemanticContext.entity_field_hint,
      time_field_hint:
        resolvedAnalysisContext.semantic?.time_field_hint ?? baseSemanticContext.time_field_hint,
    };

    const request: AnalysisRequest = {
      task_type: task,
      table,
      chart_spec: chartSpec ?? undefined,
      chart_rows: chartRows ?? [],
      kpi_id: resolvedKpiId ?? undefined,
      horizon,
      cluster_count: clusterCount,
      analysis_context: {
        ...resolvedAnalysisContext,
        table,
        semantic: requestSemanticContext,
      },
    };

    try {
      const response = await apiClient.postAnalysis(datasetId, request);
      setPanelStateByContext((previous) => {
        const current = previous[requestContextKey];
        if (!current || current.tasks[task].runId !== runId) {
          return previous;
        }
        return {
          ...previous,
          [requestContextKey]: {
            ...current,
            runningTask: current.runningTask === task ? null : current.runningTask,
            lastCompletedTask: task,
            tasks: {
              ...current.tasks,
              [task]: { runId, isLoading: false, analysis: response, error: null },
            },
          },
        };
      });

      if (chartSpec && onChartSpecChange) {
        onChartSpecChange(mergeChartSemanticContext(chartSpec, buildSemanticPatch(response, request.analysis_context ?? {}, resolvedKpiId)));
      }
    } catch (requestError) {
      const message = formatError(requestError);
      setPanelStateByContext((previous) => {
        const current = previous[requestContextKey];
        if (!current || current.tasks[task].runId !== runId) {
          return previous;
        }
        return {
          ...previous,
          [requestContextKey]: {
            ...current,
            runningTask: current.runningTask === task ? null : current.runningTask,
            tasks: {
              ...current.tasks,
              [task]: { runId, isLoading: false, analysis: null, error: message },
            },
          },
        };
      });
    }
  };

  const handleTaskSelect = (task: DecisionTaskType) => {
    setPanelStateByContext((previous) => {
      const current = previous[stableContextKey] ?? createPanelState(defaultTask);
      return {
        ...previous,
        [stableContextKey]: {
          ...current,
          selectedTask: task,
          displayedTask: task,
        },
      };
    });
    void runAnalysis(task);
  };
  const runAnalysisEvent = useEffectEvent((task: DecisionTaskType) => {
    void runAnalysis(task);
  });

  useEffect(() => {
    if (analysisSource !== "strategy" || !resolvedKpiId) {
      autoRunSeedRef.current = null;
      return;
    }
    const seed = [analysisSource, resolvedTable ?? "none", resolvedKpiId, chartTitle ?? "kpi"].join("|");
    if (autoRunSeedRef.current === seed) {
      return;
    }
    autoRunSeedRef.current = seed;
    runAnalysisEvent("strategy_risk");
  }, [analysisSource, chartTitle, resolvedKpiId, resolvedTable, stableContextKey]);

  const selectedTaskConfig = TASK_CONFIG[displayedTask];
  const assistantFocus = useMemo(() => {
    if (activeAnalysis) {
      return buildAnalysisFocusContext({
        title: chartTitle || selectedTaskConfig.label,
        table: resolvedTable,
        kpiId: resolvedKpiId,
        chartSpec,
        chartRows,
        analysisContext: resolvedAnalysisContext,
        semanticContext: chartSpec?.semantic_context ?? null,
        analysis: activeAnalysis,
        task: displayedTask,
        breadcrumbs: [selectedTaskConfig.label],
      });
    }
    if (analysisSource === "strategy") {
      return buildKpiFocusContext({
        title: chartTitle || "Current KPI",
        table: resolvedTable,
        kpiId: resolvedKpiId,
        analysisContext: resolvedAnalysisContext,
        breadcrumbs: ["Strategy KPI"],
      });
    }
    return buildChartFocusContext({
      title: chartTitle || "Current chart",
      table: resolvedTable,
      kpiId: resolvedKpiId,
      chartSpec,
      chartRows,
      analysisContext: resolvedAnalysisContext,
      semanticContext: chartSpec?.semantic_context ?? null,
      breadcrumbs: ["Current chart"],
    });
  }, [
    activeAnalysis,
    analysisSource,
    chartRows,
    chartSpec,
    chartTitle,
    resolvedAnalysisContext,
    resolvedKpiId,
    resolvedTable,
    displayedTask,
    selectedTaskConfig.label,
  ]);
  const assistantSuggestions = useMemo(() => contextualPromptSuggestions(assistantFocus), [assistantFocus]);

  return (
    <div className="rounded-2xl border border-indigo-200/60 bg-gradient-to-br from-white via-indigo-50/30 to-slate-50 p-4 shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-indigo-700">Decision Intelligence</p>
          <h4 className="mt-1 text-lg font-semibold text-slate-900">{chartTitle || "Structured analysis"}</h4>
          <p className="mt-1 text-sm text-slate-600">
            Run forecasting, anomaly detection, clustering, and strategy-linked KPI risk from the current chart or KPI context.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {(Object.keys(TASK_CONFIG) as DecisionTaskType[]).map((task) => {
            const Icon = TASK_CONFIG[task].icon;
            const disabled = disabledTasks[task];
            const state = taskStates[task];
            return (
              <button
                key={task}
                type="button"
                disabled={disabled}
                onClick={() => handleTaskSelect(task)}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  selectedTask === task
                    ? "border-indigo-500 bg-indigo-600 text-white"
                    : "border-slate-300 bg-white text-slate-700 hover:border-indigo-300 hover:bg-indigo-50"
                } disabled:cursor-not-allowed disabled:opacity-50`}
              >
                {state.isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Icon className="h-3.5 w-3.5" />}
                <span>{TASK_CONFIG[task].label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white/80 px-3 py-2">
        <label className="text-xs text-slate-700">
          Forecast horizon
          <input
            type="number"
            min={1}
            max={24}
            value={horizon}
            onChange={(event) => setHorizon(Math.max(1, Math.min(24, Number(event.target.value) || 6)))}
            className="ml-2 w-16 rounded-md border border-slate-300 px-2 py-1 text-xs"
          />
        </label>
        <label className="text-xs text-slate-700">
          Clusters
          <input
            type="number"
            min={2}
            max={8}
            value={clusterCount}
            onChange={(event) => setClusterCount(Math.max(2, Math.min(8, Number(event.target.value) || 4)))}
            className="ml-2 w-16 rounded-md border border-slate-300 px-2 py-1 text-xs"
          />
        </label>
          <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-1 text-[11px] text-indigo-700">
            Selected task: {TASK_CONFIG[selectedTask].label}
          </span>
        {runningTask ? (
          <span className="rounded-full border border-indigo-200 bg-white px-2 py-1 text-[11px] text-indigo-700">
            Running: {TASK_CONFIG[runningTask].label}
          </span>
        ) : null}
        {lastCompletedTask ? (
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-600">
            Last completed: {TASK_CONFIG[lastCompletedTask].label}
          </span>
        ) : null}
        <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-600">
          Source: {resolvedAnalysisContext.source ?? analysisSource}
        </span>
        {resolvedKpiId ? (
          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-[11px] text-emerald-700">
            KPI linked: {resolvedKpiId}
          </span>
        ) : null}
        {activeAnalysis ? (
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-600">
            Routed via {activeAnalysis.agent_role}
          </span>
        ) : null}
      </div>

      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full bg-slate-100 px-2 py-0.5 text-[10px] uppercase tracking-wide ${selectedTaskConfig.accent}`}>
            {selectedTaskConfig.label}
          </span>
          <span className="text-sm font-semibold text-slate-900">{selectedTaskConfig.label} Results</span>
          <span className="text-xs text-slate-500">{selectedTaskConfig.description}</span>
        </div>
        {activeAnalysis?.plan_spec.route_reason ? (
          <p className="mt-2 text-sm text-slate-700">{activeAnalysis.plan_spec.route_reason}</p>
        ) : null}
        {activeAnalysis?.plan_spec.tasks?.length ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {activeAnalysis.plan_spec.tasks.map((task) => (
              <span key={task.task_id} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-600">
                {task.title}
                {task.depends_on_task_ids.length > 0 ? " -> dependent" : ""}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      {activeTaskState.isLoading ? (
        <div className="mt-4 flex items-center justify-center rounded-xl border border-slate-200 bg-white/80 py-10 text-slate-600">
          <Loader2 className="mr-2 h-5 w-5 animate-spin text-indigo-600" />
          Running {selectedTaskConfig.label.toLowerCase()} analysis...
        </div>
      ) : activeTaskState.error ? (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-700">
          <p className="font-medium">{selectedTaskConfig.label} could not be completed.</p>
          <p className="mt-1">{activeTaskState.error}</p>
        </div>
      ) : activeAnalysis ? (
        <div className="mt-4 space-y-4">
          {activeAnalysis.insight_cards.length > 0 ? (
            <div className="grid gap-3 md:grid-cols-2">
              {activeAnalysis.insight_cards.map((card) => (
                <div key={`${card.title}-${card.summary}`} className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-900">{card.title}</p>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-600">
                      {card.severity}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-slate-700">{card.summary}</p>
                  {card.recommended_action ? <p className="mt-2 text-xs text-indigo-700">Next: {card.recommended_action}</p> : null}
                </div>
              ))}
            </div>
          ) : null}

          {activePrediction ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1 rounded-full bg-indigo-100 px-2 py-0.5 text-xs text-indigo-700">
                  <TrendingUp className="h-3.5 w-3.5" />
                  {activePrediction.mode}
                </span>
                <span className="text-xs text-slate-500">
                  {(activePrediction.display_label || activePrediction.metric) ?? "Metric"} over {activePrediction.time_grain}
                </span>
                {activePrediction.risk_band ? (
                  <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-700">
                    Risk: {activePrediction.risk_band}
                  </span>
                ) : null}
                {typeof activePrediction.confidence_score === "number" ? (
                  <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600">
                    Confidence: {Math.round(activePrediction.confidence_score * 100)}%
                  </span>
                ) : null}
                {activePrediction.metric_source && activePrediction.metric_source !== "field" ? (
                  <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700">
                    Source: {activePrediction.metric_source}
                  </span>
                ) : null}
              </div>

              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">Observed window</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">
                    {activePrediction.historical_start ?? "n/a"} to {activePrediction.historical_end ?? "n/a"}
                  </p>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">Observed periods</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">{activePrediction.observed_points}</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">Projected change</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">
                    {formatPercent(
                      typeof activePrediction.projected_change_pct === "number"
                        ? activePrediction.projected_change_pct * 100
                        : null,
                    )}
                  </p>
                </div>
              </div>

              <PredictionBars prediction={activePrediction} />

              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full text-left text-xs">
                  <thead className="text-slate-500">
                    <tr>
                      <th className="pb-2 pr-4 font-medium">Period</th>
                      <th className="pb-2 pr-4 font-medium">Actual</th>
                      <th className="pb-2 pr-4 font-medium">Forecast</th>
                      <th className="pb-2 pr-4 font-medium">Range</th>
                      <th className="pb-2 font-medium">Signal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activePrediction.points.slice(-8).map((point) => (
                      <tr key={`${point.label}-${point.forecast ?? point.actual ?? 0}`} className="border-t border-slate-100">
                        <td className="py-2 pr-4 text-slate-700">{point.label}</td>
                        <td className="py-2 pr-4 text-slate-900">{formatMetric(point.actual)}</td>
                        <td className="py-2 pr-4 text-slate-900">{formatMetric(point.forecast)}</td>
                        <td className="py-2 pr-4 text-slate-700">
                          {point.lower != null || point.upper != null
                            ? `${formatMetric(point.lower)} to ${formatMetric(point.upper)}`
                            : "-"}
                        </td>
                        <td className="py-2 text-slate-700">{point.anomaly_flag ? "Flagged" : point.is_forecast ? "Forecast" : "Observed"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {activePrediction.explanation ? (
                <p className="mt-3 text-sm text-slate-700">{activePrediction.explanation}</p>
              ) : null}

              {activePrediction.anomalies.length > 0 ? (
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {activePrediction.anomalies.slice(0, 4).map((item) => (
                    <div key={`${item.label}-${item.value}`} className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-[11px] text-red-700">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{item.label}</span>
                        <span>{item.severity} {item.severity_score != null ? `(${item.severity_score})` : ""}</span>
                      </div>
                      {item.explanation ? <p className="mt-1 text-red-800">{item.explanation}</p> : null}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          {activeSegmentation ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1 rounded-full bg-violet-100 px-2 py-0.5 text-xs text-violet-700">
                  <BrainCircuit className="h-3.5 w-3.5" />
                  {activeSegmentation.cluster_count} clusters
                </span>
                <span className="text-xs text-slate-500">
                  Entity: {activeSegmentation.entity_label || activeSegmentation.entity_field}
                </span>
                {activeSegmentation.silhouette_hint != null ? (
                  <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600">
                    Cohesion: {activeSegmentation.silhouette_hint}
                  </span>
                ) : null}
              </div>

              {activeSegmentation.comparison_highlights.length > 0 ? (
                <div className="mt-3 rounded-xl border border-violet-100 bg-violet-50 px-3 py-2 text-sm text-violet-800">
                  {activeSegmentation.comparison_highlights[0]}
                </div>
              ) : null}

              <div className="mt-3 grid gap-3 md:grid-cols-2">
                {activeSegmentation.profiles.map((profile) => {
                  const share =
                    activeSegmentation.assignments.length > 0
                      ? Math.round((profile.entity_count / activeSegmentation.assignments.length) * 100)
                      : 0;
                  return (
                    <div key={profile.cluster_id} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-slate-900">Cluster {profile.cluster_id}</p>
                        <span className="rounded-full bg-white px-2 py-0.5 text-[10px] text-slate-600">
                          {profile.entity_count} entities
                        </span>
                      </div>
                      <p className="mt-1 text-sm text-slate-700">{profile.label}</p>
                      <div className="mt-2 h-2 rounded-full bg-white">
                        <div className="h-2 rounded-full bg-violet-400" style={{ width: `${share}%` }} />
                      </div>
                      <p className="mt-1 text-[11px] text-slate-500">{share}% of clustered entities</p>
                      {profile.metric_highlights.length > 0 ? (
                        <ul className="mt-2 space-y-1 text-xs text-slate-600">
                          {profile.metric_highlights.map((item) => (
                            <li key={item}>- {item}</li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}

          {activeStrategy ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900">KPI Risk Outlook</p>
                  <p className="text-xs text-slate-500">{activeStrategy.kpi_label || activeStrategy.kpi_id}</p>
                </div>
                <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-700">
                  {activeStrategy.risk_band}
                </span>
              </div>

              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">Current</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">{formatMetric(activeStrategy.current_value)}</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">Projected</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">{formatMetric(activeStrategy.projected_value)}</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">Target</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">{formatMetric(activeStrategy.target_value)}</p>
                </div>
              </div>

              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">Target horizon</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">{activeStrategy.target_horizon || "n/a"}</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">Variance to target</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">{formatMetric(activeStrategy.variance_to_target)}</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">Confidence</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">
                    {typeof activeStrategy.confidence_score === "number" ? `${Math.round(activeStrategy.confidence_score * 100)}%` : "n/a"}
                  </p>
                </div>
              </div>

              {activeStrategy.explanation ? <p className="mt-3 text-sm text-slate-700">{activeStrategy.explanation}</p> : null}
              {activeStrategy.forecast_basis ? (
                <p className="mt-2 text-xs text-slate-500">Forecast basis: {activeStrategy.forecast_basis}</p>
              ) : null}
              {activeStrategy.supporting_details.length > 0 ? (
                <ul className="mt-3 space-y-1 text-xs text-slate-600">
                  {activeStrategy.supporting_details.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}

          {activeAnalysis.suggested_actions.length > 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-sm font-semibold text-slate-900">Suggested Next Steps</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {activeAnalysis.suggested_actions.map((action) => (
                  <button
                    key={`${action.action_type}-${action.label}`}
                    type="button"
                    onClick={() => {
                      if (
                        action.action_type === "forecast" ||
                        action.action_type === "anomaly" ||
                        action.action_type === "segment" ||
                        action.action_type === "strategy_risk"
                      ) {
                        handleTaskSelect(action.action_type);
                      }
                    }}
                    className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-slate-50 px-3 py-1.5 text-xs text-slate-700 hover:border-indigo-300 hover:bg-indigo-50"
                  >
                    <BarChart3 className="h-3.5 w-3.5" />
                    <span>{action.label}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="mt-4 rounded-xl border border-dashed border-slate-300 bg-white/70 px-4 py-8 text-center text-sm text-slate-500">
          Run {selectedTaskConfig.label.toLowerCase()} to generate a fresh, task-specific result from the current chart or KPI context.
        </div>
      )}

      {activeAnalysis || analysisSource === "strategy" ? (
        <div className="mt-4">
          <ContextualAssistant
            datasetId={datasetId}
            focus={assistantFocus}
            title={
              activeAnalysis
                ? `Ask about this ${selectedTaskConfig.label.toLowerCase()} result`
                : "Ask about this KPI"
            }
            description="This assistant inherits the current artifact, semantic context, and latest analysis state."
            suggestions={assistantSuggestions}
            onChartSpecChange={onChartSpecChange}
          />
        </div>
      ) : null}
    </div>
  );
}
