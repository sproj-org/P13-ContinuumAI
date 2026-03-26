"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { Column, Histogram, Line, Pie } from "@ant-design/plots";
import { AlertTriangle, ChevronRight, Loader2, RotateCcw } from "lucide-react";

import { apiClient } from "@/lib/api";
import type { AggregateFilter, DatasetProfileAPI } from "@/lib/api-types";
import {
  chartDimensionLabel,
  chartMetricLabel as resolveChartMetricLabel,
  formatChartCategoryLabel,
  getChartDisplayPolicy,
} from "@/lib/chart-display";
import {
  buildCategoricalSeries,
  buildHistogramData,
  buildPieData,
  CHART_PALETTE,
} from "@/lib/chart-rendering";
import { useStrategyKpis, useTableProfile } from "@/lib/hooks";
import {
  analyzeDrilldown,
  isStrongDrillRecommendation,
} from "@/lib/mart-drill-utils";
import type { ChartSpecV1 } from "@/lib/types/chartspec";

type ChartRows = Array<Record<string, unknown>>;

interface DrillLevel {
  dimension: string;
  clickedValue: unknown;
  clickedLabel: string;
  nextDimension: string;
}

interface PendingDrillSelection {
  rawValue: unknown;
  label: string;
}

interface DrillNotice {
  kind: "empty" | "terminal";
  title: string;
  message: string;
  attemptedDimension?: string | null;
}

export interface DrillDownChartProps {
  chartSpec: ChartSpecV1;
  rows: ChartRows;
  datasetId: string;
  profile?: DatasetProfileAPI | null;
  height?: string;
  chartTitle?: string | null;
  defaultAutoDrill?: boolean;
}

const OP_MAP: Record<string, AggregateFilter["op"]> = {
  "=": "eq",
  "!=": "ne",
  ">": "gt",
  ">=": "gte",
  "<": "lt",
  "<=": "lte",
  in: "in",
};

export default function DrillDownChart({
  chartSpec,
  rows: initialRows,
  datasetId,
  profile: externalProfile,
  height = "100%",
  chartTitle = null,
  defaultAutoDrill = true,
}: Readonly<DrillDownChartProps>) {
  const { data: fetchedProfile } = useTableProfile(datasetId, externalProfile ? null : chartSpec.table);
  const { data: strategyKpiLibrary } = useStrategyKpis(datasetId);
  const profile = externalProfile ?? fetchedProfile ?? null;

  const [drillStack, setDrillStack] = useState<DrillLevel[]>([]);
  const [currentRows, setCurrentRows] = useState<ChartRows>(initialRows);
  const [pendingClick, setPendingClick] = useState<PendingDrillSelection | null>(null);
  const [selectedNextDimension, setSelectedNextDimension] = useState<string>("");
  const [isDimensionPickerOpen, setIsDimensionPickerOpen] = useState(false);
  const [quickDrillEnabled, setQuickDrillEnabled] = useState(defaultAutoDrill);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drillNotice, setDrillNotice] = useState<DrillNotice | null>(null);

  const sourceFingerprintRef = useRef<string>("");
  const sourceFingerprint = useMemo(
    () =>
      JSON.stringify({
        datasetId,
        table: chartSpec.table,
        chartType: chartSpec.chart.type,
        xField: chartSpec.encoding.x.field,
        yFields: chartSpec.encoding.y.map((item) => `${item.field}:${item.aggregation ?? "sum"}`),
        filters: chartSpec.filters ?? [],
        sort: chartSpec.sort ?? [],
        limit: chartSpec.limit ?? null,
        defaultAutoDrill,
      }),
    [chartSpec.chart.type, chartSpec.encoding.x.field, chartSpec.encoding.y, chartSpec.filters, chartSpec.limit, chartSpec.sort, chartSpec.table, datasetId, defaultAutoDrill],
  );

  useEffect(() => {
    if (sourceFingerprintRef.current !== sourceFingerprint) {
      sourceFingerprintRef.current = sourceFingerprint;
      setDrillStack([]);
      setCurrentRows(initialRows);
      setPendingClick(null);
      setIsDimensionPickerOpen(false);
      setSelectedNextDimension("");
      setQuickDrillEnabled(defaultAutoDrill);
      setError(null);
      setDrillNotice(null);
    }
  }, [defaultAutoDrill, initialRows, sourceFingerprint]);

  useEffect(() => {
    if (drillStack.length === 0) {
      setCurrentRows(initialRows);
    }
  }, [drillStack.length, initialRows]);

  const startDimension = chartSpec.encoding.x.field;
  const currentDimension = drillStack.length > 0 ? drillStack[drillStack.length - 1].nextDimension : startDimension;
  const startDimensionLabel = chartDimensionLabel(startDimension);
  const currentDimensionLabel = chartDimensionLabel(currentDimension);

  const usedDimensions = useMemo(() => {
    const used = new Set<string>([startDimension]);
    for (const level of drillStack) {
      used.add(level.dimension);
      used.add(level.nextDimension);
    }
    return used;
  }, [drillStack, startDimension]);

  const metric = chartSpec.encoding.y[0];
  const metricField = metric?.field ?? "agg_value";
  const aggregation = metric?.aggregation ?? "sum";
  const metricLabel = resolveChartMetricLabel(chartSpec, {
    strategyKpis: strategyKpiLibrary?.kpis ?? [],
  });
  const metricCandidates = useMemo(
    () => Array.from(new Set([metric?.alias, "agg_value", metricField].filter((value): value is string => Boolean(value)))),
    [metric?.alias, metricField],
  );

  const drillAnalysis = useMemo(() => {
    if (!profile) {
      return {
        candidates: [],
        configuredHierarchy: [],
        preferredNextDimensions: [],
        terminalReason: null,
        matchedKpiLabel: null,
        metricFamilyLabel: null,
      };
    }
    return analyzeDrilldown({
      profile,
      martId: chartSpec.table,
      currentDimension,
      usedDimensions,
      metricField,
      chartTitle,
      chartType: chartSpec.chart.type,
      strategyKpis: strategyKpiLibrary?.kpis ?? [],
      semanticContext: chartSpec.semantic_context ?? null,
    });
  }, [profile, chartSpec.table, chartSpec.semantic_context, currentDimension, usedDimensions, metricField, chartTitle, chartSpec.chart.type, strategyKpiLibrary?.kpis]);

  const rankedDrillCandidates = drillAnalysis.candidates;
  const configuredHierarchy = drillAnalysis.configuredHierarchy;
  const preferredNextDimensions = drillAnalysis.preferredNextDimensions;

  const drillCandidates = useMemo(() => rankedDrillCandidates.map((candidate) => candidate.name), [rankedDrillCandidates]);
  const topRecommendation = rankedDrillCandidates[0] ?? null;
  const topRecommendationLabel = topRecommendation ? chartDimensionLabel(topRecommendation.name) : null;

  const displayPolicy = useMemo(
    () =>
      getChartDisplayPolicy({
        chartSpec,
        currentDimension,
        profile,
        rankedCandidates: rankedDrillCandidates,
      }),
    [chartSpec, currentDimension, profile, rankedDrillCandidates],
  );

  const supportsDrill = displayPolicy.supportsDrill;
  const effectiveDisabledReason = drillAnalysis.terminalReason ?? displayPolicy.disabledReason ?? "No deeper dimensions available";
  const canAutoDrill =
    supportsDrill &&
    displayPolicy.allowQuickDrill &&
    quickDrillEnabled &&
    isStrongDrillRecommendation(rankedDrillCandidates);

  const fetchDrillData = useCallback(
    async (dimension: string, filters: AggregateFilter[]) => {
      setLoading(true);
      setError(null);
      try {
        const resp = await apiClient.executeAggregate(datasetId, {
          table_name: chartSpec.table,
          x: dimension,
          group_by: [dimension],
          filters,
          agg: { column: aggregation === "count" ? "*" : metricField, fn: aggregation },
          limit: chartSpec.limit ?? 20,
        });
        return resp.rows as ChartRows;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to fetch drill-down data";
        setError(msg);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [datasetId, chartSpec.table, metricField, aggregation, chartSpec.limit],
  );

  const buildFilters = useCallback(
    (stack: DrillLevel[]): AggregateFilter[] => {
      const drillFilters: AggregateFilter[] = stack.map((level) => ({
        column: level.dimension,
        op: "eq" as const,
        value: level.clickedValue,
      }));

      const specFilters: AggregateFilter[] = (chartSpec.filters ?? []).map((item) => ({
        column: item.field,
        op: OP_MAP[item.op] ?? "eq",
        value: item.value,
      }));

      return [...specFilters, ...drillFilters];
    },
    [chartSpec.filters],
  );

  const executeDrill = useCallback(
    async (nextDimension: string, pendingSelectionOverride?: PendingDrillSelection | null) => {
      const effectiveSelection = pendingSelectionOverride ?? pendingClick;
      if (!effectiveSelection || effectiveSelection.rawValue == null || !nextDimension) {
        setIsDimensionPickerOpen(false);
        return;
      }

      const newLevel: DrillLevel = {
        dimension: currentDimension,
        clickedValue: effectiveSelection.rawValue,
        clickedLabel: effectiveSelection.label,
        nextDimension,
      };
      const newStack = [...drillStack, newLevel];

      setIsDimensionPickerOpen(false);
      setSelectedNextDimension("");
      setDrillNotice(null);
      const rows = await fetchDrillData(nextDimension, buildFilters(newStack));
      if (!rows) {
        return;
      }
      if (rows.length === 0) {
        setPendingClick(effectiveSelection);
        setSelectedNextDimension(nextDimension);
        setDrillNotice({
          kind: "empty",
          title: "No deeper rows returned",
          message: `${effectiveSelection.label} does not return rows when drilled into ${chartDimensionLabel(nextDimension)}. Try another dimension or step back.`,
          attemptedDimension: nextDimension,
        });
        return;
      }

      setDrillStack(newStack);
      setCurrentRows(rows);
      setPendingClick(null);
    },
    [pendingClick, currentDimension, drillStack, fetchDrillData, buildFilters],
  );

  const handleDatumClick = useCallback(
    (rawValue: unknown) => {
      if (!supportsDrill || rawValue == null || rawValue === "") return;

      const clickedLabel = formatChartCategoryLabel(rawValue, currentDimension);
      const topCandidate = topRecommendation?.name ?? drillCandidates[0] ?? "";
      const nextSelection = { rawValue, label: clickedLabel };

      setDrillNotice(null);
      setPendingClick(nextSelection);
      setSelectedNextDimension(topCandidate);

      if (!quickDrillEnabled) {
        setIsDimensionPickerOpen(true);
        return;
      }

      if (canAutoDrill && topCandidate) {
        void executeDrill(topCandidate, nextSelection);
        return;
      }

      setIsDimensionPickerOpen(true);
    },
    [supportsDrill, currentDimension, topRecommendation?.name, drillCandidates, quickDrillEnabled, canAutoDrill, executeDrill],
  );

  const confirmDrill = useCallback(() => {
    void executeDrill(selectedNextDimension);
  }, [executeDrill, selectedNextDimension]);

  const useRecommendedDrill = useCallback(() => {
    const topCandidate = topRecommendation?.name ?? drillCandidates[0];
    if (!topCandidate) {
      setIsDimensionPickerOpen(false);
      setPendingClick(null);
      setSelectedNextDimension("");
      return;
    }
    void executeDrill(topCandidate);
  }, [topRecommendation?.name, drillCandidates, executeDrill]);

  const openPickerForPendingSelection = useCallback(() => {
    if (!pendingClick || rankedDrillCandidates.length === 0) {
      return;
    }
    setSelectedNextDimension((currentValue) => currentValue || rankedDrillCandidates[0]?.name || "");
    setIsDimensionPickerOpen(true);
  }, [pendingClick, rankedDrillCandidates]);

  const handleBreadcrumbClick = useCallback(
    (levelIndex: number) => {
      if (levelIndex === -1) {
        setDrillStack([]);
        setCurrentRows(initialRows);
        setPendingClick(null);
        setIsDimensionPickerOpen(false);
        setSelectedNextDimension("");
        setError(null);
        setDrillNotice(null);
        return;
      }

      const newStack = drillStack.slice(0, levelIndex + 1);
      const nextDimension = newStack.at(-1)?.nextDimension ?? startDimension;
      setPendingClick(null);
      setIsDimensionPickerOpen(false);
      setSelectedNextDimension("");
      setError(null);
      setDrillNotice(null);
      void (async () => {
        const rows = await fetchDrillData(nextDimension, buildFilters(newStack));
        if (!rows) {
          return;
        }
        setDrillStack(newStack);
        setCurrentRows(rows);
      })();
    },
    [drillStack, initialRows, fetchDrillData, buildFilters, startDimension],
  );

  const chartType = chartSpec.chart.type;
  const { data: chartData } = useMemo(
    () =>
      buildCategoricalSeries(currentRows, {
        xField: currentDimension,
        metricCandidates,
      }),
    [currentRows, currentDimension, metricCandidates],
  );
  const pieData = useMemo(() => buildPieData(chartData), [chartData]);
  const histogramData = useMemo(() => buildHistogramData(currentRows, metricCandidates), [currentRows, metricCandidates]);

  const bindClickHandler = useCallback(
    (event: unknown) => {
      const datum = (event as { data?: { data?: Record<string, unknown> } })?.data?.data;
      handleDatumClick(datum?.rawCategory ?? datum?.[currentDimension]);
    },
    [handleDatumClick, currentDimension],
  );

  const activeDrillNotice = useMemo(() => {
    if (drillNotice) {
      return drillNotice;
    }
    if (!loading && drillStack.length > 0 && !supportsDrill && drillAnalysis.terminalReason) {
      return {
        kind: "terminal" as const,
        title: "Deepest available breakdown reached",
        message: effectiveDisabledReason,
      };
    }
    return null;
  }, [drillNotice, loading, drillStack.length, supportsDrill, drillAnalysis.terminalReason, effectiveDisabledReason]);

  const renderAntVChart = () => {
    if (chartType === "pie") {
      return (
        <Pie
          data={pieData}
          angleField="value"
          colorField="type"
          innerRadius={0.3}
          label={{ text: "value", position: "inside" }}
          legend={{ color: { position: "bottom" } }}
          scale={{ color: { range: CHART_PALETTE } }}
          interaction={{ elementSelect: { single: true } }}
          onReady={({ chart }) => {
            if (!supportsDrill) return;
            chart.on("element:click", bindClickHandler);
          }}
          height={320}
        />
      );
    }

    if (chartType === "line") {
      return (
        <Line
          data={chartData}
          xField="category"
          yField="value"
          point
          smooth
          style={{ stroke: "#8b5cf6" }}
          axis={{
            x: { title: currentDimensionLabel, labelFill: "#475569", labelAutoHide: true },
            y: { title: metricLabel, labelFill: "#475569" },
          }}
          interaction={{ elementSelect: { single: true } }}
          onReady={({ chart }) => {
            if (!supportsDrill) return;
            chart.on("element:click", bindClickHandler);
          }}
          height={320}
        />
      );
    }

    if (chartType === "histogram") {
      return (
        <Histogram
          data={histogramData}
          binField="value"
          axis={{
            x: { title: metricLabel, labelFill: "#475569" },
            y: { title: "Frequency", labelFill: "#475569" },
          }}
          style={{ fill: "#4f46e5", fillOpacity: 0.8 }}
          height={320}
        />
      );
    }

    return (
      <Column
        data={chartData}
        xField="category"
        yField="value"
        colorField="category"
        axis={{
          x: { title: currentDimensionLabel, labelFill: "#475569", labelAutoHide: true },
          y: { title: metricLabel, labelFill: "#475569" },
        }}
        scale={{ color: { range: CHART_PALETTE } }}
        interaction={{ elementSelect: { single: true } }}
        onReady={({ chart }) => {
          if (!supportsDrill) return;
          chart.on("element:click", bindClickHandler);
        }}
        height={320}
      />
    );
  };

  return (
    <div className="flex flex-col h-full relative" style={{ height }}>
      {drillStack.length > 0 && (
        <div className="flex flex-wrap items-center gap-1 px-3 py-2 bg-gradient-to-r from-indigo-50 to-violet-50 border-b border-indigo-100 rounded-t-xl text-xs flex-shrink-0">
          <button
            onClick={() => handleBreadcrumbClick(-1)}
            className="flex items-center gap-1 px-2 py-1 text-indigo-600 hover:text-indigo-800 hover:bg-indigo-100 rounded-md transition-colors font-medium"
            title="Back to top level"
          >
            <RotateCcw className="w-3 h-3" />
            Reset
          </button>

          <ChevronRight className="w-3 h-3 text-slate-400" />
          <button
            onClick={() => handleBreadcrumbClick(-1)}
            className="px-2 py-1 text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 rounded-md transition-colors font-medium"
          >
            {startDimensionLabel}
          </button>

          {drillStack.map((level, index) => (
            <span key={`${level.dimension}-${String(level.clickedValue)}-${level.nextDimension}`} className="flex items-center gap-1">
              <ChevronRight className="w-3 h-3 text-slate-400" />
              <button
                onClick={() => handleBreadcrumbClick(index)}
                className={`px-2 py-1 rounded-md transition-colors font-medium ${
                  index === drillStack.length - 1
                    ? "text-indigo-700 bg-indigo-100"
                    : "text-slate-600 hover:text-indigo-600 hover:bg-indigo-50"
                }`}
              >
                {level.clickedLabel}
              </button>
            </span>
          ))}

          <ChevronRight className="w-3 h-3 text-slate-400" />
          <span className="px-2 py-1 text-indigo-500 font-medium italic">{currentDimensionLabel}</span>

          {supportsDrill ? (
            <div className="ml-auto flex items-center gap-2">
              <span className="text-slate-400 italic">
                {!quickDrillEnabled
                  ? "Quick drill is off, so clicks open the dimension picker first."
                  : canAutoDrill && topRecommendationLabel
                    ? `Quick drill targets ${topRecommendationLabel}`
                    : "Click to choose the next drill dimension"}
              </span>
              {displayPolicy.allowQuickDrill ? (
                <button
                  type="button"
                  onClick={() => setQuickDrillEnabled((value) => !value)}
                  className={`rounded-full border px-2 py-1 text-[10px] font-medium transition-colors ${
                    quickDrillEnabled
                      ? "border-indigo-300 bg-indigo-100 text-indigo-700"
                      : "border-slate-300 bg-white text-slate-600"
                  }`}
                >
                  Quick drill {quickDrillEnabled ? "on" : "off"}
                </button>
              ) : null}
            </div>
          ) : (
            <span className="ml-auto text-slate-400 italic">
              {effectiveDisabledReason}
            </span>
          )}
        </div>
      )}

      {drillStack.length === 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-1.5 bg-indigo-50/50 border-b border-indigo-100/50 rounded-t-xl text-xs flex-shrink-0">
          <span className="text-indigo-500 font-medium">
            {supportsDrill
              ? !quickDrillEnabled
                ? `Quick drill is off. Click a ${chartType === "pie" ? "slice" : chartType === "line" ? "point" : "bar"} to open the drill picker first`
                : canAutoDrill && topRecommendationLabel
                  ? `Click a ${chartType === "pie" ? "slice" : chartType === "line" ? "point" : "bar"} to quick-drill into ${topRecommendationLabel}`
                  : `Click a ${chartType === "pie" ? "slice" : chartType === "line" ? "point" : "bar"} to choose the next drill dimension`
              : effectiveDisabledReason}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-slate-400">
              {supportsDrill && topRecommendationLabel
                ? `${topRecommendationLabel} - ${topRecommendation.recommendationLabel}`
                : supportsDrill && configuredHierarchy.length > 0
                ? `Recommended path: ${configuredHierarchy.map((dimension) => chartDimensionLabel(dimension)).join(" -> ")}`
                : supportsDrill
                ? `${drillCandidates.length} dimensions available`
                : metricLabel}
            </span>
            {supportsDrill && displayPolicy.allowQuickDrill ? (
              <button
                type="button"
                onClick={() => setQuickDrillEnabled((value) => !value)}
                className={`rounded-full border px-2 py-1 text-[10px] font-medium transition-colors ${
                  quickDrillEnabled
                    ? "border-indigo-300 bg-indigo-100 text-indigo-700"
                    : "border-slate-300 bg-white text-slate-600"
                }`}
              >
                Quick drill {quickDrillEnabled ? "on" : "off"}
              </button>
            ) : null}
          </div>
        </div>
      )}

      {activeDrillNotice ? (
        <div className="mx-3 mt-2 rounded-xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-900 flex-shrink-0">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-700" />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">{activeDrillNotice.title}</p>
              <p className="mt-1 text-xs text-amber-800">{activeDrillNotice.message}</p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {activeDrillNotice.kind === "empty" && pendingClick && rankedDrillCandidates.length > 0 ? (
                  <button
                    type="button"
                    onClick={openPickerForPendingSelection}
                    className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-900 hover:bg-amber-100"
                  >
                    Choose another dimension
                  </button>
                ) : null}
                {drillStack.length > 0 ? (
                  <button
                    type="button"
                    onClick={() => handleBreadcrumbClick(drillStack.length - 2)}
                    className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-900 hover:bg-amber-100"
                  >
                    Back one level
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => handleBreadcrumbClick(-1)}
                  className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-900 hover:bg-amber-100"
                >
                  Reset view
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/60 backdrop-blur-sm rounded-xl">
          <div className="flex items-center gap-2 px-4 py-2 bg-white rounded-lg shadow-md border border-indigo-100">
            <Loader2 className="w-4 h-4 text-indigo-600 animate-spin" />
            <span className="text-sm text-slate-600">Loading drill-down data...</span>
          </div>
        </div>
      )}

      {error && (
        <div className="mx-3 mt-2 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex-shrink-0">
          {error}
          <button onClick={() => handleBreadcrumbClick(-1)} className="ml-2 underline hover:text-red-900">
            Reset
          </button>
        </div>
      )}

      {isDimensionPickerOpen ? (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/20 backdrop-blur-[1px]">
          <div className="w-full max-w-sm rounded-xl border border-indigo-200 bg-white p-4 shadow-xl">
            <h4 className="text-sm font-semibold text-slate-900">Choose next drill dimension</h4>
            <p className="mt-1 text-xs text-slate-600">
              Selected value: <span className="font-medium">{pendingClick?.label}</span>
            </p>
            {topRecommendationLabel ? (
              <p className="mt-1 text-[11px] text-indigo-700">
                Best match: <span className="font-medium">{topRecommendationLabel}</span> - {topRecommendation?.recommendationLabel}
              </p>
            ) : null}
            <select
              value={selectedNextDimension}
              onChange={(event) => setSelectedNextDimension(event.target.value)}
              className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900"
            >
              {rankedDrillCandidates.map((candidate) => (
                <option key={candidate.name} value={candidate.name}>
                  {chartDimensionLabel(candidate.name)}
                  {topRecommendation?.name === candidate.name ? " (recommended)" : preferredNextDimensions.includes(candidate.name) ? " (path)" : ""}
                </option>
              ))}
            </select>
            {selectedNextDimension ? (
              <p className="mt-2 text-[11px] text-slate-600">
                {rankedDrillCandidates.find((candidate) => candidate.name === selectedNextDimension)?.recommendationLabel}
              </p>
            ) : null}
            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                onClick={() => {
                  setIsDimensionPickerOpen(false);
                  setPendingClick(null);
                  setSelectedNextDimension("");
                }}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={useRecommendedDrill}
                className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-sm text-indigo-700 hover:bg-indigo-100"
              >
                Use recommendation
              </button>
              <button onClick={confirmDrill} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700">
                Drill
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <div className={`flex-1 min-h-0 relative ${supportsDrill ? "cursor-pointer" : ""}`}>{renderAntVChart()}</div>
    </div>
  );
}
