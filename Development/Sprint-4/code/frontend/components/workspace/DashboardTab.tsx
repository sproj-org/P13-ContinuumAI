"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useAppStore } from "@/lib/store";
import type { SavedChart } from "@/lib/store";
import { renderChart } from "@/components/workspace/renderChart";
import { LayoutGrid, Trash2, Calendar, Database, Edit2, Wrench, Eye, X, ChevronRight } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import {
  useSavedCharts,
  useCreateSavedChart,
  useDeleteSavedChart,
  useUpdateSavedChart,
  useClearSavedCharts,
} from "@/lib/hooks";

export default function DashboardTab() {
  const {
    savedCharts,
    updateChartTitle,
    removeSavedChart,
    clearSavedCharts,
    setActiveTab,
    setSelectedAggregation,
    setChartConfig,
    hydrateSavedCharts,
    selectedDatasetId,
  } = useAppStore();
  const [editingChartId, setEditingChartId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [previewChart, setPreviewChart] = useState<typeof savedCharts[0] | null>(null);
  const [selectedDay, setSelectedDay] = useState<string | null>(null); // null = "All"

  // ── Backend sync hooks ──────────────────────────────────
  const { data: backendCharts } = useSavedCharts(selectedDatasetId);
  const createMutation = useCreateSavedChart();
  const deleteMutation = useDeleteSavedChart();
  const updateMutation = useUpdateSavedChart();
  const clearMutation = useClearSavedCharts();

  // Track which local chart IDs have already been synced to prevent re-POSTing
  const syncedIdsRef = useRef<Set<string>>(new Set());

  // Hydrate store from backend on first load
  useEffect(() => {
    if (!backendCharts) return;
    const hydrated: SavedChart[] = backendCharts.map((bc) => {
      const localId = `db-${bc.id}`;
      syncedIdsRef.current.add(localId);
      return {
        id: localId,
        backendId: bc.id,
        title: bc.title,
        chartSpec: bc.chart_spec as SavedChart["chartSpec"],
        rows: bc.rows,
        datasetId: bc.dataset_id,
        martId: bc.mart_id,
        createdAt: bc.created_at,
      };
    });
    hydrateSavedCharts(hydrated);
  }, [backendCharts, hydrateSavedCharts]);

  // ── Wrapped handlers that also sync to backend ──────────

  // Sync newly-added local charts to backend (from ChartBuilder / Numi saves)
  useEffect(() => {
    for (const chart of savedCharts) {
      if (syncedIdsRef.current.has(chart.id)) continue; // already synced
      syncedIdsRef.current.add(chart.id);
      if (chart.backendId) continue; // came from backend

      createMutation.mutate({
        dataset_id: chart.datasetId,
        mart_id: chart.martId,
        title: chart.title,
        chart_spec: chart.chartSpec as Record<string, unknown>,
        rows: chart.rows as Record<string, unknown>[],
      });
    }
  }, [savedCharts, createMutation]);

  const handleRemoveChart = useCallback(
    (chartId: string) => {
      const chart = savedCharts.find((c) => c.id === chartId);
      removeSavedChart(chartId);
      if (chart?.backendId) {
        deleteMutation.mutate(chart.backendId);
      }
    },
    [savedCharts, removeSavedChart, deleteMutation],
  );

  const handleUpdateTitle = useCallback(
    (chartId: string, newTitle: string) => {
      updateChartTitle(chartId, newTitle);
      const chart = savedCharts.find((c) => c.id === chartId);
      if (chart?.backendId) {
        updateMutation.mutate({ chartId: chart.backendId, data: { title: newTitle } });
      }
    },
    [savedCharts, updateChartTitle, updateMutation],
  );

  const handleClearAll = useCallback(() => {
    clearSavedCharts();
    clearMutation.mutate(selectedDatasetId);
  }, [clearSavedCharts, clearMutation, selectedDatasetId]);

  // ── Day-based grouping ──────────────────────────────────
  const dayKey = (dateStr: string) => {
    const d = new Date(dateStr);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  };

  const dayGroups = useMemo(() => {
    const groups: Record<string, { label: string; dayName: string; charts: typeof savedCharts }> = {};
    for (const chart of savedCharts) {
      const key = dayKey(chart.createdAt);
      if (!groups[key]) {
        const d = new Date(chart.createdAt);
        groups[key] = {
          label: d.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric", year: "numeric" }),
          dayName: d.toLocaleDateString("en-US", { weekday: "long" }),
          charts: [],
        };
      }
      groups[key].charts.push(chart);
    }
    // Sort keys descending (most recent first)
    const sorted = Object.entries(groups).sort(([a], [b]) => b.localeCompare(a));
    return sorted;
  }, [savedCharts]);

  // Auto-select the most recent day when charts load and no day is selected
  useEffect(() => {
    if (selectedDay === null && dayGroups.length > 0) {
      setSelectedDay(dayGroups[0][0]);
    }
  }, [dayGroups, selectedDay]);

  const filteredCharts = useMemo(() => {
    if (selectedDay === "__all__") return savedCharts;
    if (!selectedDay) return savedCharts;
    return savedCharts.filter((c) => dayKey(c.createdAt) === selectedDay);
  }, [savedCharts, selectedDay]);

  const selectedDayLabel = useMemo(() => {
    if (selectedDay === "__all__") return "All Charts";
    const group = dayGroups.find(([k]) => k === selectedDay);
    return group ? group[1].label : "All Charts";
  }, [selectedDay, dayGroups]);

  const handleOpenInChartBuilder = (chart: typeof savedCharts[0]) => {
    // Set the mart/aggregation
    setSelectedAggregation(chart.martId);
    
    // Map ChartSpecV1 to ChartConfig
    const chartConfig = {
      chartType: chart.chartSpec.chart.type,
      xAxis: chart.chartSpec.encoding.x.field,
      yAxis: chart.chartSpec.encoding.y[0]?.field || null,
      colorBy: null,
      aggregationFn: chart.chartSpec.encoding.y[0]?.aggregation || 'sum',
    };
    
    setChartConfig(chartConfig);
    
    // Switch to chart builder tab
    setActiveTab('chart-builder');
  };

  const handleStartEdit = (chartId: string, currentTitle: string) => {
    setEditingChartId(chartId);
    setEditingTitle(currentTitle);
  };

  const handleSaveEdit = (chartId: string) => {
    if (editingTitle.trim()) {
      handleUpdateTitle(chartId, editingTitle.trim());
    }
    setEditingChartId(null);
    setEditingTitle("");
  };

  const handleCancelEdit = () => {
    setEditingChartId(null);
    setEditingTitle("");
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="h-full flex bg-gradient-to-br from-slate-50 via-indigo-50/20 to-violet-50/20">
      {/* ── Sidebar: Day-based navigation ── */}
      {savedCharts.length > 0 && (
        <aside className="w-64 shrink-0 border-r border-indigo-200/50 bg-white/70 backdrop-blur-sm flex flex-col overflow-hidden">
          <div className="px-4 py-4 border-b border-slate-200/70">
            <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Dashboards</h2>
          </div>
          <nav className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
            {/* All Charts */}
            <button
              onClick={() => setSelectedDay("__all__")}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm transition-all ${
                selectedDay === "__all__"
                  ? "bg-gradient-to-r from-[#4f46e5] to-indigo-600 text-white shadow-md shadow-indigo-200"
                  : "text-slate-700 hover:bg-indigo-50 hover:text-[#4f46e5]"
              }`}
            >
              <LayoutGrid className="w-4 h-4 shrink-0" />
              <span className="flex-1 text-left font-medium truncate">All Charts</span>
              <span className={`text-xs font-semibold px-1.5 py-0.5 rounded-full ${
                selectedDay === "__all__" ? "bg-white/20 text-white" : "bg-slate-100 text-slate-500"
              }`}>
                {savedCharts.length}
              </span>
            </button>

            {/* Divider */}
            <div className="my-2 border-t border-slate-200/70" />

            {/* Day entries */}
            {dayGroups.map(([key, group]) => (
              <button
                key={key}
                onClick={() => setSelectedDay(key)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm transition-all ${
                  selectedDay === key
                    ? "bg-gradient-to-r from-[#4f46e5] to-indigo-600 text-white shadow-md shadow-indigo-200"
                    : "text-slate-700 hover:bg-indigo-50 hover:text-[#4f46e5]"
                }`}
              >
                <Calendar className="w-4 h-4 shrink-0" />
                <div className="flex-1 text-left min-w-0">
                  <div className="font-medium truncate">{group.dayName}</div>
                  <div className={`text-xs truncate ${selectedDay === key ? "text-indigo-200" : "text-slate-400"}`}>
                    {key}
                  </div>
                </div>
                <span className={`text-xs font-semibold px-1.5 py-0.5 rounded-full ${
                  selectedDay === key ? "bg-white/20 text-white" : "bg-slate-100 text-slate-500"
                }`}>
                  {group.charts.length}
                </span>
                {selectedDay === key && <ChevronRight className="w-3.5 h-3.5 shrink-0" />}
              </button>
            ))}
          </nav>
        </aside>
      )}

      {/* ── Main content area ── */}
      <div className="flex-1 overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-white/80 backdrop-blur-sm border-b border-indigo-200/50 px-6 py-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#4f46e5] to-indigo-600 flex items-center justify-center shadow-lg">
                <LayoutGrid className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">{selectedDayLabel}</h1>
                <p className="text-sm text-slate-600">
                  {filteredCharts.length} saved {filteredCharts.length === 1 ? "chart" : "charts"}
                </p>
              </div>
            </div>
            {savedCharts.length > 0 && (
              <button
                onClick={handleClearAll}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 rounded-lg border border-red-200 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                Clear All
              </button>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {savedCharts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-[calc(100vh-200px)]">
            <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-indigo-100 to-violet-100 flex items-center justify-center mb-6">
              <LayoutGrid className="w-12 h-12 text-[#4f46e5]" />
            </div>
            <h2 className="text-2xl font-bold text-slate-900 mb-2">No Charts Saved Yet</h2>
            <p className="text-slate-600 text-center max-w-md mb-6">
              Start chatting with Numi or experiment with the Chart Builder to create charts, then save them here for easy access and analysis.
            </p>
            <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 max-w-md">
              <p className="text-sm text-indigo-900 font-medium mb-2">💡 Quick Tip</p>
              <p className="text-sm text-indigo-700">
                Click the "Ask Numi" button and request a chart like "Show revenue by month" or
                "Sales by store". Once Numi generates it, you can save it to this dashboard!
              </p>
            </div>
          </div>
        ) : filteredCharts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-[calc(100vh-200px)]">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-100 to-violet-100 flex items-center justify-center mb-4">
              <Calendar className="w-10 h-10 text-[#4f46e5]" />
            </div>
            <h2 className="text-lg font-bold text-slate-900 mb-1">No charts on this day</h2>
            <p className="text-slate-500 text-sm">Select another day from the sidebar or create new charts.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {filteredCharts.map((chart) => (
              <div
                key={chart.id}
                className="group bg-white rounded-2xl border border-slate-200/80 shadow-md hover:shadow-xl hover:border-indigo-200 transition-all duration-300 overflow-hidden"
              >
                {/* Chart Header */}
                <div className="p-4 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-indigo-50/30">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      {editingChartId === chart.id ? (
                        <input
                          type="text"
                          value={editingTitle}
                          onChange={(e) => setEditingTitle(e.target.value)}
                          onBlur={() => handleSaveEdit(chart.id)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              handleSaveEdit(chart.id);
                            } else if (e.key === "Escape") {
                              handleCancelEdit();
                            }
                          }}
                          autoFocus
                          className="w-full font-semibold text-slate-900 mb-1 px-2 py-1 border border-indigo-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4f46e5]"
                        />
                      ) : (
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-semibold text-slate-900 truncate flex-1">
                            {chart.title}
                          </h3>
                          <button
                            onClick={() => handleStartEdit(chart.id, chart.title)}
                            className="p-1 text-slate-400 hover:text-[#4f46e5] hover:bg-indigo-50 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                            title="Edit title"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}
                      <div className="flex items-center gap-3 text-xs text-slate-600">
                        <div className="flex items-center gap-1">
                          <Database className="w-3 h-3" />
                          <span className="truncate">{chart.martId}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          <span>{formatDate(chart.createdAt)}</span>
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => handleRemoveChart(chart.id)}
                      className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                      title="Remove chart"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Chart Content */}
                <div className="p-5 bg-gradient-to-br from-slate-50/30 to-white">
                  <div className="h-72 rounded-xl overflow-hidden bg-white border border-slate-100 shadow-sm">
                    {renderChart(chart.chartSpec, chart.rows)}
                  </div>
                </div>

                {/* Chart Footer */}
                <div className="px-4 py-3 bg-gradient-to-r from-slate-50 to-indigo-50/30 border-t border-slate-200">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-slate-600">
                        {chart.rows.length} data {chart.rows.length === 1 ? "point" : "points"}
                      </span>
                      <span className="px-2 py-1 bg-indigo-100 text-indigo-700 rounded-full font-medium">
                        {chart.chartSpec.chart.type}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setPreviewChart(chart)}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-violet-600 hover:text-violet-700 hover:bg-violet-50 rounded-lg border border-violet-200 transition-colors"
                        title="Preview chart"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Preview</span>
                      </button>
                      <button
                        onClick={() => handleOpenInChartBuilder(chart)}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[#4f46e5] hover:text-indigo-700 hover:bg-indigo-50 rounded-lg border border-indigo-200 transition-colors"
                        title="Open in Chart Builder"
                      >
                        <Wrench className="w-3.5 h-3.5" />
                        <span>Edit</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Chart Preview Modal */}
      <AnimatePresence>
        {previewChart && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/60 backdrop-blur-sm"
            onClick={() => setPreviewChart(null)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ type: "spring", duration: 0.3 }}
              className="relative bg-white rounded-3xl shadow-2xl max-w-6xl w-full max-h-[90vh] overflow-hidden"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Modal Header */}
              <div className="flex items-center justify-between p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-indigo-50/30">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 flex items-center justify-center shadow-lg">
                    <Eye className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-slate-900">{previewChart.title}</h3>
                    <div className="flex items-center gap-3 text-xs text-slate-600 mt-1">
                      <div className="flex items-center gap-1">
                        <Database className="w-3 h-3" />
                        <span>{previewChart.martId}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        <span>{formatDate(previewChart.createdAt)}</span>
                      </div>
                      <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full font-medium">
                        {previewChart.chartSpec.chart.type}
                      </span>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setPreviewChart(null)}
                  className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  <X className="w-5 h-5 text-slate-600" />
                </button>
              </div>

              {/* Modal Content */}
              <div className="p-8 overflow-y-auto max-h-[calc(90vh-200px)]">
                <div className="bg-gradient-to-br from-slate-50/30 to-white rounded-2xl p-8 border border-slate-100 shadow-inner">
                  <div className="h-[600px]">
                    {renderChart(previewChart.chartSpec, previewChart.rows)}
                  </div>
                </div>
              </div>

              {/* Modal Footer */}
              <div className="flex items-center justify-between px-6 py-4 border-t border-slate-200 bg-gradient-to-r from-slate-50 to-indigo-50/30">
                <div className="text-sm text-slate-600">
                  {previewChart.rows.length} data {previewChart.rows.length === 1 ? "point" : "points"}
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => {
                      setPreviewChart(null);
                      handleOpenInChartBuilder(previewChart);
                    }}
                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-[#4f46e5] hover:text-indigo-700 hover:bg-indigo-50 rounded-lg border border-indigo-200 transition-colors"
                  >
                    <Wrench className="w-4 h-4" />
                    Edit in Chart Builder
                  </button>
                  <button
                    onClick={() => setPreviewChart(null)}
                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg border border-slate-200 transition-colors"
                  >
                    Close
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      </div>{/* end main content area */}
    </div>
  );
}
