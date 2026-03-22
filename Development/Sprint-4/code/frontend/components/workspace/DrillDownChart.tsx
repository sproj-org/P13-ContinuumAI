"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { Column, Histogram, Line, Pie } from "@ant-design/plots";
import { ChevronRight, Loader2, RotateCcw } from "lucide-react";

import { apiClient } from "@/lib/api";
import type { AggregateFilter, DatasetProfileAPI } from "@/lib/api-types";
import {
  buildCategoricalSeries,
  buildHistogramData,
  buildPieData,
  chartMetricLabel,
  CHART_PALETTE,
  toDisplayLabel,
} from "@/lib/chart-rendering";
import { useStrategyKpis, useTableProfile } from "@/lib/hooks";
import {
  getConfiguredNextDimensions,
  isStrongDrillRecommendation,
  rankDrillCandidates,
  resolveMartDrillHierarchy,
} from "@/lib/mart-drill-utils";
import type { ChartSpecV1 } from "@/lib/types/chartspec";

type ChartRows = Array<Record<string, unknown>>;

interface DrillLevel {
  dimension: string;
  clickedValue: string;
  nextDimension: string;
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
  const [pendingClickValue, setPendingClickValue] = useState<string | null>(null);
  const [selectedNextDimension, setSelectedNextDimension] = useState<string>("");
  const [isDimensionPickerOpen, setIsDimensionPickerOpen] = useState(false);
  const [quickDrillEnabled, setQuickDrillEnabled] = useState(defaultAutoDrill);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chartIdRef = useRef<string>("");
  const chartId = `${chartSpec.table}:${chartSpec.encoding.x.field}:${chartSpec.encoding.y[0]?.field}:${chartSpec.chart.type}`;
  useEffect(() => {
    if (chartIdRef.current !== chartId) {
      chartIdRef.current = chartId;
      setDrillStack([]);
      setCurrentRows(initialRows);
      setPendingClickValue(null);
      setIsDimensionPickerOpen(false);
      setSelectedNextDimension("");
      setQuickDrillEnabled(defaultAutoDrill);
      setError(null);
    }
  }, [chartId, defaultAutoDrill, initialRows]);

  const startDimension = chartSpec.encoding.x.field;
  const currentDimension = drillStack.length > 0 ? drillStack[drillStack.length - 1].nextDimension : startDimension;

  const usedDimensions = useMemo(() => {
    const used = new Set<string>([startDimension]);
    for (const level of drillStack) {
      used.add(level.dimension);
      used.add(level.nextDimension);
    }
    return used;
  }, [drillStack, startDimension]);

  const configuredHierarchy = useMemo(() => {
    if (!profile) return [];
    return resolveMartDrillHierarchy(chartSpec.table, profile.columns.map((column) => column.name));
  }, [profile, chartSpec.table]);

  const preferredNextDimensions = useMemo(() => {
    if (!profile) return [];
    return getConfiguredNextDimensions({
      martId: chartSpec.table,
      currentDimension,
      usedDimensions,
      availableColumns: profile.columns.map((column) => column.name),
    });
  }, [profile, chartSpec.table, currentDimension, usedDimensions]);

  const metric = chartSpec.encoding.y[0];
  const metricField = metric?.field ?? "agg_value";
  const aggregation = metric?.aggregation ?? "sum";
  const metricLabel = chartMetricLabel(chartSpec);
  const metricCandidates = useMemo(
    () => Array.from(new Set([metric?.alias, "agg_value", metricField].filter((value): value is string => Boolean(value)))),
    [metric?.alias, metricField],
  );

  const rankedDrillCandidates = useMemo(() => {
    if (!profile) return [];
    return rankDrillCandidates({
      profile,
      martId: chartSpec.table,
      currentDimension,
      usedDimensions,
      metricField,
      chartTitle,
      strategyKpis: strategyKpiLibrary?.kpis ?? [],
    });
  }, [profile, chartSpec.table, currentDimension, usedDimensions, metricField, chartTitle, strategyKpiLibrary?.kpis]);

  const drillCandidates = useMemo(() => rankedDrillCandidates.map((candidate) => candidate.name), [rankedDrillCandidates]);
  const topRecommendation = rankedDrillCandidates[0] ?? null;
  const canDrill = drillCandidates.length > 0;
  const supportsDrill = canDrill && chartSpec.chart.type !== "histogram";
  const canAutoDrill = supportsDrill && quickDrillEnabled && isStrongDrillRecommendation(rankedDrillCandidates);

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
          agg: { column: metricField, fn: aggregation },
          limit: chartSpec.limit ?? 20,
        });
        setCurrentRows(resp.rows);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to fetch drill-down data";
        setError(msg);
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
    (nextDimension: string, clickedValueOverride?: string | null) => {
      const effectiveClickValue = clickedValueOverride ?? pendingClickValue;
      if (!effectiveClickValue || !nextDimension) {
        setIsDimensionPickerOpen(false);
        return;
      }

      const newLevel: DrillLevel = {
        dimension: currentDimension,
        clickedValue: effectiveClickValue,
        nextDimension,
      };
      const newStack = [...drillStack, newLevel];

      setDrillStack(newStack);
      setIsDimensionPickerOpen(false);
      setSelectedNextDimension("");
      setPendingClickValue(null);
      fetchDrillData(nextDimension, buildFilters(newStack));
    },
    [pendingClickValue, currentDimension, drillStack, fetchDrillData, buildFilters],
  );

  const handleDatumClick = useCallback(
    (rawValue: unknown) => {
      if (!supportsDrill) return;

      const clickedValue = toDisplayLabel(rawValue);
      if (!clickedValue || clickedValue === "NULL") return;

      const topCandidate = topRecommendation?.name ?? drillCandidates[0] ?? "";
      setPendingClickValue(clickedValue);
      setSelectedNextDimension(topCandidate);

      if (canAutoDrill && topCandidate) {
        void executeDrill(topCandidate, clickedValue);
        return;
      }

      setIsDimensionPickerOpen(true);
    },
    [supportsDrill, topRecommendation?.name, drillCandidates, canAutoDrill, executeDrill],
  );

  const confirmDrill = useCallback(() => {
    executeDrill(selectedNextDimension);
  }, [executeDrill, selectedNextDimension]);

  const autoPickDrill = useCallback(() => {
    const topCandidate = topRecommendation?.name ?? drillCandidates[0];
    if (!topCandidate) {
      setIsDimensionPickerOpen(false);
      setPendingClickValue(null);
      setSelectedNextDimension("");
      return;
    }
    executeDrill(topCandidate);
  }, [topRecommendation?.name, drillCandidates, executeDrill]);

  const handleBreadcrumbClick = useCallback(
    (levelIndex: number) => {
      if (levelIndex === -1) {
        setDrillStack([]);
        setCurrentRows(initialRows);
        setPendingClickValue(null);
        setIsDimensionPickerOpen(false);
        setSelectedNextDimension("");
        setError(null);
        return;
      }

      const newStack = drillStack.slice(0, levelIndex + 1);
      const nextDimension = newStack.at(-1)?.nextDimension ?? startDimension;
      setDrillStack(newStack);
      setPendingClickValue(null);
      setIsDimensionPickerOpen(false);
      setSelectedNextDimension("");
      setError(null);
      fetchDrillData(nextDimension, buildFilters(newStack));
    },
    [drillStack, initialRows, fetchDrillData, buildFilters, startDimension],
  );

  const chartType = chartSpec.chart.type;
  const { labels, values, data: chartData } = useMemo(
    () =>
      buildCategoricalSeries(currentRows, {
        xField: currentDimension,
        metricCandidates,
      }),
    [currentRows, currentDimension, metricCandidates],
  );
  const pieData = useMemo(() => buildPieData(labels, values), [labels, values]);
  const histogramData = useMemo(() => buildHistogramData(currentRows, metricCandidates), [currentRows, metricCandidates]);

  const bindClickHandler = useCallback(
    (event: unknown) => {
      const datum = (event as { data?: { data?: Record<string, unknown> } })?.data?.data;
      handleDatumClick(datum?.type ?? datum?.category ?? datum?.[currentDimension]);
    },
    [handleDatumClick, currentDimension],
  );

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
            x: { title: currentDimension, labelFill: "#475569" },
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
          x: { title: currentDimension, labelFill: "#475569" },
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
            {startDimension}
          </button>

          {drillStack.map((level, index) => (
            <span key={`${level.dimension}-${level.clickedValue}-${level.nextDimension}`} className="flex items-center gap-1">
              <ChevronRight className="w-3 h-3 text-slate-400" />
              <button
                onClick={() => handleBreadcrumbClick(index)}
                className={`px-2 py-1 rounded-md transition-colors font-medium ${
                  index === drillStack.length - 1
                    ? "text-indigo-700 bg-indigo-100"
                    : "text-slate-600 hover:text-indigo-600 hover:bg-indigo-50"
                }`}
              >
                {level.clickedValue}
              </button>
            </span>
          ))}

          <ChevronRight className="w-3 h-3 text-slate-400" />
          <span className="px-2 py-1 text-indigo-500 font-medium italic">{currentDimension}</span>

          {supportsDrill ? (
            <div className="ml-auto flex items-center gap-2">
              <span className="text-slate-400 italic">
                {canAutoDrill && topRecommendation
                  ? `Quick drill targets ${topRecommendation.name}`
                  : "Click to choose the next drill dimension"}
              </span>
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
            </div>
          ) : (
            <span className="ml-auto text-slate-400 italic">
              {chartType === "histogram" ? "Histogram drilldown is not available" : "No deeper dimensions available"}
            </span>
          )}
        </div>
      )}

      {drillStack.length === 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-1.5 bg-indigo-50/50 border-b border-indigo-100/50 rounded-t-xl text-xs flex-shrink-0">
          <span className="text-indigo-500 font-medium">
            {supportsDrill
              ? canAutoDrill && topRecommendation
                ? `Click a ${chartType === "pie" ? "slice" : chartType === "line" ? "point" : "bar"} to quick-drill into ${topRecommendation.name}`
                : `Click a ${chartType === "pie" ? "slice" : chartType === "line" ? "point" : "bar"} to choose the next drill dimension`
              : chartType === "histogram"
              ? "Histogram shows the filtered distribution of the selected metric"
              : "Drilldown is not available for this view"}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-slate-400">
              {supportsDrill && topRecommendation
                ? `${topRecommendation.name} • ${topRecommendation.recommendationLabel}`
                : supportsDrill && configuredHierarchy.length > 0
                ? `Recommended path: ${configuredHierarchy.join(" -> ")}`
                : supportsDrill
                ? `${drillCandidates.length} dimensions available`
                : metricLabel}
            </span>
            {supportsDrill ? (
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
              Selected value: <span className="font-medium">{pendingClickValue}</span>
            </p>
            {topRecommendation ? (
              <p className="mt-1 text-[11px] text-indigo-700">
                Best match: <span className="font-medium">{topRecommendation.name}</span> • {topRecommendation.recommendationLabel}
              </p>
            ) : null}
            <select
              value={selectedNextDimension}
              onChange={(event) => setSelectedNextDimension(event.target.value)}
              className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900"
            >
              {rankedDrillCandidates.map((candidate) => (
                <option key={candidate.name} value={candidate.name}>
                  {candidate.name}
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
                  setPendingClickValue(null);
                  setSelectedNextDimension("");
                }}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={autoPickDrill}
                className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-sm text-indigo-700 hover:bg-indigo-100"
              >
                Auto Pick Best
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
