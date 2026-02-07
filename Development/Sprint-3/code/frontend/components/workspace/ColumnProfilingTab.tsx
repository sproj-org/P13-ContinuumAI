"use client";

import { useAppStore, AggregationTable } from "@/lib/store";
import { tableProfiles } from "@/lib/mock-data";
import { ColumnProfile, ColumnRole } from "@/lib/types";
import { motion } from "framer-motion";
import dynamic from "next/dynamic";
import {
  Columns3,
  BarChart3,
  Hash,
  Type,
  Calendar,
  TrendingUp,
  AlertTriangle,
  ArrowRight,
} from "lucide-react";

// Dynamic import for Plotly to avoid SSR issues
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

const aggregationTables: { id: AggregationTable; label: string }[] = [
  { id: "sales_detailed", label: "Sales Detailed" },
  { id: "customer_360", label: "Customer 360" },
  { id: "store_daily_performance", label: "Store Daily Performance" },
];

const roleIcons: Record<ColumnRole, React.ReactNode> = {
  dimension: <Hash className="w-4 h-4" />,
  measure: <BarChart3 className="w-4 h-4" />,
  temporal: <Calendar className="w-4 h-4" />,
};

const roleColors: Record<ColumnRole, { bg: string; text: string; border: string }> = {
  dimension: { bg: "bg-blue-500/20", text: "text-blue-400", border: "border-blue-500/30" },
  measure: { bg: "bg-emerald-500/20", text: "text-emerald-400", border: "border-emerald-500/30" },
  temporal: { bg: "bg-amber-500/20", text: "text-amber-400", border: "border-amber-500/30" },
};

function getNullColor(percentage: number) {
  if (percentage < 5) return "bg-emerald-500";
  if (percentage < 20) return "bg-amber-500";
  return "bg-red-500";
}

function DimensionDetails({ column }: { column: ColumnProfile }) {
  const cardinalityColors = {
    low: "bg-emerald-500/20 text-emerald-400",
    medium: "bg-amber-500/20 text-amber-400",
    high: "bg-red-500/20 text-red-400",
  };

  return (
    <div className="space-y-6">
      {/* Cardinality */}
      {column.cardinality && (
        <div className="flex items-center gap-4">
          <span className="text-gray-400 text-sm">Cardinality:</span>
          <span className={`px-3 py-1 rounded-full text-sm font-medium capitalize ${cardinalityColors[column.cardinality]}`}>
            {column.cardinality}
          </span>
        </div>
      )}

      {/* Top Values */}
      {column.topValues && column.topValues.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-400 mb-3">Top Values</h4>
          <div className="space-y-2">
            {column.topValues.map((item, index) => {
              const maxCount = column.topValues![0].count;
              const percentage = (item.count / maxCount) * 100;
              return (
                <div key={index} className="relative">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-300">{item.value}</span>
                    <span className="text-gray-400">{item.count.toLocaleString()}</span>
                  </div>
                  <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${percentage}%` }}
                      transition={{ duration: 0.5, delay: index * 0.1 }}
                      className="h-full bg-blue-500 rounded-full"
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

function MeasureDetails({ column }: { column: ColumnProfile }) {
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
          <div key={stat.label} className="bg-white/5 rounded-xl p-4 text-center">
            <div className="text-gray-400 text-xs mb-1">{stat.label}</div>
            <div className="text-white font-semibold">
              {stat.value !== undefined ? stat.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "N/A"}
            </div>
          </div>
        ))}
      </div>

      {/* Outliers */}
      {column.outlierCount !== undefined && column.outlierCount > 0 && (
        <div className="flex items-center gap-2 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <span className="text-amber-300 text-sm">
            {column.outlierCount.toLocaleString()} outliers detected
          </span>
        </div>
      )}

      {/* Histogram */}
      {column.histogram && column.histogram.length > 0 && (
        <div className="bg-white/[0.03] rounded-xl p-4">
          <h4 className="text-sm font-medium text-gray-400 mb-3">Distribution</h4>
          <Plot
            data={[
              {
                type: "bar",
                x: column.histogram.map(h => h.bin),
                y: column.histogram.map(h => h.count),
                marker: {
                  color: "#10b981",
                  opacity: 0.8,
                },
              },
            ]}
            layout={{
              paper_bgcolor: "transparent",
              plot_bgcolor: "transparent",
              font: { color: "#94a3b8", size: 11 },
              xaxis: { gridcolor: "#334155", title: { text: "Range", font: { size: 11 } } },
              yaxis: { gridcolor: "#334155", title: { text: "Count", font: { size: 11 } } },
              margin: { t: 20, b: 60, l: 60, r: 20 },
              height: 220,
              bargap: 0.1,
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
          />
        </div>
      )}

      {/* Suggested KPIs */}
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

function TemporalDetails({ column }: { column: ColumnProfile }) {
  return (
    <div className="space-y-6">
      {/* Time Range */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white/5 rounded-xl p-4">
          <div className="text-gray-400 text-xs mb-1">Start Date</div>
          <div className="text-white font-medium">{column.minDate || "N/A"}</div>
        </div>
        <div className="bg-white/5 rounded-xl p-4">
          <div className="text-gray-400 text-xs mb-1">End Date</div>
          <div className="text-white font-medium">{column.maxDate || "N/A"}</div>
        </div>
        <div className="bg-white/5 rounded-xl p-4">
          <div className="text-gray-400 text-xs mb-1">Granularity</div>
          <div className="text-amber-400 font-medium capitalize">{column.granularity || "Unknown"}</div>
        </div>
      </div>

      {/* Time Series Chart */}
      {column.timeSeriesData && column.timeSeriesData.length > 0 && (
        <div className="bg-white/[0.03] rounded-xl p-4">
          <h4 className="text-sm font-medium text-gray-400 mb-3">Records Over Time</h4>
          <Plot
            data={[
              {
                type: "scatter",
                mode: "lines+markers",
                x: column.timeSeriesData.map(d => d.date),
                y: column.timeSeriesData.map(d => d.count),
                line: { color: "#f59e0b", width: 2 },
                marker: { color: "#f59e0b", size: 6 },
                fill: "tozeroy",
                fillcolor: "rgba(245, 158, 11, 0.1)",
              },
            ]}
            layout={{
              paper_bgcolor: "transparent",
              plot_bgcolor: "transparent",
              font: { color: "#94a3b8", size: 11 },
              xaxis: { gridcolor: "#334155" },
              yaxis: { gridcolor: "#334155", title: { text: "Count", font: { size: 11 } } },
              margin: { t: 20, b: 40, l: 60, r: 20 },
              height: 220,
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
          />
        </div>
      )}

      {/* Suggested Charts */}
      <div>
        <h4 className="text-sm font-medium text-gray-400 mb-3">Suggested Visualizations</h4>
        <div className="flex gap-2">
          <span className="px-3 py-1.5 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-400 text-sm font-medium">
            Line Chart (Trend)
          </span>
          <span className="px-3 py-1.5 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-400 text-sm font-medium">
            Area Chart (Volume)
          </span>
        </div>
      </div>
    </div>
  );
}

export default function ColumnProfilingTab() {
  const { selectedAggregation, setSelectedAggregation, selectedColumn, setSelectedColumn, setActiveTab, setChartConfig } = useAppStore();
  const profile = selectedAggregation ? tableProfiles[selectedAggregation] : null;
  const columnProfile = profile?.columns.find(c => c.name === selectedColumn);

  const handleChartSuggestionClick = (chart: { type: string; xAxis?: string; yAxis?: string }) => {
    setChartConfig({
      chartType: chart.type as 'bar' | 'line' | 'pie' | 'histogram',
      xAxis: chart.xAxis || null,
      yAxis: chart.yAxis || null,
    });
    setActiveTab("chart-builder");
  };

  return (
    <div className="flex h-full">
      {/* Left Panel - Table & Column Selector */}
      <div className="w-72 border-r border-white/10 bg-[#060010]/50 overflow-y-auto">
        {/* Table Selector */}
        <div className="p-4 border-b border-white/10">
          <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
            Table
          </h3>
          <select
            value={selectedAggregation || ""}
            onChange={(e) => setSelectedAggregation(e.target.value as AggregationTable)}
            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-[#5237ff]/50"
          >
            <option value="">Select a table</option>
            {aggregationTables.map((table) => (
              <option key={table.id} value={table.id}>
                {table.label}
              </option>
            ))}
          </select>
        </div>

        {/* Column List */}
        <div className="p-4">
          <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
            Columns
          </h3>
          {profile ? (
            <div className="space-y-1">
              {profile.columns.map((col) => {
                const roleStyle = roleColors[col.role];
                return (
                  <button
                    key={col.name}
                    onClick={() => setSelectedColumn(col.name)}
                    className={`w-full text-left p-2.5 rounded-lg transition-all flex items-center gap-2 ${
                      selectedColumn === col.name
                        ? "bg-[#5237ff]/20 border border-[#5237ff]/30"
                        : "hover:bg-white/5"
                    }`}
                  >
                    <div className={`p-1 rounded ${roleStyle.bg} ${roleStyle.text}`}>
                      {roleIcons[col.role]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className={`text-sm font-medium truncate ${selectedColumn === col.name ? "text-white" : "text-gray-300"}`}>
                        {col.name}
                      </div>
                      <div className="text-xs text-gray-500">{col.dataType}</div>
                    </div>
                    {col.nullPercentage > 0 && (
                      <span className="text-xs text-gray-500">{col.nullPercentage}%</span>
                    )}
                  </button>
                );
              })}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">Select a table first</p>
          )}
        </div>
      </div>

      {/* Main Panel - Column Details */}
      <div className="flex-1 overflow-y-auto p-6">
        {!selectedColumn || !columnProfile ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <Columns3 className="w-16 h-16 text-gray-600 mx-auto mb-4" />
              <h3 className="text-xl font-medium text-gray-400 mb-2">Select a Column</h3>
              <p className="text-gray-500">Choose a column from the left panel to view its profile</p>
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
                  <h2 className="text-2xl font-bold text-white">{columnProfile.name}</h2>
                  <div className="flex items-center gap-3 mt-1">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${roleColors[columnProfile.role].bg} ${roleColors[columnProfile.role].text}`}>
                      {columnProfile.role}
                    </span>
                    <span className="text-gray-400 text-sm flex items-center gap-1">
                      <Type className="w-3 h-3" />
                      {columnProfile.dataType}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                <div className="text-gray-400 text-sm mb-1">Null %</div>
                <div className="flex items-center gap-3">
                  <span className="text-2xl font-bold text-white">{columnProfile.nullPercentage}%</span>
                  <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${getNullColor(columnProfile.nullPercentage)}`}
                      style={{ width: `${columnProfile.nullPercentage}%` }}
                    />
                  </div>
                </div>
              </div>

              <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                <div className="text-gray-400 text-sm mb-1">Unique Values</div>
                <div className="text-2xl font-bold text-white">
                  {columnProfile.uniqueCount.toLocaleString()}
                </div>
              </div>

              <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                <div className="text-gray-400 text-sm mb-1">Total Count</div>
                <div className="text-2xl font-bold text-white">
                  {columnProfile.totalCount.toLocaleString()}
                </div>
              </div>
            </div>

            {/* Role-specific details */}
            {columnProfile.role === "dimension" && <DimensionDetails column={columnProfile} />}
            {columnProfile.role === "measure" && <MeasureDetails column={columnProfile} />}
            {columnProfile.role === "temporal" && <TemporalDetails column={columnProfile} />}

            {/* Suggested Charts */}
            {columnProfile.suggestedCharts && columnProfile.suggestedCharts.length > 0 && (
              <div className="bg-white/5 border border-white/10 rounded-xl p-5">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-[#5237ff]" />
                  Suggested Charts
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  {columnProfile.suggestedCharts.map((chart, index) => (
                    <button
                      key={index}
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
