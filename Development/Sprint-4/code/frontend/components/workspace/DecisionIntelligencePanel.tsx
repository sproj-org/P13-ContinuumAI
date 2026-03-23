"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, BarChart3, BrainCircuit, Loader2, Radar, TrendingUp } from "lucide-react";

import { apiClient } from "@/lib/api";
import { mergeChartSemanticContext } from "@/lib/chart-display";
import type { AnalysisRequest, AnalysisResponse, AnalysisTaskType } from "@/lib/types/analysis";
import type { ChartSemanticContext, ChartSpecV1 } from "@/lib/types/chartspec";

type PanelTask = "forecast" | "anomaly" | "segment" | "strategy_risk";

interface DecisionIntelligencePanelProps {
  datasetId: string;
  martId?: string | null;
  chartSpec?: ChartSpecV1 | null;
  chartRows?: Array<Record<string, unknown>> | null;
  chartTitle?: string | null;
  kpiId?: string | null;
  onChartSpecChange?: (nextChartSpec: ChartSpecV1) => void;
}

const TASK_CONFIG: Record<PanelTask, { label: string; icon: typeof TrendingUp }> = {
  forecast: { label: "Forecast", icon: TrendingUp },
  anomaly: { label: "Anomalies", icon: AlertTriangle },
  segment: { label: "Segments", icon: BrainCircuit },
  strategy_risk: { label: "KPI Risk", icon: Radar },
};

function formatMetric(value: unknown): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
}

export default function DecisionIntelligencePanel({
  datasetId,
  martId,
  chartSpec,
  chartRows,
  chartTitle,
  kpiId,
  onChartSpecChange,
}: DecisionIntelligencePanelProps) {
  const [activeTask, setActiveTask] = useState<PanelTask>("forecast");
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [horizon, setHorizon] = useState(6);
  const [clusterCount, setClusterCount] = useState(4);

  const resolvedKpiId = kpiId || chartSpec?.semantic_context?.matched_kpi_id || null;
  const disabledTasks = useMemo<Record<PanelTask, boolean>>(
    () => ({
      forecast: !Boolean(martId || chartSpec?.table),
      anomaly: !Boolean(martId || chartSpec?.table),
      segment: !Boolean(martId || chartSpec?.table),
      strategy_risk: !Boolean(resolvedKpiId),
    }),
    [chartSpec?.table, martId, resolvedKpiId],
  );

  const runAnalysis = async (task: PanelTask) => {
    const table = martId || chartSpec?.table || null;
    if (!table && task !== "strategy_risk") {
      setError("Select a mart or chart before running advanced analysis.");
      return;
    }
    if (task === "strategy_risk" && !resolvedKpiId) {
      setError("A matched KPI is required for strategy risk analysis.");
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const request: AnalysisRequest = {
        task_type: task as AnalysisTaskType,
        table,
        chart_spec: chartSpec ?? undefined,
        chart_rows: chartRows ?? [],
        kpi_id: resolvedKpiId ?? undefined,
        horizon,
        cluster_count: clusterCount,
      };
      const response = await apiClient.postAnalysis(datasetId, request);
      setAnalysis(response);

      if (chartSpec && onChartSpecChange) {
        const semanticPatch: Partial<ChartSemanticContext> = {};
        if (response.prediction) {
          semanticPatch.prediction_context = {
            mode: response.prediction.mode,
            metric: response.prediction.metric,
            time_field: response.prediction.time_field,
            time_grain: response.prediction.time_grain,
            horizon: response.prediction.horizon,
            risk_band: response.prediction.risk_band ?? null,
            kpi_id: resolvedKpiId,
          };
        }
        if (response.segmentation) {
          semanticPatch.segmentation_context = {
            entity_field: response.segmentation.entity_field,
            features: response.segmentation.features,
            cluster_count: response.segmentation.cluster_count,
          };
        }
        if (Object.keys(semanticPatch).length > 0) {
          onChartSpecChange(mergeChartSemanticContext(chartSpec, semanticPatch));
        }
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Analysis request failed.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="rounded-2xl border border-indigo-200/60 bg-gradient-to-br from-white via-indigo-50/30 to-slate-50 p-4 shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-indigo-700">Decision Intelligence</p>
          <h4 className="mt-1 text-lg font-semibold text-slate-900">{chartTitle || "Structured analysis"}</h4>
          <p className="mt-1 text-sm text-slate-600">
            Run forecasting, anomaly detection, clustering, and strategy-linked KPI risk from the current chart context.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {(Object.keys(TASK_CONFIG) as PanelTask[]).map((task) => {
            const Icon = TASK_CONFIG[task].icon;
            const disabled = disabledTasks[task];
            return (
              <button
                key={task}
                type="button"
                disabled={disabled || isLoading}
                onClick={() => {
                  setActiveTask(task);
                  void runAnalysis(task);
                }}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  activeTask === task
                    ? "border-indigo-500 bg-indigo-600 text-white"
                    : "border-slate-300 bg-white text-slate-700 hover:border-indigo-300 hover:bg-indigo-50"
                } disabled:cursor-not-allowed disabled:opacity-50`}
              >
                <Icon className="h-3.5 w-3.5" />
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
        {resolvedKpiId ? (
          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-[11px] text-emerald-700">
            KPI linked: {resolvedKpiId}
          </span>
        ) : null}
        {analysis ? (
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-600">
            Routed via {analysis.agent_role}
          </span>
        ) : null}
        {analysis?.plan_spec.matched_kpi_label ? (
          <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-1 text-[11px] text-indigo-700">
            Matched KPI: {analysis.plan_spec.matched_kpi_label}
          </span>
        ) : null}
      </div>

      {error ? (
        <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      ) : null}

      {isLoading ? (
        <div className="mt-4 flex items-center justify-center rounded-xl border border-slate-200 bg-white/80 py-10 text-slate-600">
          <Loader2 className="mr-2 h-5 w-5 animate-spin text-indigo-600" />
          Running structured analysis...
        </div>
      ) : analysis ? (
        <div className="mt-4 space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-600">
                {analysis.plan_spec.primary_task.replace("_", " ")}
              </span>
              <span className="text-xs text-slate-500">{analysis.plan_spec.route_reason}</span>
            </div>
            {analysis.primary_view?.summary ? (
              <p className="mt-2 text-sm text-slate-700">{analysis.primary_view.summary}</p>
            ) : null}
          </div>
          {analysis.insight_cards.length > 0 ? (
            <div className="grid gap-3 md:grid-cols-2">
              {analysis.insight_cards.map((card) => (
                <div key={`${card.title}-${card.summary}`} className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-900">{card.title}</p>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-600">
                      {card.severity}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-slate-700">{card.summary}</p>
                  {card.recommended_action ? (
                    <p className="mt-2 text-xs text-indigo-700">Next: {card.recommended_action}</p>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}

          {analysis.prediction ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1 rounded-full bg-indigo-100 px-2 py-0.5 text-xs text-indigo-700">
                  <TrendingUp className="h-3.5 w-3.5" />
                  {analysis.prediction.mode}
                </span>
                <span className="text-xs text-slate-500">
                  {analysis.prediction.metric} over {analysis.prediction.time_grain}
                </span>
                {analysis.prediction.risk_band ? (
                  <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-700">
                    Risk: {analysis.prediction.risk_band}
                  </span>
                ) : null}
              </div>
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full text-left text-xs">
                  <thead className="text-slate-500">
                    <tr>
                      <th className="pb-2 pr-4 font-medium">Period</th>
                      <th className="pb-2 pr-4 font-medium">Actual</th>
                      <th className="pb-2 pr-4 font-medium">Forecast</th>
                      <th className="pb-2 font-medium">Anomaly</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.prediction.points.slice(-8).map((point) => (
                      <tr key={`${point.label}-${point.forecast ?? point.actual ?? 0}`} className="border-t border-slate-100">
                        <td className="py-2 pr-4 text-slate-700">{point.label}</td>
                        <td className="py-2 pr-4 text-slate-900">{formatMetric(point.actual)}</td>
                        <td className="py-2 pr-4 text-slate-900">{formatMetric(point.forecast)}</td>
                        <td className="py-2 text-slate-700">{point.anomaly_flag ? "Flagged" : "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {analysis.prediction.anomalies.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {analysis.prediction.anomalies.slice(0, 4).map((item) => (
                    <span key={`${item.label}-${item.value}`} className="rounded-full border border-red-200 bg-red-50 px-2 py-1 text-[11px] text-red-700">
                      {item.label}: {item.severity}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          {analysis.segmentation ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1 rounded-full bg-violet-100 px-2 py-0.5 text-xs text-violet-700">
                  <BrainCircuit className="h-3.5 w-3.5" />
                  {analysis.segmentation.cluster_count} clusters
                </span>
                <span className="text-xs text-slate-500">
                  Entity: {analysis.segmentation.entity_field}
                </span>
                {analysis.segmentation.silhouette_hint != null ? (
                  <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600">
                    Cohesion: {analysis.segmentation.silhouette_hint}
                  </span>
                ) : null}
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                {analysis.segmentation.profiles.map((profile) => (
                  <div key={profile.cluster_id} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-slate-900">Cluster {profile.cluster_id}</p>
                      <span className="rounded-full bg-white px-2 py-0.5 text-[10px] text-slate-600">
                        {profile.entity_count} entities
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-slate-700">{profile.label}</p>
                    {profile.metric_highlights.length > 0 ? (
                      <ul className="mt-2 space-y-1 text-xs text-slate-600">
                        {profile.metric_highlights.map((item) => (
                          <li key={item}>• {item}</li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {analysis.strategy ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900">KPI Risk Outlook</p>
                  <p className="text-xs text-slate-500">{analysis.strategy.kpi_id}</p>
                </div>
                <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-700">
                  {analysis.strategy.risk_band}
                </span>
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">Current</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">{formatMetric(analysis.strategy.current_value)}</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">Projected</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">{formatMetric(analysis.strategy.projected_value)}</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">Target</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">{formatMetric(analysis.strategy.target_value)}</p>
                </div>
              </div>
            </div>
          ) : null}

          {analysis.suggested_actions.length > 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-sm font-semibold text-slate-900">Suggested Next Steps</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {analysis.suggested_actions.map((action) => (
                  <button
                    key={`${action.action_type}-${action.label}`}
                    type="button"
                    onClick={() => {
                      if (action.action_type === "forecast" || action.action_type === "anomaly" || action.action_type === "segment" || action.action_type === "strategy_risk") {
                        setActiveTask(action.action_type as PanelTask);
                        void runAnalysis(action.action_type as PanelTask);
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
          Select an analysis mode above to run the first structured decision-intelligence pass.
        </div>
      )}
    </div>
  );
}
