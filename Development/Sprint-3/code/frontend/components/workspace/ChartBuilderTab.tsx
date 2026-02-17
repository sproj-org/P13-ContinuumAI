"use client";

import { useState, useMemo, useEffect } from "react";
import { useAppStore, ChartConfig } from "@/lib/store";
import { useAggregations, useTableProfile, useChartData } from "@/lib/hooks";
import { 
  transformColumnProfile,
  type ColumnRole,
} from "@/lib/transformers";
import { motion, AnimatePresence } from "framer-motion";
import dynamic from "next/dynamic";
import {
  DndContext,
  DragEndEvent,
  DragStartEvent,
  DragOverlay,
  useDraggable,
  useDroppable,
} from "@dnd-kit/core";
import {
  BarChart3,
  LineChart,
  PieChart,
  Activity,
  Hash,
  Calendar,
  GripVertical,
  X,
  Sparkles,
  RefreshCw,
  Loader2,
  AlertTriangle,
} from "lucide-react";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

const chartTypes: { id: ChartConfig["chartType"]; label: string; icon: React.ReactNode }[] = [
  { id: "bar", label: "Bar", icon: <BarChart3 className="w-4 h-4" /> },
  { id: "line", label: "Line", icon: <LineChart className="w-4 h-4" /> },
  { id: "pie", label: "Pie", icon: <PieChart className="w-4 h-4" /> },
  { id: "histogram", label: "Histogram", icon: <Activity className="w-4 h-4" /> },
];

const aggregationFns: { id: ChartConfig["aggregationFn"]; label: string }[] = [
  { id: "sum", label: "Sum" },
  { id: "avg", label: "Average" },
  { id: "count", label: "Count" },
  { id: "min", label: "Min" },
  { id: "max", label: "Max" },
];

const roleColors: Record<ColumnRole, { bg: string; text: string; border: string }> = {
  dimension: { bg: "bg-blue-500/20", text: "text-blue-400", border: "border-blue-500/30" },
  measure: { bg: "bg-emerald-500/20", text: "text-emerald-400", border: "border-emerald-500/30" },
  temporal: { bg: "bg-amber-500/20", text: "text-amber-400", border: "border-amber-500/30" },
};

const roleIcons: Record<ColumnRole, React.ReactNode> = {
  dimension: <Hash className="w-3.5 h-3.5" />,
  measure: <BarChart3 className="w-3.5 h-3.5" />,
  temporal: <Calendar className="w-3.5 h-3.5" />,
};

// Draggable Field Component
function DraggableField({ column }: { column: { name: string; role: ColumnRole } }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: column.name,
    data: column,
  });

  const roleStyle = roleColors[column.role];

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-grab active:cursor-grabbing transition-all ${
        isDragging
          ? "opacity-50 bg-[#5237ff]/20 border border-[#5237ff]/30"
          : `${roleStyle.bg} border ${roleStyle.border} hover:brightness-110`
      }`}
    >
      <GripVertical className="w-3 h-3 text-gray-500" />
      <span className={`${roleStyle.text}`}>{roleIcons[column.role]}</span>
      <span className="text-sm text-gray-200 truncate">{column.name}</span>
    </div>
  );
}

// Drop Zone Component
function DropZone({
  id,
  label,
  value,
  onClear,
  acceptRoles,
}: {
  id: string;
  label: string;
  value: string | null;
  onClear: () => void;
  acceptRoles: ColumnRole[];
}) {
  const { isOver, setNodeRef } = useDroppable({ id });

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-gray-400">{label}</label>
      <div
        ref={setNodeRef}
        className={`min-h-[48px] rounded-xl border-2 border-dashed transition-all flex items-center px-4 ${
          isOver
            ? "border-[#5237ff] bg-[#5237ff]/10"
            : value
            ? "border-white/20 bg-white/5"
            : "border-white/10 bg-white/[0.03]"
        }`}
      >
        {value ? (
          <div className="flex items-center justify-between w-full">
            <span className="text-white text-sm">{value}</span>
            <button
              onClick={onClear}
              className="p-1 hover:bg-white/10 rounded-lg transition-colors"
            >
              <X className="w-4 h-4 text-gray-400" />
            </button>
          </div>
        ) : (
          <span className="text-gray-500 text-sm">
            Drop {acceptRoles.join(" or ")} here
          </span>
        )}
      </div>
    </div>
  );
}

export default function ChartBuilderTab() {
  const {
    selectedAggregation,
    setSelectedAggregation,
    chartConfig,
    setChartConfig,
    resetChartConfig,
  } = useAppStore();

  const [activeDragId, setActiveDragId] = useState<string | null>(null);

  const { data: aggregationsData } = useAggregations();
  const { data: profile, isLoading } = useTableProfile(selectedAggregation);
  const aggregationTables = aggregationsData?.aggregations ?? [];
  
  // Transform columns for frontend use
  const transformedColumns = useMemo(() => {
    return profile?.columns.map(transformColumnProfile) ?? [];
  }, [profile]);

  // Group columns by role and create a map for quick lookup
  const { groupedColumns, columnRoleMap } = useMemo(() => {
    if (transformedColumns.length === 0) {
      return {
        groupedColumns: { dimensions: [], measures: [], temporal: [] },
        columnRoleMap: new Map<string, ColumnRole>(),
      };
    }

    const roleMap = new Map<string, ColumnRole>();
    transformedColumns.forEach((c) => roleMap.set(c.name, c.role));

    return {
      groupedColumns: {
        dimensions: transformedColumns.filter((c) => c.role === "dimension"),
        measures: transformedColumns.filter((c) => c.role === "measure"),
        temporal: transformedColumns.filter((c) => c.role === "temporal"),
      },
      columnRoleMap: roleMap,
    };
  }, [transformedColumns]);

  // Get valid aggregation functions based on the selected y-axis column role
  const validAggregations = useMemo(() => {
    if (!chartConfig.yAxis) {
      return aggregationFns; // All aggregations available when no column selected
    }

    const role = columnRoleMap.get(chartConfig.yAxis);

    if (role === "measure") {
      // Measures support all aggregations
      return aggregationFns;
    } else if (role === "temporal") {
      // Temporal columns: COUNT, MIN, MAX (no SUM/AVG on dates)
      return aggregationFns.filter((agg) => ["count", "min", "max"].includes(agg.id));
    } else {
      // Dimensions: only COUNT makes sense
      return aggregationFns.filter((agg) => agg.id === "count");
    }
  }, [chartConfig.yAxis, columnRoleMap]);

  // Auto-switch aggregation when y-axis changes to an incompatible column
  useEffect(() => {
    if (chartConfig.yAxis && validAggregations.length > 0) {
      const currentAggValid = validAggregations.some((agg) => agg.id === chartConfig.aggregationFn);
      if (!currentAggValid) {
        // Switch to first valid aggregation
        setChartConfig({ aggregationFn: validAggregations[0].id });
      }
    }
  }, [chartConfig.yAxis, chartConfig.aggregationFn, validAggregations, setChartConfig]);

  // Fetch real chart data from the database
  const { 
    data: chartData, 
    isLoading: isChartLoading, 
    error: chartError 
  } = useChartData(
    selectedAggregation,
    chartConfig.xAxis,
    chartConfig.yAxis,
    chartConfig.aggregationFn
  );

  const handleDragStart = (event: DragStartEvent) => {
    setActiveDragId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveDragId(null);

    const { active, over } = event;
    if (!over) return;

    const columnName = active.id as string;
    const dropZone = over.id as string;

    if (dropZone === "x-axis") {
      setChartConfig({ xAxis: columnName });
    } else if (dropZone === "y-axis") {
      setChartConfig({ yAxis: columnName });
    } else if (dropZone === "color-by") {
      setChartConfig({ colorBy: columnName });
    }
  };

  const activeColumn = activeDragId
    ? transformedColumns.find((c) => c.name === activeDragId)
    : null;

  return (
    <DndContext onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <div className="flex h-full">
        {/* Left Panel - Fields */}
        <div className="w-64 border-r border-white/10 bg-[#060010]/50 overflow-y-auto p-4">
          {/* Aggregation Selector */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
              Aggregation
            </h3>
            <select
              value={selectedAggregation || ""}
              onChange={(e) => {
                setSelectedAggregation(e.target.value || null);
                resetChartConfig();
              }}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-[#5237ff]/50"
            >
              <option value="">Select table</option>
              {aggregationTables.map((table) => (
                <option key={table.table_name} value={table.table_name}>
                  {table.label ?? table.table_name}
                </option>
              ))}
            </select>
          </div>

          {/* Fields */}
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 text-[#5237ff] animate-spin" />
            </div>
          ) : transformedColumns.length > 0 ? (
            <>
              {/* Dimensions */}
              <div className="mb-6">
                <h3 className="text-sm font-medium text-blue-400 mb-3 flex items-center gap-2">
                  <Hash className="w-4 h-4" />
                  Dimensions
                </h3>
                <div className="space-y-2">
                  {groupedColumns.dimensions.map((col) => (
                    <DraggableField key={col.name} column={{ name: col.name, role: col.role }} />
                  ))}
                </div>
              </div>

              {/* Measures */}
              <div className="mb-6">
                <h3 className="text-sm font-medium text-emerald-400 mb-3 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4" />
                  Measures
                </h3>
                <div className="space-y-2">
                  {groupedColumns.measures.map((col) => (
                    <DraggableField key={col.name} column={{ name: col.name, role: col.role }} />
                  ))}
                </div>
              </div>

              {/* Temporal */}
              <div className="mb-6">
                <h3 className="text-sm font-medium text-amber-400 mb-3 flex items-center gap-2">
                  <Calendar className="w-4 h-4" />
                  Temporal
                </h3>
                <div className="space-y-2">
                  {groupedColumns.temporal.map((col) => (
                    <DraggableField key={col.name} column={{ name: col.name, role: col.role }} />
                  ))}
                </div>
              </div>
            </>
          ) : selectedAggregation ? (
            <p className="text-gray-500 text-sm text-center">No columns found</p>
          ) : null}
        </div>

        {/* Center - Chart Canvas */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 p-6 overflow-y-auto">
            <AnimatePresence mode="wait">
              {!chartConfig.xAxis || !chartConfig.yAxis ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="h-full flex items-center justify-center"
                >
                  <div className="text-center">
                    <div className="w-20 h-20 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mx-auto mb-4">
                      <Sparkles className="w-10 h-10 text-gray-600" />
                    </div>
                    <h3 className="text-xl font-medium text-gray-400 mb-2">
                      Build Your Chart
                    </h3>
                    <p className="text-gray-500 max-w-sm">
                      Drag fields from the left panel to the axis drop zones on the right
                    </p>
                  </div>
                </motion.div>
              ) : isChartLoading ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="h-full flex items-center justify-center"
                >
                  <div className="text-center">
                    <Loader2 className="w-12 h-12 text-[#5237ff] mx-auto mb-4 animate-spin" />
                    <h3 className="text-lg font-medium text-gray-400">Loading chart data...</h3>
                    <p className="text-gray-500 text-sm mt-1">Querying database</p>
                  </div>
                </motion.div>
              ) : chartError ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="h-full flex items-center justify-center"
                >
                  <div className="text-center">
                    <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-400 mb-2">Failed to load chart data</h3>
                    <p className="text-gray-500 text-sm max-w-sm">{chartError.message}</p>
                  </div>
                </motion.div>
              ) : chartData ? (
                <motion.div
                  key={`${chartConfig.xAxis}-${chartConfig.yAxis}-${chartConfig.chartType}`}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="bg-white/5 border border-white/10 rounded-2xl p-6 h-full"
                >
                  <Plot
                    data={[
                      chartConfig.chartType === "pie"
                        ? {
                            type: "pie" as const,
                            values: chartData.y,
                            labels: chartData.x,
                            textinfo: "percent" as const,
                            textposition: "inside" as const,
                            marker: {
                              colors: [
                                "#8b5cf6",
                                "#3b82f6",
                                "#06b6d4",
                                "#10b981",
                                "#f59e0b",
                                "#ef4444",
                              ],
                            },
                            hole: 0.3,
                          }
                        : chartConfig.chartType === "line"
                        ? {
                            type: "scatter",
                            mode: "lines+markers",
                            x: chartData.x,
                            y: chartData.y,
                            line: { color: "#8b5cf6", width: 3 },
                            marker: { color: "#8b5cf6", size: 8 },
                            fill: "tozeroy",
                            fillcolor: "rgba(139, 92, 246, 0.1)",
                          }
                        : chartConfig.chartType === "histogram"
                        ? ({
                            type: "histogram",
                            x: chartData.y,
                            marker: { color: "#10b981", opacity: 0.8 },
                            nbinsx: 10,
                          } as unknown as Plotly.Data)
                        : {
                            type: "bar",
                            x: chartData.x,
                            y: chartData.y,
                            marker: {
                              color: chartData.y.map((_, i) =>
                                [
                                  "#8b5cf6",
                                  "#3b82f6",
                                  "#06b6d4",
                                  "#10b981",
                                  "#f59e0b",
                                  "#ef4444",
                                ][i % 6]
                              ),
                              opacity: 0.9,
                            },
                          },
                    ]}
                    layout={{
                      title: {
                        text: chartData.title,
                        font: { color: "#fff", size: 16 },
                      },
                      paper_bgcolor: "transparent",
                      plot_bgcolor: "transparent",
                      font: { color: "#94a3b8" },
                      xaxis: {
                        gridcolor: "#334155",
                        title: { text: chartConfig.xAxis || "" },
                      },
                      yaxis: {
                        gridcolor: "#334155",
                        title: { text: chartConfig.yAxis || "" },
                      },
                      margin: { t: 60, b: 60, l: 80, r: 40 },
                      showlegend: chartConfig.chartType === "pie",
                      legend: { orientation: "h", y: -0.2 },
                    }}
                    config={{ displayModeBar: false, responsive: true }}
                    style={{ width: "100%", height: "100%", minHeight: "400px" }}
                  />
                </motion.div>
              ) : null}
            </AnimatePresence>
          </div>
        </div>

        {/* Right Panel - Config */}
        <div className="w-72 border-l border-white/10 bg-[#060010]/50 overflow-y-auto p-4 space-y-6">
          {/* Chart Type */}
          <div>
            <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
              Chart Type
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {chartTypes.map((type) => (
                <button
                  key={type.id}
                  onClick={() => setChartConfig({ chartType: type.id })}
                  className={`flex items-center gap-2 px-3 py-2.5 rounded-xl transition-all ${
                    chartConfig.chartType === type.id
                      ? "bg-[#5237ff]/20 border border-[#5237ff]/30 text-[#7b69ff]"
                      : "bg-white/5 border border-white/10 text-gray-400 hover:bg-white/10 hover:text-white"
                  }`}
                >
                  {type.icon}
                  <span className="text-sm">{type.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Axis Mapping */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider">
              Axis Mapping
            </h3>

            <DropZone
              id="x-axis"
              label="X-Axis"
              value={chartConfig.xAxis}
              onClear={() => setChartConfig({ xAxis: null })}
              acceptRoles={["dimension", "temporal"]}
            />

            <DropZone
              id="y-axis"
              label="Y-Axis"
              value={chartConfig.yAxis}
              onClear={() => setChartConfig({ yAxis: null })}
              acceptRoles={["measure"]}
            />

            <DropZone
              id="color-by"
              label="Color / Group"
              value={chartConfig.colorBy}
              onClear={() => setChartConfig({ colorBy: null })}
              acceptRoles={["dimension"]}
            />
          </div>

          {/* Aggregation */}
          <div>
            <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
              Aggregation
            </h3>
            <div className="flex flex-wrap gap-2">
              {aggregationFns.map((agg) => {
                const isValid = validAggregations.some((v) => v.id === agg.id);
                return (
                  <button
                    key={agg.id}
                    onClick={() => isValid && setChartConfig({ aggregationFn: agg.id })}
                    disabled={!isValid}
                    title={!isValid ? `${agg.label} is not available for this column type` : undefined}
                    className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                      !isValid
                        ? "bg-white/5 border border-white/5 text-gray-600 cursor-not-allowed opacity-50"
                        : chartConfig.aggregationFn === agg.id
                        ? "bg-emerald-500/20 border border-emerald-500/30 text-emerald-300"
                        : "bg-white/5 border border-white/10 text-gray-400 hover:text-white"
                    }`}
                  >
                    {agg.label}
                  </button>
                );
              })}
            </div>
            {chartConfig.yAxis && validAggregations.length < aggregationFns.length && (
              <p className="text-xs text-gray-500 mt-2">
                Some aggregations are disabled for {columnRoleMap.get(chartConfig.yAxis)} columns
              </p>
            )}
          </div>

          {/* Reset Button */}
          <button
            onClick={resetChartConfig}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-gray-400 hover:text-white hover:bg-white/10 transition-all"
          >
            <RefreshCw className="w-4 h-4" />
            Reset Chart
          </button>
        </div>
      </div>

      {/* Drag Overlay */}
      <DragOverlay>
        {activeColumn && (
          <div
            className={`flex items-center gap-2 px-3 py-2 rounded-lg shadow-xl ${
              roleColors[activeColumn.role].bg
            } border ${roleColors[activeColumn.role].border}`}
          >
            <GripVertical className="w-3 h-3 text-gray-500" />
            <span className={roleColors[activeColumn.role].text}>
              {roleIcons[activeColumn.role]}
            </span>
            <span className="text-sm text-gray-200">{activeColumn.name}</span>
          </div>
        )}
      </DragOverlay>
    </DndContext>
  );
}
