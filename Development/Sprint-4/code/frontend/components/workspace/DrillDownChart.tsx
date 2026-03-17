"use client";

/**
 * DrillDownChart — AntV-based chart with multi-level drill-down.
 *
 * Architecture:
 * 1. Receives the original chartSpec + rows from the saved chart (level 0).
 * 2. Reads the mart's column profile to auto-detect a drill hierarchy
 *    (all dimension columns sorted ascending by cardinality, starting from
 *    the current x-field downward).
 * 3. On bar/slice click → pushes a filter, advances to next dimension,
 *    fetches fresh aggregated data from POST /datasets/{id}/query/aggregate.
 * 4. Breadcrumbs allow drill-up to any previous level.
 *
 * Does NOT touch renderChart.tsx — that remains the renderer for
 * ChartBuilder and VizAgent.  This component is used ONLY on DashboardTab.
 */

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { Column, Histogram, Line, Pie } from "@ant-design/plots";
import type { ChartSpecV1 } from "@/lib/types/chartspec";
import type { AggregateFilter, DatasetProfileAPI } from "@/lib/api-types";
import { apiClient } from "@/lib/api";
import { useTableProfile } from "@/lib/hooks";
import { ChevronRight, RotateCcw, Loader2 } from "lucide-react";

/* ── Types ────────────────────────────────────────────────────── */
type ChartRows = Array<Record<string, unknown>>;

interface DrillLevel {
  dimension: string;       // field name being grouped by
  clickedValue: string;    // value that was clicked to reach this level
}

export interface DrillDownChartProps {
  chartSpec: ChartSpecV1;
  rows: ChartRows;              // original level-0 rows from saved chart
  datasetId: string;
  /** Column profile for the mart (from useTableProfile). null/undefined = fetch internally. */
  profile?: DatasetProfileAPI | null;
  /** Chart height CSS value */
  height?: string;
}

/* ── Colours ──────────────────────────────────────────────────── */
const PALETTE = ["#8b5cf6", "#3b82f6", "#4f46e5", "#6366f1", "#f59e0b", "#ef4444", "#10b981", "#ec4899"];

/* ── Filter op mapping from chart spec to aggregate API ── */
const OP_MAP: Record<string, AggregateFilter["op"]> = {
  "=": "eq", "!=": "ne", ">": "gt", ">=": "gte",
  "<": "lt", "<=": "lte", "in": "in",
};

/* ── Helper: dimension columns (role = dimension | datetime | temporal | id | text | boolean) ── */
const DRILLABLE_ROLES = new Set(["dimension", "datetime", "temporal", "id", "text", "boolean"]);

function buildHierarchy(profile: DatasetProfileAPI, startField: string): string[] {
  // Collect all dimension-like columns, sorted by cardinality (ascending)
  const dims = profile.columns
    .filter((c) => DRILLABLE_ROLES.has(c.effective_role))
    .sort((a, b) => a.distinct_count - b.distinct_count);

  // Find position of the start field
  const startIdx = dims.findIndex((c) => c.name === startField);
  if (startIdx === -1) {
    // Start field not in dimensions — just return all dims after it by cardinality
    return dims.map((c) => c.name);
  }

  // Hierarchy = start field + everything with same or higher cardinality after it
  // (skip duplicates and the start field itself which is level 0)
  const hierarchy = [dims[startIdx].name];

  for (let i = startIdx + 1; i < dims.length; i++) {
    // Skip columns with same cardinality as current x-field AND same name (dedup)
    if (dims[i].name !== hierarchy.at(-1)) {
      hierarchy.push(dims[i].name);
    }
  }

  return hierarchy;
}

/* ── Component ────────────────────────────────────────────────── */
export default function DrillDownChart({
  chartSpec,
  rows: initialRows,
  datasetId,
  profile: externalProfile,
  height = "100%",
}: Readonly<DrillDownChartProps>) {
  /* ── Fetch profile internally if not provided ── */
  const { data: fetchedProfile } = useTableProfile(datasetId, externalProfile ? null : chartSpec.table);
  const profile = externalProfile ?? fetchedProfile ?? null;

  /* ── Hierarchy from profile ── */
  const hierarchy = useMemo(() => {
    if (!profile) return [chartSpec.encoding.x.field]; // fallback: just original x
    return buildHierarchy(profile, chartSpec.encoding.x.field);
  }, [profile, chartSpec.encoding.x.field]);

  /* ── Drill state ── */
  const [drillStack, setDrillStack] = useState<DrillLevel[]>([]);
  const [currentRows, setCurrentRows] = useState<ChartRows>(initialRows);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset when chart changes
  const chartIdRef = useRef<string>("");
  const chartId = `${chartSpec.table}:${chartSpec.encoding.x.field}:${chartSpec.encoding.y[0]?.field}`;
  useEffect(() => {
    if (chartIdRef.current !== chartId) {
      chartIdRef.current = chartId;
      setDrillStack([]);
      setCurrentRows(initialRows);
      setError(null);
    }
  }, [chartId, initialRows]);

  /* ── Derived state ── */
  const currentLevel = drillStack.length;
  const currentDimension = hierarchy[Math.min(currentLevel, hierarchy.length - 1)];
  const canDrill = currentLevel < hierarchy.length - 1;
  const metric = chartSpec.encoding.y[0];
  const metricField = metric?.field ?? "agg_value";
  const aggregation = metric?.aggregation ?? "sum";
  const metricLabel = `${aggregation.toUpperCase()}(${metricField})`;

  /* ── Fetch aggregated data for a drill level ── */
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

  /* ── Build filters from drill stack ── */
  const buildFilters = useCallback(
    (stack: DrillLevel[]): AggregateFilter[] => {
      // Combine chart-level filters with drill filters
      const drillFilters: AggregateFilter[] = stack.map((lvl) => ({
        column: lvl.dimension,
        op: "eq" as const,
        value: lvl.clickedValue,
      }));
      // Also include any filters from the original chart spec
      const specFilters: AggregateFilter[] = (chartSpec.filters ?? []).map((f) => ({
        column: f.field,
        op: OP_MAP[f.op] ?? "eq",
        value: f.value,
      }));
      return [...specFilters, ...drillFilters];
    },
    [chartSpec.filters],
  );

  /* ── Click handler — drill down ── */
  const handleDatumClick = useCallback(
    (rawValue: unknown) => {
      if (!canDrill) return;

      let clickedValue: string;
      if (rawValue == null) {
        clickedValue = "";
      } else if (typeof rawValue === "string") {
        clickedValue = rawValue;
      } else if (typeof rawValue === "number" || typeof rawValue === "boolean") {
        clickedValue = `${rawValue}`;
      } else {
        clickedValue = JSON.stringify(rawValue);
      }

      if (!clickedValue || clickedValue === "NULL") return;

      const newLevel: DrillLevel = { dimension: currentDimension, clickedValue };
      const newStack = [...drillStack, newLevel];
      const nextDimension = hierarchy[Math.min(newStack.length, hierarchy.length - 1)];

      setDrillStack(newStack);
      fetchDrillData(nextDimension, buildFilters(newStack));
    },
    [canDrill, currentDimension, drillStack, hierarchy, fetchDrillData, buildFilters],
  );

  /* ── Breadcrumb click — drill up ── */
  const handleBreadcrumbClick = useCallback(
    (levelIndex: number) => {
      if (levelIndex === -1) {
        // Back to root
        setDrillStack([]);
        setCurrentRows(initialRows);
        setError(null);
        return;
      }
      // Drill up to this level (keep filters up to and including this index)
      const newStack = drillStack.slice(0, levelIndex + 1);
      const nextDimension = hierarchy[Math.min(newStack.length, hierarchy.length - 1)];
      setDrillStack(newStack);
      fetchDrillData(nextDimension, buildFilters(newStack));
    },
    [drillStack, hierarchy, initialRows, fetchDrillData, buildFilters],
  );

  /* ── Extract x/y values from current rows ── */
  const { x, y } = useMemo(() => {
    const xField = currentDimension;
    // Initial rows come from the chart-preview endpoint which renames
    // the metric column to the alias (e.g. "metric_value").  Drilled
    // rows come from the raw aggregate API which always uses "agg_value".
    const isRoot = drillStack.length === 0;
    const aliasField = metric?.alias ?? "agg_value";
    const yField = isRoot ? aliasField : "agg_value";
    return {
      x: currentRows.map((row) => {
        const val = row[xField];
        if (val == null) return "NULL";
        if (typeof val === "string") return val;
        if (typeof val === "number" || typeof val === "boolean") return `${val}`;
        return JSON.stringify(val);
      }),
      y: currentRows.map((row) => Number(row[yField] ?? 0)),
    };
  }, [currentRows, currentDimension, metric?.alias, drillStack.length]);

  const chartType = chartSpec.chart.type;
  const chartData = useMemo(
    () => x.map((category, index) => ({ category, value: y[index] ?? 0 })),
    [x, y],
  );
  const pieData = useMemo(
    () => x.map((type, index) => ({ type, value: y[index] ?? 0 })),
    [x, y],
  );
  const histogramData = useMemo(() => y.map((value) => ({ value })), [y]);

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
            chart.on("element:click", (event: unknown) => {
              const datum = (event as { data?: { data?: Record<string, unknown> } })?.data?.data;
              handleDatumClick(datum?.type ?? datum?.[currentDimension]);
            });
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
            chart.on("element:click", (event: unknown) => {
              const datum = (event as { data?: { data?: Record<string, unknown> } })?.data?.data;
              handleDatumClick(datum?.category ?? datum?.[currentDimension]);
            });
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
          chart.on("element:click", (event: unknown) => {
            const datum = (event as { data?: { data?: Record<string, unknown> } })?.data?.data;
            handleDatumClick(datum?.category ?? datum?.[currentDimension]);
          });
        }}
        height={320}
      />
    );
  };

  return (
    <div className="flex flex-col h-full" style={{ height }}>
      {/* ── Breadcrumb bar ── */}
      {drillStack.length > 0 && (
        <div className="flex items-center gap-1 px-3 py-2 bg-gradient-to-r from-indigo-50 to-violet-50 border-b border-indigo-100 rounded-t-xl text-xs flex-shrink-0">
          {/* Reset button */}
          <button
            onClick={() => handleBreadcrumbClick(-1)}
            className="flex items-center gap-1 px-2 py-1 text-indigo-600 hover:text-indigo-800 hover:bg-indigo-100 rounded-md transition-colors font-medium"
            title="Back to top level"
          >
            <RotateCcw className="w-3 h-3" />
            Reset
          </button>

          {/* Root level */}
          <ChevronRight className="w-3 h-3 text-slate-400" />
          <button
            onClick={() => handleBreadcrumbClick(-1)}
            className="px-2 py-1 text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 rounded-md transition-colors font-medium"
          >
            {hierarchy[0]}
          </button>

          {/* Drill levels */}
          {drillStack.map((lvl, idx) => (
            <span key={`${lvl.dimension}-${lvl.clickedValue}`} className="flex items-center gap-1">
              <ChevronRight className="w-3 h-3 text-slate-400" />
              <button
                onClick={() => handleBreadcrumbClick(idx)}
                className={`px-2 py-1 rounded-md transition-colors font-medium ${
                  idx === drillStack.length - 1
                    ? "text-indigo-700 bg-indigo-100"
                    : "text-slate-600 hover:text-indigo-600 hover:bg-indigo-50"
                }`}
              >
                {lvl.clickedValue}
              </button>
            </span>
          ))}

          {/* Current dimension label */}
          <ChevronRight className="w-3 h-3 text-slate-400" />
          <span className="px-2 py-1 text-indigo-500 font-medium italic">
            {currentDimension}
          </span>

          {/* Drill hint */}
          {canDrill && (
            <span className="ml-auto text-slate-400 italic">
              Click a {chartType === "pie" ? "slice" : "bar"} to drill deeper
            </span>
          )}
          {!canDrill && (
            <span className="ml-auto text-slate-400 italic">
              Deepest level reached
            </span>
          )}
        </div>
      )}

      {/* ── Drill hint for level 0 ── */}
      {drillStack.length === 0 && hierarchy.length > 1 && (
        <div className="flex items-center justify-between px-3 py-1.5 bg-indigo-50/50 border-b border-indigo-100/50 rounded-t-xl text-xs flex-shrink-0">
          <span className="text-indigo-500 font-medium">
            🔍 Click a {chartType === "pie" ? "slice" : "bar"} to drill down into {hierarchy[1]}
          </span>
          <span className="text-slate-400">
            {hierarchy.length} levels available
          </span>
        </div>
      )}

      {/* ── Loading overlay ── */}
      {loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/60 backdrop-blur-sm rounded-xl">
          <div className="flex items-center gap-2 px-4 py-2 bg-white rounded-lg shadow-md border border-indigo-100">
            <Loader2 className="w-4 h-4 text-indigo-600 animate-spin" />
            <span className="text-sm text-slate-600">Loading drill-down data…</span>
          </div>
        </div>
      )}

      {/* ── Error message ── */}
      {error && (
        <div className="mx-3 mt-2 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex-shrink-0">
          {error}
          <button
            onClick={() => handleBreadcrumbClick(-1)}
            className="ml-2 underline hover:text-red-900"
          >
            Reset
          </button>
        </div>
      )}

      {/* ── Chart ── */}
      <div className={`flex-1 min-h-0 relative ${canDrill ? "cursor-pointer" : ""}`}>
        {renderAntVChart()}
      </div>
    </div>
  );
}
