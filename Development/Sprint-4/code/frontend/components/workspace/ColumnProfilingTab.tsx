"use client";

import { useAppStore } from "@/lib/store";
import { useTableProfile } from "@/lib/hooks";
import { 
  transformColumnProfile, 
  generateSuggestedCharts,
  type TransformedColumnProfile,
  type ColumnRole,
} from "@/lib/transformers";
import { motion } from "framer-motion";
import dynamic from "next/dynamic";
import {
  Columns3,
  BarChart3,
  Hash,
  Type,
  Calendar,
  TrendingUp,
  ArrowRight,
  Loader2,
} from "lucide-react";

// Dynamic import for Plotly to avoid SSR issues
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

const roleIcons: Record<ColumnRole, React.ReactNode> = {
  dimension: <Hash className="w-4 h-4" />,
  measure: <BarChart3 className="w-4 h-4" />,
  temporal: <Calendar className="w-4 h-4" />,
};

const roleColors: Record<ColumnRole, { bg: string; text: string; border: string }> = {
  dimension: { bg: "bg-blue-100", text: "text-blue-700", border: "border-blue-300" },
  measure: { bg: "bg-emerald-100", text: "text-emerald-700", border: "border-emerald-300" },
  temporal: { bg: "bg-amber-100", text: "text-amber-700", border: "border-amber-300" },
};

function getNullColor(percentage: number) {
  if (percentage < 5) return "bg-emerald-500";
  if (percentage < 20) return "bg-amber-500";
  return "bg-red-500";
}

function DimensionDetails({ column }: { column: TransformedColumnProfile }) {
  const cardinalityColors = {
    low: "bg-emerald-100 text-emerald-700",
    medium: "bg-amber-100 text-amber-700",
    high: "bg-red-100 text-red-700",
  };

  return (
    <div className="space-y-6">
      {/* Cardinality */}
      {column.cardinality && (
        <div className="flex items-center gap-4">
          <span className="text-slate-600 text-sm">Cardinality:</span>
          <span className={`px-3 py-1 rounded-full text-sm font-medium capitalize ${cardinalityColors[column.cardinality]}`}>
            {column.cardinality}
          </span>
        </div>
      )}

      {/* Top Values */}
      {column.topValues && column.topValues.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-slate-700 mb-3">Top Values</h4>
          <div className="space-y-2">
            {column.topValues.map((item, index) => {
              const maxPercent = column.topValues[0].percent;
              const percentage = maxPercent > 0 ? (item.percent / maxPercent) * 100 : 0;
              return (
                <div key={index} className="relative">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-900">{item.value}</span>
                    <span className="text-slate-600">{item.count.toLocaleString()}</span>
                  </div>
                  <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${percentage}%` }}
                      transition={{ duration: 0.5, delay: index * 0.1 }}
                      className="h-full bg-blue-600 rounded-full"
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Pie Chart for Distribution */}
      {column.topValues && column.topValues.length > 0 && column.topValues.length <= 6 && (
        <div className="bg-white/[0.03] rounded-xl p-4">
          <Plot
            data={[
              {
                type: "pie",
                values: column.topValues.map(v => v.count),
                labels: column.topValues.map(v => v.value),
                textinfo: "percent",
                textposition: "inside",
                marker: {
                  colors: ["#3b82f6", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444"],
                },
                hole: 0.4,
              },
            ]}
            layout={{
              paper_bgcolor: "transparent",
              plot_bgcolor: "transparent",
              font: { color: "#94a3b8", size: 12 },
              showlegend: true,
              legend: { orientation: "h", y: -0.2 },
              margin: { t: 20, b: 40, l: 20, r: 20 },
              height: 250,
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
          />
        </div>
      )}
    </div>
  );
}

function MeasureDetails({ column }: { column: TransformedColumnProfile }) {
  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Min", value: column.min },
          { label: "Max", value: column.max },
          { label: "Mean", value: column.mean },
          { label: "Median", value: column.median },
        ].map((stat) => (
          <div key={stat.label} className="bg-white border border-slate-200 rounded-xl p-4 text-center shadow-sm">
            <div className="text-slate-600 text-xs mb-1">{stat.label}</div>
            <div className="text-slate-900 font-semibold">
              {stat.value !== null && stat.value !== undefined ? stat.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "N/A"}
            </div>
          </div>
        ))}
      </div>

      {/* Suggested Aggregations */}
      <div>
        <h4 className="text-sm font-medium text-gray-400 mb-3">Suggested Aggregations</h4>
        <div className="flex gap-2">
          {["SUM", "AVG", "COUNT", "MIN", "MAX"].map((agg) => (
            <span
              key={agg}
              className="px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-400 text-sm font-medium"
            >
              {agg}({column.name})
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function TemporalDetails({ column }: { column: TransformedColumnProfile }) {
  return (
    <div className="space-y-6">
      {/* Time Range */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="text-slate-600 text-xs mb-1">Start Date</div>
          <div className="text-slate-900 font-medium">{column.minDate || "N/A"}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="text-slate-600 text-xs mb-1">End Date</div>
          <div className="text-slate-900 font-medium">{column.maxDate || "N/A"}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="text-slate-600 text-xs mb-1">Distinct Days</div>
          <div className="text-amber-600 font-medium">{column.distinctDays?.toLocaleString() || "N/A"}</div>
        </div>
      </div>

      {/* Suggested Charts */}
      <div>
        <h4 className="text-sm font-medium text-slate-700 mb-3">Suggested Visualizations</h4>
        <div className="flex gap-2">
          <span className="px-3 py-1.5 bg-amber-100 border border-amber-300 rounded-lg text-amber-700 text-sm font-medium">
            Line Chart (Trend)
          </span>
          <span className="px-3 py-1.5 bg-amber-100 border border-amber-300 rounded-lg text-amber-700 text-sm font-medium">
            Area Chart (Volume)
          </span>
        </div>
      </div>
    </div>
  );
}

export default function ColumnProfilingTab() {
  const {
    selectedDatasetId,
    selectedAggregation,
    setSelectedAggregation,
    availableMarts,
    selectedColumn,
    setSelectedColumn,
    setActiveTab,
    setChartConfig,
  } = useAppStore();
  const { data: profile, isLoading: isProfileLoading, error } = useTableProfile(
    selectedDatasetId,
    selectedAggregation
  );
  const isLoading = !!selectedAggregation && isProfileLoading;
  
  // Transform columns for frontend use
  const transformedColumns = profile?.columns.map(transformColumnProfile) ?? [];
  const columnProfile = transformedColumns.find(c => c.name === selectedColumn);
  
  // Generate suggested charts for the selected column
  const suggestedCharts = selectedColumn && profile 
    ? generateSuggestedCharts(
        profile.columns.find(c => c.name === selectedColumn)!,
        profile.columns
      )
    : [];

  const handleChartSuggestionClick = (chart: { type: string; xAxis?: string; yAxis?: string }) => {
    setChartConfig({
      chartType: chart.type as 'bar' | 'line' | 'pie' | 'histogram',
      xAxis: chart.xAxis || null,
      yAxis: chart.yAxis || null,
    });
    setActiveTab("chart-builder");
  };

  return (
    <div className="flex h-full bg-gradient-to-br from-slate-50 to-indigo-50/30">
      {/* Left Panel - Table & Column Selector */}
      <div className="w-72 border-r border-indigo-200/50 bg-white/80 backdrop-blur-sm overflow-y-auto">
        {/* Table Selector */}
        <div className="p-4 border-b border-indigo-200/50">
          <h3 className="text-sm font-medium text-indigo-900 uppercase tracking-wider mb-3">
            Table
          </h3>
          <select
            value={selectedAggregation || ""}
            onChange={(e) => setSelectedAggregation(e.target.value || null)}
            className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-[#4F46E5]/50 shadow-sm"
          >
            <option value="">Select a table</option>
            {availableMarts.map((table) => (
              <option key={table.id} value={table.id}>
                {table.label ?? table.id}
              </option>
            ))}
          </select>
        </div>

        {/* Column List */}
        <div className="p-4">
          <h3 className="text-sm font-medium text-indigo-900 uppercase tracking-wider mb-3">
            Columns
          </h3>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 text-[#4F46E5] animate-spin" />
            </div>
          ) : error ? (
            <div className="text-red-600 text-sm bg-red-50 p-3 rounded-lg border border-red-200">Failed to load columns</div>
          ) : transformedColumns.length > 0 ? (
            <div className="space-y-1">
              {transformedColumns.map((col) => {
                const roleStyle = roleColors[col.role];
                return (
                  <button
                    key={col.name}
                    onClick={() => setSelectedColumn(col.name)}
                    className={`w-full text-left p-2.5 rounded-lg transition-all flex items-center gap-2 ${
                      selectedColumn === col.name
                        ? "bg-indigo-100 border border-indigo-300 shadow-sm"
                        : "hover:bg-slate-100 border border-transparent"
                    }`}
                  >
                    <div className={`p-1 rounded ${roleStyle.bg} ${roleStyle.text}`}>
                      {roleIcons[col.role]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className={`text-sm font-medium truncate ${selectedColumn === col.name ? "text-indigo-900" : "text-slate-700"}`}>
                        {col.name}
                      </div>
                      <div className="text-xs text-slate-500">{col.dataType}</div>
                    </div>
                    {col.nullPercentage > 0 && (
                      <span className="text-xs text-slate-500">{col.nullPercentage.toFixed(1)}%</span>
                    )}
                  </button>
                );
              })}
            </div>
          ) : selectedAggregation ? (
            <p className="text-slate-500 text-sm">No columns found</p>
          ) : (
            <p className="text-slate-500 text-sm">Select a table first</p>
          )}
        </div>
      </div>

      {/* Main Panel - Column Details */}
      <div className="flex-1 overflow-y-auto p-6">
        {!selectedColumn || !columnProfile ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <Columns3 className="w-16 h-16 text-slate-400 mx-auto mb-4" />
              <h3 className="text-xl font-medium text-slate-600 mb-2">Select a Column</h3>
              <p className="text-slate-500">Choose a column from the left panel to view its profile</p>
            </div>
          </div>
        ) : (
          <motion.div
            key={selectedColumn}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
            className="space-y-6"
          >
            {/* Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={`p-3 rounded-xl ${roleColors[columnProfile.role].bg} ${roleColors[columnProfile.role].text}`}>
                  {roleIcons[columnProfile.role]}
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-slate-900">{columnProfile.name}</h2>
                  <div className="flex items-center gap-3 mt-1">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${roleColors[columnProfile.role].bg} ${roleColors[columnProfile.role].text}`}>
                      {columnProfile.role}
                    </span>
                    <span className="text-slate-600 text-sm flex items-center gap-1">
                      <Type className="w-3 h-3" />
                      {columnProfile.dataType}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                <div className="text-slate-600 text-sm mb-1">Null %</div>
                <div className="flex items-center gap-3">
                  <span className="text-2xl font-bold text-slate-900">{columnProfile.nullPercentage.toFixed(1)}%</span>
                  <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${getNullColor(columnProfile.nullPercentage)}`}
                      style={{ width: `${Math.min(columnProfile.nullPercentage, 100)}%` }}
                    />
                  </div>
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                <div className="text-slate-600 text-sm mb-1">Unique Values</div>
                <div className="text-2xl font-bold text-slate-900">
                  {columnProfile.uniqueCount.toLocaleString()}
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                <div className="text-slate-600 text-sm mb-1">Total Count</div>
                <div className="text-2xl font-bold text-slate-900">
                  {columnProfile.totalCount.toLocaleString()}
                </div>
              </div>
            </div>

            {/* Role-specific details */}
            {columnProfile.role === "dimension" && <DimensionDetails column={columnProfile} />}
            {columnProfile.role === "measure" && <MeasureDetails column={columnProfile} />}
            {columnProfile.role === "temporal" && <TemporalDetails column={columnProfile} />}

            {/* Suggested Charts */}
            {suggestedCharts && suggestedCharts.length > 0 && (
              <div className="bg-white/5 border border-white/10 rounded-xl p-5">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-[#5237ff]" />
                  Suggested Charts
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  {suggestedCharts.map((chart, index) => (
                    <button
                      key={`${chart.type}-${chart.xAxis}-${index}`}
                      onClick={() => handleChartSuggestionClick(chart)}
                      className="flex items-center justify-between p-4 bg-white/[0.03] hover:bg-[#5237ff]/10 border border-white/10 hover:border-[#5237ff]/30 rounded-xl transition-all group"
                    >
                      <div className="flex items-center gap-3">
                        <BarChart3 className="w-5 h-5 text-[#5237ff]" />
                        <span className="text-gray-300 group-hover:text-[#7b69ff]">{chart.title}</span>
                      </div>
                      <ArrowRight className="w-4 h-4 text-gray-500 group-hover:text-[#5237ff]" />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
}
