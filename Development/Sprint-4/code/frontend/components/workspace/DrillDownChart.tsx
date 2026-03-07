"use client";

/**
 * DrillDownChart — Plotly-based chart with multi-level drill-down.
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
import dynamic from "next/dynamic";
import type { ChartSpecV1 } from "@/lib/types/chartspec";
import type { AggregateFilter, DatasetProfileAPI } from "@/lib/api-types";
import { apiClient } from "@/lib/api";
import { useTableProfile } from "@/lib/hooks";
import { ChevronRight, RotateCcw, Loader2 } from "lucide-react";

/* ── Plotly (client-only) ─────────────────────────────────────── */
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

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
  const handleChartClick = useCallback(
    (event: Readonly<Plotly.PlotMouseEvent>) => {
      if (!canDrill || !event.points || event.points.length === 0) return;

      const point = event.points[0];
      // For pie charts, the label is in point.label; for bar/line it's in point.x
      const ptAny = point as unknown as Record<string, unknown>;
      const rawValue = ptAny.label ?? ptAny.x ?? "";
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

  /* ── Build Plotly trace ── */
  const trace = useMemo((): Partial<Plotly.Data> => {
    if (chartType === "pie") {
      return {
        type: "pie" as const,
        values: y,
        labels: x,
        textinfo: "percent" as const,
        textposition: "inside" as const,
        marker: { colors: PALETTE },
        hole: 0.3,
        hoverinfo: "label+value+percent" as const,
      };
    }
    if (chartType === "line") {
      return {
        type: "scatter",
        mode: "lines+markers" as const,
        x,
        y,
        line: { color: "#8b5cf6", width: 3 },
        marker: { color: "#8b5cf6", size: 8 },
        fill: "tozeroy" as const,
        fillcolor: "rgba(139, 92, 246, 0.1)",
      };
    }
    if (chartType === "histogram") {
      return {
        type: "histogram",
        x: y,
        marker: { color: "#4f46e5", opacity: 0.8 },
        nbinsx: 10,
      } as unknown as Partial<Plotly.Data>;
    }
    // Default: bar
    return {
      type: "bar",
      x,
      y,
      marker: {
        color: y.map((_, i) => PALETTE[i % PALETTE.length]),
        opacity: 0.9,
      },
    };
  }, [chartType, x, y]);

  /* ── Layout ── */
  const layout = useMemo((): Partial<Plotly.Layout> => ({
    title: {
      text: `${metricLabel} by ${currentDimension}`,
      font: { color: "#1e293b", size: 15, family: "Inter, system-ui, sans-serif" },
    },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { color: "#64748b", family: "Inter, system-ui, sans-serif" },
    xaxis: {
      gridcolor: "#e2e8f0",
      title: { text: currentDimension, font: { color: "#475569", size: 12 } },
      tickfont: { color: "#475569" },
    },
    yaxis: {
      gridcolor: "#e2e8f0",
      title: { text: metricLabel, font: { color: "#475569", size: 12 } },
      tickfont: { color: "#475569" },
    },
    margin: { t: 50, b: 60, l: 80, r: 40 },
    showlegend: chartType === "pie",
    legend: { orientation: "h" as const, y: -0.2 },
  }), [metricLabel, currentDimension, chartType]);

  /* ── Cursor style — show pointer when drillable ── */
  const plotRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!plotRef.current) return;
    const bars = plotRef.current.querySelectorAll<SVGElement>(".plot-container .trace .point, .plot-container .trace path.surface, .plot-container .slice");
    bars.forEach((el) => {
      el.style.cursor = canDrill ? "pointer" : "default";
    });
  });

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
      <div ref={plotRef} className="flex-1 min-h-0 relative">
        <Plot
          data={[trace as Plotly.Data]}
          layout={layout}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: "100%", height: "100%" }}
          onClick={canDrill ? handleChartClick : undefined}
        />
      </div>
    </div>
  );
}
