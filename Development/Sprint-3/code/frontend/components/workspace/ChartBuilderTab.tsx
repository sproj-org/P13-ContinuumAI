"use client";

import { useState, useMemo, useEffect } from "react";
import { useAppStore, ChartConfig } from "@/lib/store";
import { useTableProfile, useChartsPreview } from "@/lib/hooks";
import {
  transformColumnProfile,
  type ColumnRole,
} from "@/lib/transformers";
import { renderChart } from "@/components/workspace/renderChart";
import type { ChartSpecV1, FilterOperator, FilterSpec } from "@/lib/types/chartspec";
import { motion, AnimatePresence } from "framer-motion";
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
  Plus,
} from "lucide-react";

interface UIChartFilter {
  id: string;
  field: string;
  op: FilterOperator;
  value: string;
}

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

const filterOperators: { id: FilterOperator; label: string }[] = [
  { id: "=", label: "=" },
  { id: "!=", label: "!=" },
  { id: ">", label: ">" },
  { id: ">=", label: ">=" },
  { id: "<", label: "<" },
  { id: "<=", label: "<=" },
  { id: "in", label: "IN" },
  { id: "between", label: "BETWEEN" },
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

function toPrimitive(raw: string): unknown {
  const trimmed = raw.trim();
  if (!trimmed) return trimmed;
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) {
    const asNumber = Number(trimmed);
    if (Number.isFinite(asNumber)) {
      return asNumber;
    }
  }
  return trimmed;
}

function mapFilter(filter: UIChartFilter): FilterSpec | null {
  if (!filter.field) return null;

  if (filter.op === "in") {
    const values = filter.value
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
      .map((item) => toPrimitive(item));
    if (values.length === 0) return null;
    return { field: filter.field, op: "in", value: values };
  }

  if (filter.op === "between") {
    const parts = filter.value
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
      .map((item) => toPrimitive(item));
    if (parts.length < 2) return null;
    return { field: filter.field, op: "between", value: [parts[0], parts[1]] };
  }

  if (!filter.value.trim()) return null;
  return { field: filter.field, op: filter.op, value: toPrimitive(filter.value) };
}

function daysAgoISO(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
}

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
    selectedDatasetId,
    selectedAggregation,
    setSelectedAggregation,
    availableMarts,
    chartConfig,
    setChartConfig,
    resetChartConfig,
  } = useAppStore();

  const [activeDragId, setActiveDragId] = useState<string | null>(null);
  const [validationMessage, setValidationMessage] = useState<string | null>(null);
  const [filters, setFilters] = useState<UIChartFilter[]>([]);
  const [sortTarget, setSortTarget] = useState<"x" | "metric">("metric");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const [resultLimit, setResultLimit] = useState<number>(20);
  const [timeWindow, setTimeWindow] = useState<"none" | "last_7" | "last_30" | "last_90" | "custom">("none");
  const [timeField, setTimeField] = useState<string>("");
  const [customStartDate, setCustomStartDate] = useState<string>("");
  const [customEndDate, setCustomEndDate] = useState<string>("");

  const { data: profile, isLoading } = useTableProfile(selectedDatasetId, selectedAggregation);

  const transformedColumns = useMemo(() => {
    return profile?.columns.map(transformColumnProfile) ?? [];
  }, [profile]);

  const { groupedColumns, columnRoleMap } = useMemo(() => {
    if (transformedColumns.length === 0) {
      return {
        groupedColumns: { dimensions: [], measures: [], temporal: [] },
        columnRoleMap: new Map<string, ColumnRole>(),
      };
    }

    const roleMap = new Map<string, ColumnRole>();
    transformedColumns.forEach((column) => roleMap.set(column.name, column.role));

    return {
      groupedColumns: {
        dimensions: transformedColumns.filter((column) => column.role === "dimension"),
        measures: transformedColumns.filter((column) => column.role === "measure"),
        temporal: transformedColumns.filter((column) => column.role === "temporal"),
      },
      columnRoleMap: roleMap,
    };
  }, [transformedColumns]);

  useEffect(() => {
    if (groupedColumns.temporal.length === 0) {
      if (timeField) {
        setTimeField("");
      }
      return;
    }

    const stillExists = groupedColumns.temporal.some((column) => column.name === timeField);
    if (!stillExists) {
      setTimeField(groupedColumns.temporal[0].name);
    }
  }, [groupedColumns.temporal, timeField]);

  const validAggregations = useMemo(() => {
    if (!chartConfig.yAxis) {
      return aggregationFns;
    }

    const role = columnRoleMap.get(chartConfig.yAxis);
    if (role === "measure") {
      return aggregationFns;
    }
    if (role === "temporal") {
      return aggregationFns.filter((aggregation) => ["count", "min", "max"].includes(aggregation.id));
    }
    return aggregationFns.filter((aggregation) => aggregation.id === "count");
  }, [chartConfig.yAxis, columnRoleMap]);

  useEffect(() => {
    if (chartConfig.yAxis && validAggregations.length > 0) {
      const currentAggValid = validAggregations.some((aggregation) => aggregation.id === chartConfig.aggregationFn);
      if (!currentAggValid) {
        setChartConfig({ aggregationFn: validAggregations[0].id });
      }
    }
  }, [chartConfig.yAxis, chartConfig.aggregationFn, validAggregations, setChartConfig]);

  const chartSpec = useMemo<ChartSpecV1 | null>(() => {
    if (!selectedAggregation || !chartConfig.xAxis || !chartConfig.yAxis) {
      return null;
    }

    const xRole = columnRoleMap.get(chartConfig.xAxis);
    const yRole = columnRoleMap.get(chartConfig.yAxis);
    if (!(xRole === "dimension" || xRole === "temporal")) {
      return null;
    }
    if (yRole !== "measure") {
      return null;
    }

    const chartFilters: FilterSpec[] = filters
      .map((item) => mapFilter(item))
      .filter((item): item is FilterSpec => item !== null);

    if (timeWindow !== "none" && timeField) {
      if (timeWindow === "custom") {
        if (customStartDate && customEndDate) {
          chartFilters.push({
            field: timeField,
            op: "between",
            value: [customStartDate, customEndDate],
          });
        }
      } else {
        const days = timeWindow === "last_7" ? 7 : timeWindow === "last_30" ? 30 : 90;
        chartFilters.push({
          field: timeField,
          op: ">=",
          value: daysAgoISO(days),
        });
      }
    }

    return {
      version: "v1",
      dataset_id: selectedDatasetId,
      table: selectedAggregation,
      chart: { type: chartConfig.chartType === "kpi" ? "bar" : chartConfig.chartType },
      encoding: {
        x: { field: chartConfig.xAxis },
        y: [
          {
            field: chartConfig.yAxis,
            aggregation: chartConfig.aggregationFn,
            alias: "metric_value",
          },
        ],
      },
      filters: chartFilters,
      sort: [
        {
          field: sortTarget === "x" ? chartConfig.xAxis : "metric_value",
          direction: sortDirection,
        },
      ],
      limit: resultLimit,
    };
  }, [
    selectedAggregation,
    selectedDatasetId,
    chartConfig,
    columnRoleMap,
    filters,
    timeWindow,
    timeField,
    customStartDate,
    customEndDate,
    sortTarget,
    sortDirection,
    resultLimit,
  ]);

  const {
    data: previewData,
    isLoading: isPreviewLoading,
    error: previewError,
  } = useChartsPreview(selectedDatasetId, chartSpec);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveDragId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveDragId(null);

    const { active, over } = event;
    if (!over) return;

    const columnName = active.id as string;
    const dropZone = over.id as string;
    const role = columnRoleMap.get(columnName);

    if (!role) {
      return;
    }

    if (dropZone === "x-axis") {
      if (!(role === "dimension" || role === "temporal")) {
        setValidationMessage("X-axis only accepts dimension or temporal fields.");
        return;
      }
      setChartConfig({ xAxis: columnName });
      setValidationMessage(null);
      return;
    }

    if (dropZone === "y-axis") {
      if (role !== "measure") {
        setValidationMessage("Y-axis only accepts measure fields.");
        return;
      }
      setChartConfig({ yAxis: columnName });
      setValidationMessage(null);
      return;
    }

    if (dropZone === "color-by") {
      if (role !== "dimension") {
        setValidationMessage("Color/Group only accepts dimension fields.");
        return;
      }
      setChartConfig({ colorBy: columnName });
      setValidationMessage(null);
    }
  };

  const activeColumn = activeDragId
    ? transformedColumns.find((column) => column.name === activeDragId)
    : null;

  const addFilter = () => {
    setFilters((prev) => [
      ...prev,
      { id: `${Date.now()}-${prev.length}`, field: "", op: "=", value: "" },
    ]);
  };

  const updateFilter = (id: string, patch: Partial<UIChartFilter>) => {
    setFilters((prev) => prev.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  };

  const removeFilter = (id: string) => {
    setFilters((prev) => prev.filter((item) => item.id !== id));
  };

  const handleReset = () => {
    resetChartConfig();
    setFilters([]);
    setSortTarget("metric");
    setSortDirection("desc");
    setResultLimit(20);
    setTimeWindow("none");
    setCustomStartDate("");
    setCustomEndDate("");
    setValidationMessage(null);
  };

  return (
    <DndContext onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <div className="flex h-full">
        <div className="w-64 border-r border-white/10 bg-[#060010]/50 overflow-y-auto p-4">
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
              Aggregation
            </h3>
            <select
              value={selectedAggregation || ""}
              onChange={(event) => {
                setSelectedAggregation(event.target.value || null);
                handleReset();
              }}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-[#5237ff]/50"
            >
              <option value="">Select table</option>
              {availableMarts.map((table) => (
                <option key={table.id} value={table.id}>
                  {table.label ?? table.id}
                </option>
              ))}
            </select>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 text-[#5237ff] animate-spin" />
            </div>
          ) : transformedColumns.length > 0 ? (
            <>
              <div className="mb-6">
                <h3 className="text-sm font-medium text-blue-400 mb-3 flex items-center gap-2">
                  <Hash className="w-4 h-4" />
                  Dimensions
                </h3>
                <div className="space-y-2">
                  {groupedColumns.dimensions.map((column) => (
                    <DraggableField key={column.name} column={{ name: column.name, role: column.role }} />
                  ))}
                </div>
              </div>

              <div className="mb-6">
                <h3 className="text-sm font-medium text-emerald-400 mb-3 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4" />
                  Measures
                </h3>
                <div className="space-y-2">
                  {groupedColumns.measures.map((column) => (
                    <DraggableField key={column.name} column={{ name: column.name, role: column.role }} />
                  ))}
                </div>
              </div>

              <div className="mb-6">
                <h3 className="text-sm font-medium text-amber-400 mb-3 flex items-center gap-2">
                  <Calendar className="w-4 h-4" />
                  Temporal
                </h3>
                <div className="space-y-2">
                  {groupedColumns.temporal.map((column) => (
                    <DraggableField key={column.name} column={{ name: column.name, role: column.role }} />
                  ))}
                </div>
              </div>
            </>
          ) : selectedAggregation ? (
            <p className="text-gray-500 text-sm text-center">No columns found</p>
          ) : null}
        </div>

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
              ) : validationMessage ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="h-full flex items-center justify-center"
                >
                  <div className="text-center">
                    <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-300 mb-2">Invalid axis mapping</h3>
                    <p className="text-gray-500 text-sm max-w-sm">{validationMessage}</p>
                  </div>
                </motion.div>
              ) : isPreviewLoading ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="h-full flex items-center justify-center"
                >
                  <div className="text-center">
                    <Loader2 className="w-12 h-12 text-[#5237ff] mx-auto mb-4 animate-spin" />
                    <h3 className="text-lg font-medium text-gray-400">Loading chart data...</h3>
                    <p className="text-gray-500 text-sm mt-1">Executing chart preview</p>
                  </div>
                </motion.div>
              ) : previewError ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="h-full flex items-center justify-center"
                >
                  <div className="text-center">
                    <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-400 mb-2">Failed to load chart data</h3>
                    <p className="text-gray-500 text-sm max-w-sm">{previewError.message}</p>
                  </div>
                </motion.div>
              ) : previewData && chartSpec ? (
                <motion.div
                  key={`${chartConfig.xAxis}-${chartConfig.yAxis}-${chartConfig.chartType}`}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="bg-white/5 border border-white/10 rounded-2xl p-6 h-full"
                >
                  {renderChart(chartSpec, previewData.rows)}
                </motion.div>
              ) : (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="h-full flex items-center justify-center"
                >
                  <div className="text-center">
                    <AlertTriangle className="w-12 h-12 text-gray-500 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-400">No chart data</h3>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        <div className="w-80 border-l border-white/10 bg-[#060010]/50 overflow-y-auto p-4 space-y-6">
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

          <div>
            <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
              Aggregation
            </h3>
            <div className="flex flex-wrap gap-2">
              {aggregationFns.map((aggregation) => {
                const isValid = validAggregations.some((item) => item.id === aggregation.id);
                return (
                  <button
                    key={aggregation.id}
                    onClick={() => isValid && setChartConfig({ aggregationFn: aggregation.id })}
                    disabled={!isValid}
                    title={!isValid ? `${aggregation.label} is not available for this column type` : undefined}
                    className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                      !isValid
                        ? "bg-white/5 border border-white/5 text-gray-600 cursor-not-allowed opacity-50"
                        : chartConfig.aggregationFn === aggregation.id
                        ? "bg-emerald-500/20 border border-emerald-500/30 text-emerald-300"
                        : "bg-white/5 border border-white/10 text-gray-400 hover:text-white"
                    }`}
                  >
                    {aggregation.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
              Filters
            </h3>
            <div className="space-y-3">
              {filters.map((filter) => (
                <div key={filter.id} className="space-y-2 bg-white/5 border border-white/10 rounded-lg p-2">
                  <select
                    value={filter.field}
                    onChange={(event) => updateFilter(filter.id, { field: event.target.value })}
                    className="w-full bg-white/5 border border-white/10 rounded px-2 py-1.5 text-white text-xs"
                  >
                    <option value="">Field</option>
                    {transformedColumns.map((column) => (
                      <option key={column.name} value={column.name}>
                        {column.name}
                      </option>
                    ))}
                  </select>
                  <div className="grid grid-cols-[1fr_2fr_auto] gap-2">
                    <select
                      value={filter.op}
                      onChange={(event) => updateFilter(filter.id, { op: event.target.value as FilterOperator })}
                      className="bg-white/5 border border-white/10 rounded px-2 py-1.5 text-white text-xs"
                    >
                      {filterOperators.map((op) => (
                        <option key={op.id} value={op.id}>{op.label}</option>
                      ))}
                    </select>
                    <input
                      value={filter.value}
                      onChange={(event) => updateFilter(filter.id, { value: event.target.value })}
                      placeholder={filter.op === "in" ? "a,b,c" : filter.op === "between" ? "min,max" : "value"}
                      className="bg-white/5 border border-white/10 rounded px-2 py-1.5 text-white text-xs"
                    />
                    <button
                      onClick={() => removeFilter(filter.id)}
                      className="px-2 py-1.5 rounded bg-red-500/20 border border-red-500/30 text-red-300"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              ))}
              <button
                onClick={addFilter}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-gray-300 hover:text-white"
              >
                <Plus className="w-4 h-4" />
                Add Filter
              </button>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
              Time Window
            </h3>
            {groupedColumns.temporal.length > 0 ? (
              <div className="space-y-2">
                <select
                  value={timeField}
                  onChange={(event) => setTimeField(event.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded px-2 py-2 text-white text-sm"
                >
                  {groupedColumns.temporal.map((column) => (
                    <option key={column.name} value={column.name}>{column.name}</option>
                  ))}
                </select>
                <select
                  value={timeWindow}
                  onChange={(event) => setTimeWindow(event.target.value as "none" | "last_7" | "last_30" | "last_90" | "custom")}
                  className="w-full bg-white/5 border border-white/10 rounded px-2 py-2 text-white text-sm"
                >
                  <option value="none">None</option>
                  <option value="last_7">Last 7 days</option>
                  <option value="last_30">Last 30 days</option>
                  <option value="last_90">Last 90 days</option>
                  <option value="custom">Custom range</option>
                </select>
                {timeWindow === "custom" ? (
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="date"
                      value={customStartDate}
                      onChange={(event) => setCustomStartDate(event.target.value)}
                      className="bg-white/5 border border-white/10 rounded px-2 py-2 text-white text-sm"
                    />
                    <input
                      type="date"
                      value={customEndDate}
                      onChange={(event) => setCustomEndDate(event.target.value)}
                      className="bg-white/5 border border-white/10 rounded px-2 py-2 text-white text-sm"
                    />
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="text-xs text-gray-500">No temporal field available for time windows.</p>
            )}
          </div>

          <div>
            <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
              Sort & Limit
            </h3>
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <select
                  value={sortTarget}
                  onChange={(event) => setSortTarget(event.target.value as "x" | "metric")}
                  className="bg-white/5 border border-white/10 rounded px-2 py-2 text-white text-sm"
                >
                  <option value="metric">Sort by metric</option>
                  <option value="x">Sort by X-axis</option>
                </select>
                <select
                  value={sortDirection}
                  onChange={(event) => setSortDirection(event.target.value as "asc" | "desc")}
                  className="bg-white/5 border border-white/10 rounded px-2 py-2 text-white text-sm"
                >
                  <option value="desc">Descending</option>
                  <option value="asc">Ascending</option>
                </select>
              </div>
              <input
                type="number"
                min={1}
                max={5000}
                value={resultLimit}
                onChange={(event) => {
                  const value = Number(event.target.value);
                  if (!Number.isNaN(value)) {
                    setResultLimit(Math.max(1, Math.min(5000, value)));
                  }
                }}
                className="w-full bg-white/5 border border-white/10 rounded px-2 py-2 text-white text-sm"
              />
            </div>
          </div>

          <button
            onClick={handleReset}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-gray-400 hover:text-white hover:bg-white/10 transition-all"
          >
            <RefreshCw className="w-4 h-4" />
            Reset Chart
          </button>
        </div>
      </div>

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
