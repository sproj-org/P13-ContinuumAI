"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { Column, Histogram, Line, Pie } from "@ant-design/plots";
import type { ChartSpecV1 } from "@/lib/types/chartspec";
import type { AggregateFilter, DatasetProfileAPI } from "@/lib/api-types";
import { apiClient } from "@/lib/api";
import { useTableProfile } from "@/lib/hooks";
import { getConfiguredNextDimensions, resolveMartDrillHierarchy } from "@/lib/mart-drill-utils";
import { ChevronRight, RotateCcw, Loader2 } from "lucide-react";

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
}

const PALETTE = ["#8b5cf6", "#3b82f6", "#4f46e5", "#6366f1", "#f59e0b", "#ef4444", "#10b981", "#ec4899"];

const OP_MAP: Record<string, AggregateFilter["op"]> = {
  "=": "eq",
  "!=": "ne",
  ">": "gt",
  ">=": "gte",
  "<": "lt",
  "<=": "lte",
  in: "in",
};

const DRILLABLE_ROLES = new Set(["dimension", "datetime", "temporal", "id", "text", "boolean"]);
const TEMPORAL_ROLES = new Set(["datetime", "temporal"]);

function keywordScore(name: string, current: string): number {
  const lower = name.toLowerCase();
  const currentLower = current.toLowerCase();
  let score = 0;

  if (lower.includes("sku") || lower.includes("product") || lower.includes("item")) score += 8;
  if (lower.includes("store") || lower.includes("city") || lower.includes("region")) score += 5;
  if (lower.includes("category") || lower.includes("segment") || lower.includes("channel")) score += 4;
  if (lower.includes("date") || lower.includes("day") || lower.includes("month")) score -= 2;
  if (currentLower.includes("store") && (lower.includes("sku") || lower.includes("product"))) score += 6;

  return score;
}

function roleScore(role: string): number {
  if (role === "id") return 6;
  if (role === "dimension" || role === "text") return 5;
  if (role === "boolean") return 3;
  if (TEMPORAL_ROLES.has(role)) return 1;
  return 0;
}

function rankDrillCandidates(
  profile: DatasetProfileAPI,
  martId: string,
  currentDimension: string,
  usedDimensions: Set<string>,
): string[] {
  const availableColumns = profile.columns.map((column) => column.name);
  const configuredNext = getConfiguredNextDimensions({
    martId,
    currentDimension,
    usedDimensions,
    availableColumns,
  });

  const ranked = profile.columns
    .filter((column) => DRILLABLE_ROLES.has(column.effective_role))
    .filter((column) => column.name !== currentDimension)
    .filter((column) => !usedDimensions.has(column.name))
    .map((column) => {
      const score =
        keywordScore(column.name, currentDimension) +
        roleScore(column.effective_role) +
        Math.min(column.distinct_count, 1000) / 100;

      return {
        name: column.name,
        score,
        distinctCount: column.distinct_count,
      };
    })
    .sort((left, right) => {
      if (right.score !== left.score) return right.score - left.score;
      if (right.distinctCount !== left.distinctCount) return right.distinctCount - left.distinctCount;
      return left.name.localeCompare(right.name);
    });

  const configuredSet = new Set(configuredNext);
  const heuristic = ranked.map((item) => item.name).filter((name) => !configuredSet.has(name));
  return [...configuredNext, ...heuristic];
}

function toDisplayLabel(value: unknown): string {
  if (value == null) return "NULL";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return `${value}`;
  return JSON.stringify(value);
}

export default function DrillDownChart({
  chartSpec,
  rows: initialRows,
  datasetId,
  profile: externalProfile,
  height = "100%",
}: Readonly<DrillDownChartProps>) {
  const { data: fetchedProfile } = useTableProfile(datasetId, externalProfile ? null : chartSpec.table);
  const profile = externalProfile ?? fetchedProfile ?? null;

  const [drillStack, setDrillStack] = useState<DrillLevel[]>([]);
  const [currentRows, setCurrentRows] = useState<ChartRows>(initialRows);
  const [pendingClickValue, setPendingClickValue] = useState<string | null>(null);
  const [selectedNextDimension, setSelectedNextDimension] = useState<string>("");
  const [isDimensionPickerOpen, setIsDimensionPickerOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chartIdRef = useRef<string>("");
  const chartId = `${chartSpec.table}:${chartSpec.encoding.x.field}:${chartSpec.encoding.y[0]?.field}`;
  useEffect(() => {
    if (chartIdRef.current !== chartId) {
      chartIdRef.current = chartId;
      setDrillStack([]);
      setCurrentRows(initialRows);
      setPendingClickValue(null);
      setIsDimensionPickerOpen(false);
      setSelectedNextDimension("");
      setError(null);
    }
  }, [chartId, initialRows]);

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

  const drillCandidates = useMemo(() => {
    if (!profile) return [];
    return rankDrillCandidates(profile, chartSpec.table, currentDimension, usedDimensions);
  }, [profile, chartSpec.table, currentDimension, usedDimensions]);

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

  const canDrill = drillCandidates.length > 0;
  const metric = chartSpec.encoding.y[0];
  const metricField = metric?.field ?? "agg_value";
  const aggregation = metric?.aggregation ?? "sum";
  const metricLabel = `${aggregation.toUpperCase()}(${metricField})`;

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

  const handleDatumClick = useCallback(
    (rawValue: unknown) => {
      if (!canDrill) return;

      const clickedValue = toDisplayLabel(rawValue);
      if (!clickedValue || clickedValue === "NULL") return;

      setPendingClickValue(clickedValue);
      setSelectedNextDimension(drillCandidates[0] ?? "");
      setIsDimensionPickerOpen(true);
    },
    [canDrill, drillCandidates],
  );

  const executeDrill = useCallback(
    (nextDimension: string) => {
      if (!pendingClickValue || !nextDimension) {
        setIsDimensionPickerOpen(false);
        return;
      }

      const newLevel: DrillLevel = {
        dimension: currentDimension,
        clickedValue: pendingClickValue,
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

  const confirmDrill = useCallback(() => {
    executeDrill(selectedNextDimension);
  }, [executeDrill, selectedNextDimension]);

  const autoPickDrill = useCallback(() => {
    const topCandidate = drillCandidates[0];
    if (!topCandidate) {
      setIsDimensionPickerOpen(false);
      setPendingClickValue(null);
      setSelectedNextDimension("");
      return;
    }
    executeDrill(topCandidate);
  }, [drillCandidates, executeDrill]);

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
      fetchDrillData(nextDimension, buildFilters(newStack));
    },
    [drillStack, initialRows, fetchDrillData, buildFilters, startDimension],
  );

  const { x, y } = useMemo(() => {
    const xField = currentDimension;
    const isRoot = drillStack.length === 0;
    const aliasField = metric?.alias ?? "agg_value";
    const yField = isRoot ? aliasField : "agg_value";
    return {
      x: currentRows.map((row) => toDisplayLabel(row[xField])),
      y: currentRows.map((row) => Number(row[yField] ?? 0)),
    };
  }, [currentRows, currentDimension, metric?.alias, drillStack.length]);

  const chartType = chartSpec.chart.type;
  const chartData = useMemo(() => x.map((category, index) => ({ category, value: y[index] ?? 0 })), [x, y]);
  const pieData = useMemo(() => x.map((type, index) => ({ type, value: y[index] ?? 0 })), [x, y]);
  const histogramData = useMemo(() => y.map((value) => ({ value })), [y]);

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
          scale={{ color: { range: PALETTE } }}
          interaction={{ elementSelect: { single: true } }}
          onReady={({ chart }) => {
            if (!canDrill) return;
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
          shapeField="smooth"
          style={{ stroke: "#8b5cf6" }}
          axis={{
            x: { title: currentDimension, labelFill: "#475569" },
            y: { title: metricLabel, labelFill: "#475569" },
          }}
          interaction={{ elementSelect: { single: true } }}
          onReady={({ chart }) => {
            if (!canDrill) return;
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
        scale={{ color: { range: PALETTE } }}
        interaction={{ elementSelect: { single: true } }}
        onReady={({ chart }) => {
          if (!canDrill) return;
          chart.on("element:click", bindClickHandler);
        }}
        height={320}
      />
    );
  };

  return (
    <div className="flex flex-col h-full relative" style={{ height }}>
      {drillStack.length > 0 && (
        <div className="flex items-center gap-1 px-3 py-2 bg-gradient-to-r from-indigo-50 to-violet-50 border-b border-indigo-100 rounded-t-xl text-xs flex-shrink-0">
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

          {canDrill ? (
            <span className="ml-auto text-slate-400 italic">Click to choose next drill dimension</span>
          ) : (
            <span className="ml-auto text-slate-400 italic">No deeper dimensions available</span>
          )}
        </div>
      )}

      {drillStack.length === 0 && (
        <div className="flex items-center justify-between px-3 py-1.5 bg-indigo-50/50 border-b border-indigo-100/50 rounded-t-xl text-xs flex-shrink-0">
          <span className="text-indigo-500 font-medium">Click a {chartType === "pie" ? "slice" : "bar"} to choose the next drill dimension</span>
          <span className="text-slate-400">
            {configuredHierarchy.length > 0
              ? `Recommended path: ${configuredHierarchy.join(" -> ")}`
              : `${drillCandidates.length} dimensions available`}
          </span>
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
            <select
              value={selectedNextDimension}
              onChange={(event) => setSelectedNextDimension(event.target.value)}
              className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900"
            >
              {drillCandidates.map((dimension) => (
                <option key={dimension} value={dimension}>
                  {preferredNextDimensions.includes(dimension) ? `${dimension} (recommended)` : dimension}
                </option>
              ))}
            </select>
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

      <div className={`flex-1 min-h-0 relative ${canDrill ? "cursor-pointer" : ""}`}>{renderAntVChart()}</div>
    </div>
  );
}
