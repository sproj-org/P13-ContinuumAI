"use client";

import { useState } from "react";
import { useAppStore } from "@/lib/store";
import { useTableProfile } from "@/lib/hooks";
import {
  getColumnRoleDistribution,
  calculateTableMissingPercentage,
  transformColumnProfile,
  generateSuggestedQuestions,
  type TransformedColumnProfile,
  type ColumnRole,
  formatDate,
} from "@/lib/transformers";
import { motion, AnimatePresence } from "framer-motion";
import dynamic from "next/dynamic";
import {
  Database,
  Activity,
  BarChart3,
  Clock,
  TrendingUp,
  Hash,
  Calendar,
  Loader2,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  CheckCircle2,
  HelpCircle,
} from "lucide-react";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

const roleIcons: Record<ColumnRole, React.ReactNode> = {
  dimension: <Hash className="w-4 h-4" />,
  measure: <BarChart3 className="w-4 h-4" />,
  temporal: <Calendar className="w-4 h-4" />,
};

const roleColors: Record<ColumnRole, { bg: string; text: string; border: string; label: string }> = {
  dimension: { bg: "bg-blue-100", text: "text-blue-700", border: "border-blue-300", label: "DIMENSION" },
<<<<<<< HEAD
  measure: { bg: "bg-indigo-100", text: "text-indigo-700", border: "border-indigo-300", label: "MEASURE" },
=======
  measure: { bg: "bg-emerald-100", text: "text-emerald-700", border: "border-emerald-300", label: "MEASURE" },
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
  temporal: { bg: "bg-amber-100", text: "text-amber-700", border: "border-amber-300", label: "TEMPORAL" },
};

function getNullColor(percentage: number) {
<<<<<<< HEAD
  if (percentage < 5) return "text-indigo-600";
=======
  if (percentage < 5) return "text-emerald-600";
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
  if (percentage < 20) return "text-amber-600";
  return "text-red-600";
}

function getQualityColor(percentage: number) {
<<<<<<< HEAD
  if (percentage < 5) return "bg-indigo-500";
=======
  if (percentage < 5) return "bg-emerald-500";
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
  if (percentage < 20) return "bg-amber-500";
  return "bg-red-500";
}

function formatNumber(num: number): string {
  if (num < 1000) {
    return num.toString();
  } else if (num < 1000000) {
    return `${(num / 1000).toFixed(1)}K`;
  } else {
    return `${(num / 1000000).toFixed(1)}M`;
  }
}

function getTimeAgo(dateString: string): string {
  const now = new Date();
  const past = new Date(dateString);
  const diffMs = now.getTime() - past.getTime();
  
  const diffMinutes = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const diffMonths = Math.floor(diffDays / 30);
  const diffYears = Math.floor(diffDays / 365);
  
  if (diffMinutes < 60) {
    return `${diffMinutes}m`;
  } else if (diffHours < 24) {
    return `${diffHours}h`;
  } else if (diffDays < 30) {
    return `${diffDays}d`;
  } else if (diffMonths < 12) {
    return `${diffMonths}mo`;
  } else {
    return `${diffYears}y`;
  }
}

function DimensionDetails({ column }: { column: TransformedColumnProfile }) {
  return (
    <div className="p-6 bg-gradient-to-br from-slate-50 to-indigo-50/20 border-t border-slate-200">
      <div className="space-y-6">
        {/* Cardinality */}
        {column.cardinality && (
          <div className="flex items-center gap-4">
            <span className="text-slate-600 text-sm font-medium">Cardinality:</span>
            <span className={`px-3 py-1 rounded-full text-sm font-medium capitalize ${
<<<<<<< HEAD
              column.cardinality === 'low' ? 'bg-indigo-100 text-indigo-700' :
=======
              column.cardinality === 'low' ? 'bg-emerald-100 text-emerald-700' :
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
              column.cardinality === 'medium' ? 'bg-amber-100 text-amber-700' :
              'bg-red-100 text-red-700'
            }`}>
              {column.cardinality}
            </span>
          </div>
        )}

        {/* Top Values */}
        {column.topValues && column.topValues.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold text-slate-700 mb-3">Top Values Distribution</h4>
            <div className="space-y-2">
              {column.topValues.map((item, index) => {
                const maxPercent = column.topValues[0].percent;
                const percentage = maxPercent > 0 ? (item.percent / maxPercent) * 100 : 0;
                return (
                  <div key={index} className="relative">
                    <div className="flex justify-between text-sm mb-1.5">
                      <span className="text-slate-900 font-medium">{item.value}</span>
                      <span className="text-slate-600">{item.count.toLocaleString()} ({item.percent.toFixed(1)}%)</span>
                    </div>
                    <div className="h-2.5 bg-slate-200 rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${percentage}%` }}
                        transition={{ duration: 0.5, delay: index * 0.1 }}
                        className="h-full bg-gradient-to-r from-blue-500 to-blue-600 rounded-full"
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Pie Chart for Distribution */}
        {column.topValues && column.topValues.length > 0 && column.topValues.length <= 8 && (
          <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
            <Plot
              data={[
                {
                  type: "pie",
                  values: column.topValues.map(v => v.count),
                  labels: column.topValues.map(v => v.value),
                  textinfo: "percent",
                  textposition: "inside",
                  marker: {
<<<<<<< HEAD
                    colors: ["#4F46E5", "#8b5cf6", "#a78bfa", "#6366f1", "#f59e0b", "#ef4444", "#ec4899", "#818cf8"],
=======
                    colors: ["#4F46E5", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#ec4899", "#6366f1"],
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
                  },
                  hole: 0.4,
                },
              ]}
              layout={{
                paper_bgcolor: "transparent",
                plot_bgcolor: "transparent",
                font: { color: "#64748b", size: 12 },
                showlegend: true,
                legend: { orientation: "h", y: -0.2 },
                margin: { t: 20, b: 60, l: 20, r: 20 },
                height: 280,
              }}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: "100%" }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function MeasureDetails({ column }: { column: TransformedColumnProfile }) {
  return (
<<<<<<< HEAD
    <div className="p-6 bg-gradient-to-br from-slate-50 to-indigo-50/20 border-t border-slate-200">
=======
    <div className="p-6 bg-gradient-to-br from-slate-50 to-emerald-50/20 border-t border-slate-200">
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
      <div className="space-y-6">
        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: "Min", value: column.min, color: "text-blue-600" },
<<<<<<< HEAD
            { label: "Max", value: column.max, color: "text-indigo-600" },
            { label: "Mean", value: column.mean, color: "text-violet-600" },
            { label: "Median", value: column.median, color: "text-purple-600" },
=======
            { label: "Max", value: column.max, color: "text-cyan-600" },
            { label: "Mean", value: column.mean, color: "text-emerald-600" },
            { label: "Median", value: column.median, color: "text-violet-600" },
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
          ].map((stat) => (
            <div key={stat.label} className="bg-white border border-slate-200 rounded-xl p-4 text-center shadow-sm">
              <div className="text-slate-600 text-xs mb-1.5 font-medium uppercase">{stat.label}</div>
              <div className={`text-lg font-bold ${stat.color}`}>
                {stat.value !== null && stat.value !== undefined ? stat.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "N/A"}
              </div>
            </div>
          ))}
        </div>

        {/* Suggested Aggregations */}
        <div>
          <h4 className="text-sm font-semibold text-slate-700 mb-3">Suggested Aggregations</h4>
          <div className="flex flex-wrap gap-2">
            {["SUM", "AVG", "COUNT", "MIN", "MAX"].map((agg) => (
              <span
                key={agg}
<<<<<<< HEAD
                className="px-3 py-1.5 bg-indigo-100 border border-indigo-300 rounded-lg text-indigo-700 text-sm font-medium"
=======
                className="px-3 py-1.5 bg-emerald-100 border border-emerald-300 rounded-lg text-emerald-700 text-sm font-medium"
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
              >
                {agg}({column.name})
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function TemporalDetails({ column }: { column: TransformedColumnProfile }) {
  return (
    <div className="p-6 bg-gradient-to-br from-slate-50 to-amber-50/20 border-t border-slate-200">
      <div className="space-y-6">
        {/* Time Range */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
            <div className="text-slate-600 text-xs mb-1.5 font-medium uppercase">Start Date</div>
            <div className="text-slate-900 font-semibold">{column.minDate || "N/A"}</div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
            <div className="text-slate-600 text-xs mb-1.5 font-medium uppercase">End Date</div>
            <div className="text-slate-900 font-semibold">{column.maxDate || "N/A"}</div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
            <div className="text-slate-600 text-xs mb-1.5 font-medium uppercase">Distinct Days</div>
            <div className="text-amber-600 font-semibold">{column.distinctDays?.toLocaleString() || "N/A"}</div>
          </div>
        </div>

        {/* Suggested Visualizations */}
        <div>
          <h4 className="text-sm font-semibold text-slate-700 mb-3">Suggested Visualizations</h4>
          <div className="flex flex-wrap gap-2">
            <span className="px-3 py-1.5 bg-amber-100 border border-amber-300 rounded-lg text-amber-700 text-sm font-medium">
              📈 Line Chart (Trend)
            </span>
            <span className="px-3 py-1.5 bg-amber-100 border border-amber-300 rounded-lg text-amber-700 text-sm font-medium">
              📊 Area Chart (Volume)
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function MartsTab() {
  const { selectedDatasetId, selectedAggregation, setSelectedAggregation, availableMarts } = useAppStore();
  const { data: profile, isLoading: isProfileLoading, error } = useTableProfile(
    selectedDatasetId,
    selectedAggregation
  );
  const isLoading = !!selectedAggregation && isProfileLoading;
  const [expandedColumn, setExpandedColumn] = useState<string | null>(null);

  const missingPercentage = profile ? calculateTableMissingPercentage(profile) : 0;
  const columnRoleDistribution = profile ? getColumnRoleDistribution(profile) : { dimensions: 0, measures: 0, temporal: 0 };
  const transformedColumns = profile?.columns.map(transformColumnProfile) ?? [];
  const suggestedQuestions = profile ? generateSuggestedQuestions(profile) : [];

  const getHealthScore = (missingPct: number) => {
    return Math.max(0, 100 - missingPct * 1.5).toFixed(1);
  };

  const getHealthStatus = (score: number) => {
<<<<<<< HEAD
    if (score >= 90) return { label: "High", color: "text-indigo-600", bg: "bg-indigo-100" };
=======
    if (score >= 90) return { label: "High", color: "text-emerald-600", bg: "bg-emerald-100" };
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
    if (score >= 70) return { label: "Medium", color: "text-amber-600", bg: "bg-amber-100" };
    return { label: "Low", color: "text-red-600", bg: "bg-red-100" };
  };

  return (
<<<<<<< HEAD
    <div className="flex h-full bg-gradient-to-br from-slate-50 via-indigo-50/20 to-violet-50/20">
      {/* Left Panel - Mart Selector */}
      <div className="w-80 border-r border-indigo-100 bg-white/90 backdrop-blur-sm overflow-y-auto">
        <div className="p-5 border-b border-indigo-100 bg-gradient-to-r from-white to-indigo-50/30">
          <h3 className="text-sm font-bold text-indigo-800 uppercase tracking-wider mb-1">
=======
    <div className="flex h-full bg-gradient-to-br from-slate-50 via-cyan-50/20 to-emerald-50/20">
      {/* Left Panel - Mart Selector */}
      <div className="w-80 border-r border-cyan-100 bg-white/90 backdrop-blur-sm overflow-y-auto">
        <div className="p-5 border-b border-cyan-100 bg-gradient-to-r from-white to-cyan-50/30">
          <h3 className="text-sm font-bold text-cyan-800 uppercase tracking-wider mb-1">
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
            Data Profiling
          </h3>
          <p className="text-xs text-slate-600">Select a mart to view its profile</p>
        </div>
        {availableMarts.length > 0 ? (
          <div className="p-4 space-y-2">
            {availableMarts.map((table) => (
              <button
                key={table.id}
                onClick={() => {
                  setSelectedAggregation(table.id);
                  setExpandedColumn(null); // Reset expanded column when changing mart
                }}
                className={`w-full text-left p-3.5 rounded-xl transition-all ${
                  selectedAggregation === table.id
<<<<<<< HEAD
                    ? "bg-gradient-to-r from-indigo-100 to-violet-100 border border-indigo-300 shadow-md"
                    : "bg-white border border-slate-200 hover:bg-indigo-50/50 hover:border-indigo-200 shadow-sm"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${selectedAggregation === table.id ? "bg-gradient-to-br from-[#4f46e5] to-indigo-600" : "bg-slate-100"}`}>
=======
                    ? "bg-gradient-to-r from-cyan-100 to-emerald-100 border border-cyan-300 shadow-md"
                    : "bg-white border border-slate-200 hover:bg-cyan-50/50 hover:border-cyan-200 shadow-sm"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${selectedAggregation === table.id ? "bg-gradient-to-br from-cyan-500 to-emerald-500" : "bg-slate-100"}`}>
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
                    <Database
                      className={`w-5 h-5 ${selectedAggregation === table.id ? "text-white" : "text-slate-500"}`}
                    />
                  </div>
                  <div className="flex-1 min-w-0">
<<<<<<< HEAD
                    <div className={`font-semibold text-sm truncate ${selectedAggregation === table.id ? "text-indigo-800" : "text-slate-700"}`}>
=======
                    <div className={`font-semibold text-sm truncate ${selectedAggregation === table.id ? "text-cyan-800" : "text-slate-700"}`}>
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
                      {table.label ?? table.id}
                    </div>
                    <div className="text-xs text-slate-500 truncate">
                      {table.description ?? "Registry mart"}
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="p-4">
            <p className="text-sm text-slate-500">No marts available.</p>
          </div>
        )}
      </div>

      {/* Main Panel - Mart Profile */}
      <div className="flex-1 overflow-y-auto">
        {!selectedAggregation ? (
          <div className="h-full flex items-center justify-center p-6">
            <div className="text-center">
              <Database className="w-20 h-20 text-slate-300 mx-auto mb-4" />
              <h3 className="text-2xl font-bold text-slate-600 mb-2">Select a Data Mart</h3>
              <p className="text-slate-500">Choose a mart from the left panel to view its comprehensive profile</p>
            </div>
          </div>
        ) : isLoading ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
<<<<<<< HEAD
              <Loader2 className="w-12 h-12 text-indigo-600 mx-auto mb-4 animate-spin" />
=======
              <Loader2 className="w-12 h-12 text-cyan-600 mx-auto mb-4 animate-spin" />
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
              <h3 className="text-lg font-medium text-slate-600">Loading mart profile...</h3>
            </div>
          </div>
        ) : error ? (
          <div className="h-full flex items-center justify-center p-6">
            <div className="text-center">
              <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-slate-600 mb-2">Failed to load profile</h3>
              <p className="text-slate-500 text-sm">Please try again later</p>
            </div>
          </div>
        ) : profile ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
            className="pb-8"
          >
            {/* Header Section */}
<<<<<<< HEAD
            <div className="sticky top-0 z-10 bg-white/95 backdrop-blur-sm border-b border-indigo-100 shadow-sm">
=======
            <div className="sticky top-0 z-10 bg-white/95 backdrop-blur-sm border-b border-cyan-100 shadow-sm">
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
              <div className="px-8 py-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h2 className="text-3xl font-bold text-slate-900 mb-1">
                      {(profile.table_name ?? profile.dataset_name).replaceAll(/_/g, " ").replaceAll(/\b\w/g, l => l.toUpperCase())}
                    </h2>
                    <p className="text-slate-600">
                      {profile.schema_name ?? "aggregations"}.{profile.table_name ?? profile.dataset_name}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 text-slate-500 text-sm bg-slate-100 px-3 py-2 rounded-lg">
                    <Clock className="w-4 h-4" />
                    Last profiled: {formatDate(profile.profiled_at)}
                  </div>
                </div>

                {/* Summary Cards */}
                <div className="grid grid-cols-4 gap-4">
<<<<<<< HEAD
                  <div className="bg-gradient-to-br from-indigo-50 to-violet-50 border border-indigo-200 rounded-xl p-4 shadow-sm">
                    <div className="flex items-center gap-2 text-indigo-700 text-sm mb-2 font-medium">
                      <Activity className="w-4 h-4" />
                      Data Health Score
                    </div>
                    <div className="text-3xl font-bold text-indigo-600">
                      {getHealthScore(missingPercentage)}%
                    </div>
                    <div className="text-xs text-indigo-600 mt-1">
=======
                  <div className="bg-gradient-to-br from-cyan-50 to-emerald-50 border border-cyan-200 rounded-xl p-4 shadow-sm">
                    <div className="flex items-center gap-2 text-cyan-700 text-sm mb-2 font-medium">
                      <Activity className="w-4 h-4" />
                      Data Health Score
                    </div>
                    <div className="text-3xl font-bold text-cyan-600">
                      {getHealthScore(missingPercentage)}%
                    </div>
                    <div className="text-xs text-cyan-600 mt-1">
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
                      {getHealthStatus(parseFloat(getHealthScore(missingPercentage))).label}
                    </div>
                  </div>

                  <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                    <div className="flex items-center gap-2 text-slate-600 text-sm mb-2 font-medium">
                      <Database className="w-4 h-4" />
                      Total Records
                    </div>
                    <div className="text-3xl font-bold text-slate-900">
                      {formatNumber(profile.row_count)}
                    </div>
                    <div className="text-xs text-slate-600 mt-1">
                      {profile.row_count.toLocaleString()} rows
                    </div>
                  </div>

                  {/* Note: Schema Stability is a placeholder metric - in production this would track schema changes over time */}
                  <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                    <div className="flex items-center gap-2 text-slate-600 text-sm mb-2 font-medium">
                      <CheckCircle2 className="w-4 h-4" />
                      Schema Stability
                    </div>
                    <div className="text-3xl font-bold text-slate-900">
                      High
                    </div>
                    <div className="text-xs text-slate-600 mt-1">
                      0 Drift detected
                    </div>
                  </div>

                  <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                    <div className="flex items-center gap-2 text-slate-600 text-sm mb-2 font-medium">
                      <Clock className="w-4 h-4" />
                      Last Refreshed
                    </div>
                    <div className="text-3xl font-bold text-slate-900">
                      {getTimeAgo(profile.profiled_at)}
                    </div>
                    <div className="text-xs text-slate-600 mt-1">
                      ago
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Column Distribution */}
            <div className="px-8 py-6">
              <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
<<<<<<< HEAD
                    <BarChart3 className="w-5 h-5 text-indigo-600" />
=======
                    <BarChart3 className="w-5 h-5 text-cyan-600" />
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
                    Column Distribution
                  </h3>
                  <div className="flex items-center gap-4 text-sm">
                    <div className="flex items-center gap-2">
                      <span className="text-slate-600">Measures ({columnRoleDistribution.measures})</span>
<<<<<<< HEAD
                      <div className="w-3 h-3 rounded-full bg-indigo-600"></div>
=======
                      <div className="w-3 h-3 rounded-full bg-emerald-600"></div>
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-slate-600">Dimensions ({columnRoleDistribution.dimensions})</span>
                      <div className="w-3 h-3 rounded-full bg-blue-600"></div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-slate-600">Temporal ({columnRoleDistribution.temporal})</span>
                      <div className="w-3 h-3 rounded-full bg-amber-600"></div>
                    </div>
                  </div>
                </div>
                <div className="h-12 bg-slate-100 rounded-full overflow-hidden flex">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${(columnRoleDistribution.measures / profile.column_count) * 100}%` }}
                    transition={{ duration: 0.8 }}
<<<<<<< HEAD
                    className="bg-indigo-600 h-full flex items-center justify-center text-white text-sm font-medium"
=======
                    className="bg-emerald-600 h-full flex items-center justify-center text-white text-sm font-medium"
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
                  >
                    {((columnRoleDistribution.measures / profile.column_count) * 100).toFixed(0)}%
                  </motion.div>
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${(columnRoleDistribution.dimensions / profile.column_count) * 100}%` }}
                    transition={{ duration: 0.8, delay: 0.2 }}
                    className="bg-blue-600 h-full flex items-center justify-center text-white text-sm font-medium"
                  >
                    {((columnRoleDistribution.dimensions / profile.column_count) * 100).toFixed(0)}%
                  </motion.div>
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${(columnRoleDistribution.temporal / profile.column_count) * 100}%` }}
                    transition={{ duration: 0.8, delay: 0.4 }}
                    className="bg-amber-600 h-full flex items-center justify-center text-white text-sm font-medium"
                  >
                    {((columnRoleDistribution.temporal / profile.column_count) * 100).toFixed(0)}%
                  </motion.div>
                </div>
              </div>
            </div>

            {/* Schema Inventory */}
            <div className="px-8">
              <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
<<<<<<< HEAD
                <div className="px-6 py-4 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-indigo-50/30">
=======
                <div className="px-6 py-4 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-cyan-50/30">
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
                  <h3 className="text-lg font-bold text-slate-900">
                    Schema Inventory
                  </h3>
                </div>

                {/* Table Header */}
                <div className="grid grid-cols-12 gap-4 px-6 py-3 bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                  <div className="col-span-1">Status</div>
                  <div className="col-span-3">Column Name</div>
                  <div className="col-span-2">Data Type</div>
                  <div className="col-span-2">Role</div>
                  <div className="col-span-2">Quality</div>
                  <div className="col-span-2 text-center">Nullability</div>
                </div>

                {/* Scrollable Column List */}
                <div className="max-h-[600px] overflow-y-auto">
                  {transformedColumns.map((col, index) => {
                    const isExpanded = expandedColumn === col.name;
                    const roleStyle = roleColors[col.role];
                    const qualityScore = 100 - col.nullPercentage;

                    return (
                      <div key={col.name}>
                        <button
                          onClick={() => setExpandedColumn(isExpanded ? null : col.name)}
<<<<<<< HEAD
                          className="w-full grid grid-cols-12 gap-4 px-6 py-4 hover:bg-indigo-50/50 transition-colors border-b border-slate-100 text-left"
                        >
                          <div className="col-span-1 flex items-center">
                            {col.nullPercentage < 5 ? (
                              <CheckCircle2 className="w-5 h-5 text-indigo-600" />
=======
                          className="w-full grid grid-cols-12 gap-4 px-6 py-4 hover:bg-cyan-50/50 transition-colors border-b border-slate-100 text-left"
                        >
                          <div className="col-span-1 flex items-center">
                            {col.nullPercentage < 5 ? (
                              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
                            ) : col.nullPercentage < 20 ? (
                              <AlertCircle className="w-5 h-5 text-amber-600" />
                            ) : (
                              <AlertCircle className="w-5 h-5 text-red-600" />
                            )}
                          </div>
                          
                          <div className="col-span-3 flex items-center gap-2">
                            <span className="text-sm font-semibold text-slate-900">{col.name}</span>
                            {isExpanded ? (
                              <ChevronUp className="w-4 h-4 text-slate-400" />
                            ) : (
                              <ChevronDown className="w-4 h-4 text-slate-400" />
                            )}
                          </div>
                          
                          <div className="col-span-2 flex items-center">
                            <span className="text-sm text-slate-600 font-mono">{col.dataType}</span>
                          </div>
                          
                          <div className="col-span-2 flex items-center">
                            <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${roleStyle.bg} ${roleStyle.text} uppercase`}>
                              {roleStyle.label}
                            </span>
                          </div>
                          
                          <div className="col-span-2 flex items-center gap-2">
                            <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
                              <div
                                className={`h-full ${getQualityColor(col.nullPercentage)}`}
                                style={{ width: `${qualityScore}%` }}
                              />
                            </div>
                            <span className="text-sm font-semibold text-slate-700">{qualityScore.toFixed(0)}%</span>
                          </div>
                          
                          <div className="col-span-2 flex items-center justify-center">
                            <span className={`text-sm font-semibold ${getNullColor(col.nullPercentage)}`}>
                              {col.nullPercentage.toFixed(1)}%
                            </span>
                          </div>
                        </button>

                        {/* Expanded Column Details */}
                        <AnimatePresence>
                          {isExpanded && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: "auto", opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              transition={{ duration: 0.3 }}
                              className="overflow-hidden"
                            >
                              {col.role === "dimension" && <DimensionDetails column={col} />}
                              {col.role === "measure" && <MeasureDetails column={col} />}
                              {col.role === "temporal" && <TemporalDetails column={col} />}
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    );
                  })}
                </div>

                {transformedColumns.length === 0 && (
                  <div className="py-12 text-center text-slate-500">
                    <Database className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p>No columns found in this mart</p>
                  </div>
                )}
              </div>
            </div>

            {/* Suggested Questions */}
            {suggestedQuestions.length > 0 && (
              <div className="px-8 py-6">
                <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                  <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
<<<<<<< HEAD
                    <HelpCircle className="w-5 h-5 text-indigo-600" />
=======
                    <HelpCircle className="w-5 h-5 text-cyan-600" />
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
                    Suggested Questions
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {suggestedQuestions.map((question, index) => (
                      <button
                        key={index}
<<<<<<< HEAD
                        className="px-4 py-2.5 bg-gradient-to-r from-slate-50 to-indigo-50/50 hover:from-indigo-50 hover:to-violet-50 border border-slate-200 hover:border-indigo-300 rounded-xl text-sm text-slate-700 hover:text-indigo-700 transition-all shadow-sm hover:shadow-md font-medium"
=======
                        className="px-4 py-2.5 bg-gradient-to-r from-slate-50 to-cyan-50/50 hover:from-cyan-50 hover:to-emerald-50 border border-slate-200 hover:border-cyan-300 rounded-xl text-sm text-slate-700 hover:text-cyan-700 transition-all shadow-sm hover:shadow-md font-medium"
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
                      >
                        {question}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        ) : null}
      </div>
    </div>
  );
}
