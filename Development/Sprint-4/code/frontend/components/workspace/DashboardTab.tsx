"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useAppStore } from "@/lib/store";
import type { SavedChart } from "@/lib/store";
import DrillDownChart from "@/components/workspace/DrillDownChart";
import { LayoutGrid, Trash2, Calendar, Database, Edit2, Wrench, Eye, X, ChevronRight } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import {
  useSavedCharts,
  useCreateSavedChart,
  useDeleteSavedChart,
  useUpdateSavedChart,
  useDashboards,
  useCreateDashboard,
  useRenameDashboard,
  useDeleteDashboard,
} from "@/lib/hooks";

export default function DashboardTab() {
  const {
    savedCharts,
    updateChartTitle,
    removeSavedChart,
    setActiveTab,
    setSelectedAggregation,
    setChartConfig,
    hydrateSavedCharts,
    selectedDatasetId,
  } = useAppStore();
  const [editingChartId, setEditingChartId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [previewChart, setPreviewChart] = useState<typeof savedCharts[0] | null>(null);
  const [selectedDashboardName, setSelectedDashboardName] = useState<string | null>(null);
  const [newDashboardName, setNewDashboardName] = useState("");
  const [isCreateDashboardOpen, setIsCreateDashboardOpen] = useState(false);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    dashboardId: number;
    dashboardName: string;
  } | null>(null);

  // ── Backend sync hooks ──────────────────────────────────
  const { data: backendCharts } = useSavedCharts(selectedDatasetId);
  const { data: dashboardsData } = useDashboards(selectedDatasetId);
  const createMutation = useCreateSavedChart();
  const deleteMutation = useDeleteSavedChart();
  const updateMutation = useUpdateSavedChart();
  const createDashboardMutation = useCreateDashboard();
  const renameDashboardMutation = useRenameDashboard();
  const deleteDashboardMutation = useDeleteDashboard();

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
        dashboardName: bc.dashboard_name,
        chartSpec: bc.chart_spec as unknown as SavedChart["chartSpec"],
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
        dashboard_name: chart.dashboardName,
        mart_id: chart.martId,
        title: chart.title,
        chart_spec: chart.chartSpec as unknown as Record<string, unknown>,
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

  const dashboardIdByName = useMemo(() => {
    const map = new Map<string, number>();
    for (const dashboard of dashboardsData ?? []) {
      map.set(dashboard.name, dashboard.id);
    }
    return map;
  }, [dashboardsData]);

  const handleCreateDashboard = useCallback(() => {
    const name = newDashboardName.trim();
    if (!name) {
      return;
    }
    createDashboardMutation.mutate(
      { dataset_id: selectedDatasetId, name },
      {
        onSuccess: () => {
          setSelectedDashboardName(name);
          setIsCreateDashboardOpen(false);
          setNewDashboardName("");
        },
      }
    );
  }, [createDashboardMutation, newDashboardName, selectedDatasetId]);

  const dashboardGroups = useMemo(() => {
    const groups: Record<string, { charts: typeof savedCharts }> = {};

    for (const dashboard of dashboardsData ?? []) {
      groups[dashboard.name] = { charts: [] };
    }

    for (const chart of savedCharts) {
      const key = chart.dashboardName || "Default";
      if (!groups[key]) {
        groups[key] = { charts: [] };
      }
      groups[key].charts.push(chart);
    }

    if (!groups.Default) {
      groups.Default = { charts: [] };
    }

    const sorted = Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
    return sorted;
  }, [dashboardsData, savedCharts]);

  const effectiveSelectedDashboardName = useMemo(() => {
    if (selectedDashboardName === "__all__") {
      return "__all__";
    }
    if (selectedDashboardName && dashboardGroups.some(([name]) => name === selectedDashboardName)) {
      return selectedDashboardName;
    }
    return dashboardGroups[0]?.[0] ?? "__all__";
  }, [dashboardGroups, selectedDashboardName]);

  const handleRenameDashboard = useCallback(
    (dashboardId: number, currentName: string) => {
      const nextName = globalThis.prompt("Rename dashboard", currentName)?.trim();
      if (!nextName || nextName === currentName) {
        return;
      }
      renameDashboardMutation.mutate(
        { dashboardId, data: { name: nextName } },
        {
          onSuccess: () => {
            if (effectiveSelectedDashboardName === currentName) {
              setSelectedDashboardName(nextName);
            }
          },
        }
      );
    },
    [effectiveSelectedDashboardName, renameDashboardMutation]
  );

  const handleDeleteDashboard = useCallback(
    (dashboardId: number, dashboardName: string) => {
      const confirmed = globalThis.confirm(
        `Delete dashboard "${dashboardName}"? This will also remove charts saved in it.`
      );
      if (!confirmed) {
        return;
      }
      deleteDashboardMutation.mutate(dashboardId, {
        onSuccess: () => {
          if (effectiveSelectedDashboardName === dashboardName) {
            setSelectedDashboardName("__all__");
          }
        },
      });
    },
    [deleteDashboardMutation, effectiveSelectedDashboardName]
  );

  const filteredCharts = useMemo(() => {
    if (effectiveSelectedDashboardName === "__all__") return savedCharts;
    return savedCharts.filter((c) => (c.dashboardName || "Default") === effectiveSelectedDashboardName);
  }, [effectiveSelectedDashboardName, savedCharts]);

  const selectedDashboardLabel = useMemo(() => {
    if (effectiveSelectedDashboardName === "__all__") return "All Dashboards";
    return effectiveSelectedDashboardName || "All Dashboards";
  }, [effectiveSelectedDashboardName]);

  const activeMartCount = useMemo(
    () => new Set(filteredCharts.map((chart) => chart.martId)).size,
    [filteredCharts],
  );

  const chartTypeMix = useMemo(() => {
    const counts = new Map<string, number>();
    for (const chart of filteredCharts) {
      const type = chart.chartSpec.chart.type;
      counts.set(type, (counts.get(type) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((left, right) => right[1] - left[1])
      .slice(0, 3);
  }, [filteredCharts]);

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

  const latestSavedLabel = useMemo(() => {
    if (filteredCharts.length === 0) {
      return "No saved charts";
    }
    const latest = [...filteredCharts].sort(
      (left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime(),
    )[0];
    return formatDate(latest.createdAt);
  }, [filteredCharts]);

  return (
    <div className="h-full flex bg-gradient-to-br from-slate-50 via-indigo-50/20 to-violet-50/20">
      {/* ── Sidebar: Named dashboard navigation ── */}
      {dashboardGroups.length > 0 && (
        <aside className="w-64 shrink-0 border-r border-indigo-200/50 bg-white/70 backdrop-blur-sm flex flex-col overflow-hidden">
          <div className="px-4 py-4 border-b border-slate-200/70 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Dashboards</h2>
              <button
                onClick={() => setIsCreateDashboardOpen(true)}
                className="text-xs px-2 py-1 rounded-md border border-indigo-200 text-indigo-700 hover:bg-indigo-50"
              >
                + New
              </button>
            </div>
          </div>
          <nav className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
            {/* All Dashboards */}
              <button
                onClick={() => setSelectedDashboardName("__all__")}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm transition-all ${
                effectiveSelectedDashboardName === "__all__"
                  ? "bg-gradient-to-r from-[#4f46e5] to-indigo-600 text-white shadow-md shadow-indigo-200"
                  : "text-slate-700 hover:bg-indigo-50 hover:text-[#4f46e5]"
              }`}
            >
              <LayoutGrid className="w-4 h-4 shrink-0" />
              <span className="flex-1 text-left font-medium truncate">All Dashboards</span>
              <span className={`text-xs font-semibold px-1.5 py-0.5 rounded-full ${
                effectiveSelectedDashboardName === "__all__" ? "bg-white/20 text-white" : "bg-slate-100 text-slate-500"
              }`}>
                {savedCharts.length}
              </span>
            </button>

            {/* Divider */}
            <div className="my-2 border-t border-slate-200/70" />

            {/* Dashboard entries */}
            {dashboardGroups.map(([name, group]) => (
              <button
                key={name}
                onClick={() => setSelectedDashboardName(name)}
                onContextMenu={(event) => {
                  const dashboardId = dashboardIdByName.get(name);
                  if (!dashboardId) {
                    return;
                  }
                  event.preventDefault();
                  setContextMenu({
                    x: event.clientX,
                    y: event.clientY,
                    dashboardId,
                    dashboardName: name,
                  });
                }}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm transition-all ${
                  effectiveSelectedDashboardName === name
                    ? "bg-gradient-to-r from-[#4f46e5] to-indigo-600 text-white shadow-md shadow-indigo-200"
                    : "text-slate-700 hover:bg-indigo-50 hover:text-[#4f46e5]"
                }`}
              >
                <LayoutGrid className="w-4 h-4 shrink-0" />
                <div className="flex-1 text-left min-w-0">
                  <div className="font-medium truncate">{name}</div>
                </div>
                <span className={`text-xs font-semibold px-1.5 py-0.5 rounded-full ${
                  effectiveSelectedDashboardName === name ? "bg-white/20 text-white" : "bg-slate-100 text-slate-500"
                }`}>
                  {group.charts.length}
                </span>
                {effectiveSelectedDashboardName === name && <ChevronRight className="w-3.5 h-3.5 shrink-0" />}
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
                <h1 className="text-xl font-bold text-slate-900">{selectedDashboardLabel}</h1>
                <p className="text-sm text-slate-600">
                  Dataset {selectedDatasetId} with {filteredCharts.length} saved {filteredCharts.length === 1 ? "chart" : "charts"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveTab("chart-builder")}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 rounded-lg border border-slate-200 transition-colors"
              >
                <Wrench className="w-4 h-4" />
                Compose
              </button>
              <button
                onClick={() => setIsCreateDashboardOpen(true)}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-50 rounded-lg border border-indigo-200 transition-colors"
              >
                <LayoutGrid className="w-4 h-4" />
                New Dashboard
              </button>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {savedCharts.length > 0 ? (
            <div className="mb-6 grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs uppercase tracking-wide text-slate-500">Active board</p>
                <p className="mt-1 text-lg font-semibold text-slate-900">{selectedDashboardLabel}</p>
                <p className="text-xs text-slate-600">{filteredCharts.length} chart card(s) visible</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs uppercase tracking-wide text-slate-500">Composition</p>
                <p className="mt-1 text-lg font-semibold text-slate-900">
                  {chartTypeMix.length > 0 ? chartTypeMix.map(([type, count]) => `${type} ${count}`).join(" | ") : "No charts yet"}
                </p>
                <p className="text-xs text-slate-600">{activeMartCount} mart(s) represented</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs uppercase tracking-wide text-slate-500">Latest save</p>
                <p className="mt-1 text-lg font-semibold text-slate-900">{latestSavedLabel}</p>
                <p className="text-xs text-slate-600">Use Edit to send a saved chart back to the builder.</p>
              </div>
            </div>
          ) : null}

          {savedCharts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-[calc(100vh-200px)]">
            <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-indigo-100 to-violet-100 flex items-center justify-center mb-6">
              <LayoutGrid className="w-12 h-12 text-[#4f46e5]" />
            </div>
            <h2 className="text-2xl font-bold text-slate-900 mb-2">No Charts Saved Yet</h2>
            <p className="text-slate-600 text-center max-w-md mb-6">
              Start chatting with VizAgent or experiment with the Chart Builder to create charts, then save them here for easy access and analysis.
            </p>
            <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 max-w-md">
              <p className="text-sm text-indigo-900 font-medium mb-2">💡 Quick Tip</p>
              <p className="text-sm text-indigo-700">
                Click the &quot;Ask VizAgent&quot; button and request a chart like &quot;Show revenue by month&quot; or
                &quot;Sales by store&quot;. Once VizAgent generates it, you can save it to this dashboard.
              </p>
            </div>
            <button
              onClick={() => setActiveTab("chart-builder")}
              className="mt-5 inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              <Wrench className="w-4 h-4" />
              Open Chart Builder
            </button>
          </div>
        ) : filteredCharts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-[calc(100vh-200px)]">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-100 to-violet-100 flex items-center justify-center mb-4">
              <LayoutGrid className="w-10 h-10 text-[#4f46e5]" />
            </div>
            <h2 className="text-lg font-bold text-slate-900 mb-1">No charts in this dashboard</h2>
            <p className="text-slate-500 text-sm">Select another dashboard from the sidebar or create new charts.</p>
            <button
              onClick={() => setActiveTab("chart-builder")}
              className="mt-4 inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              <Wrench className="w-4 h-4" />
              Build a chart
            </button>
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

                {/* Chart Content — DrillDownChart with click-to-drill */}
                <div className="p-5 bg-gradient-to-br from-slate-50/30 to-white">
                  <div className="h-80 rounded-xl overflow-hidden bg-white border border-slate-100 shadow-sm relative">
                    <DrillDownChart
                      chartSpec={chart.chartSpec}
                      rows={chart.rows}
                      datasetId={selectedDatasetId}
                      height="100%"
                      chartTitle={chart.title}
                    />
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

      {contextMenu ? (
        <>
          <button
            className="fixed inset-0 z-40 cursor-default"
            onClick={() => setContextMenu(null)}
            aria-label="Dismiss dashboard menu"
          />
          <div
            className="fixed z-50 w-44 rounded-lg border border-slate-200 bg-white shadow-xl"
            style={{ top: contextMenu.y, left: contextMenu.x }}
          >
            <button
              className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              onClick={() => {
                handleRenameDashboard(contextMenu.dashboardId, contextMenu.dashboardName);
                setContextMenu(null);
              }}
            >
              Rename
            </button>
            <button
              className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50"
              onClick={() => {
                handleDeleteDashboard(contextMenu.dashboardId, contextMenu.dashboardName);
                setContextMenu(null);
              }}
            >
              Delete
            </button>
          </div>
        </>
      ) : null}

      {isCreateDashboardOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-2xl border border-slate-200">
            <h3 className="text-lg font-semibold text-slate-900 mb-3">Create Dashboard</h3>
            <input
              autoFocus
              type="text"
              value={newDashboardName}
              onChange={(event) => setNewDashboardName(event.target.value)}
              placeholder="Dashboard name"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
            />
            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                onClick={() => {
                  setIsCreateDashboardOpen(false);
                  setNewDashboardName("");
                }}
                className="px-3 py-2 text-sm rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateDashboard}
                className="px-3 py-2 text-sm rounded-lg bg-indigo-600 text-white hover:bg-indigo-700"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      ) : null}

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

              {/* Modal Content — DrillDownChart with full drill-down in preview */}
              <div className="p-8 overflow-y-auto max-h-[calc(90vh-200px)]">
                <div className="bg-gradient-to-br from-slate-50/30 to-white rounded-2xl p-8 border border-slate-100 shadow-inner">
                  <div className="h-[600px] relative">
                    <DrillDownChart
                      chartSpec={previewChart.chartSpec}
                      rows={previewChart.rows}
                      datasetId={selectedDatasetId}
                      height="100%"
                      chartTitle={previewChart.title}
                    />
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
