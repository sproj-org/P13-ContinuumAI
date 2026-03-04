"use client";

import { useAppStore } from "@/lib/store";
import { useTableProfile } from "@/lib/hooks";
import {
  getColumnRoleDistribution,
  calculateTableMissingPercentage,
  generateInsights,
  generateSuggestedQuestions,
  formatDate,
} from "@/lib/transformers";
import { motion } from "framer-motion";
import {
  Table2,
  Columns3,
  AlertTriangle,
  TrendingUp,
  Clock,
  PieChart,
  Lightbulb,
  HelpCircle,
  Loader2,
} from "lucide-react";

export default function TableProfilingTab() {
  const { selectedDatasetId, selectedAggregation, setSelectedAggregation, availableMarts } = useAppStore();
  const { data: profile, isLoading: isProfileLoading, error } = useTableProfile(
    selectedDatasetId,
    selectedAggregation
  );
  const isLoading = !!selectedAggregation && isProfileLoading;

  // Derive values from profile using transformers
  const missingPercentage = profile ? calculateTableMissingPercentage(profile) : 0;
  const columnRoleDistribution = profile ? getColumnRoleDistribution(profile) : { dimensions: 0, measures: 0, temporal: 0 };
  const keyInsights = profile ? generateInsights(profile) : [];
  const suggestedQuestions = profile ? generateSuggestedQuestions(profile) : [];

  const getMissingDataColor = (percentage: number) => {
    if (percentage < 5) return "text-emerald-400";
    if (percentage < 20) return "text-amber-400";
    return "text-red-400";
  };

  const getMissingDataBg = (percentage: number) => {
    if (percentage < 5) return "bg-emerald-500/20";
    if (percentage < 20) return "bg-amber-500/20";
    return "bg-red-500/20";
  };

  return (
    <div className="flex h-full">
      {/* Left Panel - Table Selector */}
      <div className="w-72 border-r border-slate-200 bg-slate-50 p-4 overflow-y-auto">
        <h3 className="text-sm font-medium text-slate-600 uppercase tracking-wider mb-4">
          Aggregation Tables
        </h3>
        {availableMarts.length > 0 ? (
          <div className="space-y-2">
            {availableMarts.map((table) => (
              <button
                key={table.id}
                onClick={() => setSelectedAggregation(table.id)}
                className={`w-full text-left p-3 rounded-xl transition-all ${
                  selectedAggregation === table.id
                    ? "bg-indigo-100 border border-indigo-200 text-slate-900"
                    : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-100 hover:border-slate-300"
                }`}
              >
                <div className="flex items-center gap-3">
                  <Table2
                    className={`w-5 h-5 ${selectedAggregation === table.id ? "text-[#4F46E5]" : "text-slate-500"}`}
                  />
                  <div>
                    <div className="font-medium text-sm">
                      {table.label ?? table.id}
                    </div>
                    <div className="text-xs text-slate-500">
                      {table.description ?? "Registry mart"}
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">No marts available.</p>
        )}
      </div>

      {/* Main Panel - Profile View */}
      <div className="flex-1 overflow-y-auto p-6">
        {!selectedAggregation ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <Table2 className="w-16 h-16 text-slate-400 mx-auto mb-4" />
              <h3 className="text-xl font-medium text-slate-600 mb-2">Select a Table</h3>
              <p className="text-slate-500">Choose an aggregation table from the left panel</p>
            </div>
          </div>
        ) : isLoading ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <Loader2 className="w-12 h-12 text-[#4F46E5] mx-auto mb-4 animate-spin" />
              <h3 className="text-lg font-medium text-slate-600">Loading profile...</h3>
            </div>
          </div>
        ) : error ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-slate-600 mb-2">Failed to load profile</h3>
              <p className="text-slate-500 text-sm">Please try again later</p>
            </div>
          </div>
        ) : profile ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
            className="space-y-6"
          >
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-slate-900">
                  {(profile.table_name ?? profile.dataset_name).replaceAll(/_/g, " ").replaceAll(/\b\w/g, l => l.toUpperCase())}
                </h2>
                <p className="text-slate-600 mt-1">
                  {profile.schema_name ?? "aggregations"}.{profile.table_name ?? profile.dataset_name}
                </p>
              </div>
              <div className="flex items-center gap-2 text-slate-600 text-sm">
                <Clock className="w-4 h-4" />
                Last profiled: {formatDate(profile.profiled_at)}
              </div>
            </div>

            {/* Summary Cards */}
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                <div className="flex items-center gap-2 text-slate-600 text-sm mb-2">
                  <TrendingUp className="w-4 h-4" />
                  Row Count
                </div>
                <div className="text-2xl font-bold text-slate-900">
                  {profile.row_count.toLocaleString()}
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                <div className="flex items-center gap-2 text-slate-600 text-sm mb-2">
                  <Columns3 className="w-4 h-4" />
                  Columns
                </div>
                <div className="text-2xl font-bold text-slate-900">
                  {profile.column_count}
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                <div className="flex items-center gap-2 text-slate-600 text-sm mb-2">
                  <AlertTriangle className="w-4 h-4" />
                  Missing Data
                </div>
                <div className={`text-2xl font-bold ${getMissingDataColor(missingPercentage)}`}>
                  {missingPercentage.toFixed(1)}%
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                <div className="flex items-center gap-2 text-slate-600 text-sm mb-2">
                  <Columns3 className="w-4 h-4" />
                  Dimensions
                </div>
                <div className="text-2xl font-bold text-blue-600">
                  {columnRoleDistribution.dimensions}
                </div>
              </div>
            </div>

            {/* Data Quality & Column Distribution */}
            <div className="grid grid-cols-2 gap-6">
              {/* Data Quality */}
              <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-amber-600" />
                  Data Quality
                </h3>
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-slate-600">Missing Data %</span>
                      <span className={getMissingDataColor(missingPercentage)}>
                        {missingPercentage.toFixed(1)}%
                      </span>
                    </div>
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${getMissingDataBg(missingPercentage)} transition-all`}
                        style={{ width: `${Math.min(missingPercentage * 2, 100)}%` }}
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between py-2 border-t border-slate-200">
                    <span className="text-slate-600">Total Rows</span>
                    <span className="text-emerald-600 font-medium">
                      {profile.row_count.toLocaleString()}
                    </span>
                  </div>

                  <div className="flex items-center justify-between py-2 border-t border-slate-200">
                    <span className="text-slate-600">Column Count</span>
                    <span className="text-emerald-600 font-medium">
                      {profile.column_count}
                    </span>
                  </div>
                </div>
              </div>

              {/* Column Role Distribution */}
              <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
                  <PieChart className="w-5 h-5 text-[#4F46E5]" />
                  Column Role Distribution
                </h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-blue-600" />
                      <span className="text-slate-700">Dimensions</span>
                    </div>
                    <span className="text-slate-900 font-medium">{columnRoleDistribution.dimensions}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-emerald-600" />
                      <span className="text-slate-700">Measures</span>
                    </div>
                    <span className="text-slate-900 font-medium">{columnRoleDistribution.measures}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-amber-600" />
                      <span className="text-slate-700">Temporal</span>
                    </div>
                    <span className="text-slate-900 font-medium">{columnRoleDistribution.temporal}</span>
                  </div>
                </div>

                {/* Visual Bar */}
                <div className="mt-4 h-3 bg-slate-100 rounded-full overflow-hidden flex">
                  <div
                    className="bg-blue-600 h-full"
                    style={{
                      width: `${(columnRoleDistribution.dimensions / profile.column_count) * 100}%`,
                    }}
                  />
                  <div
                    className="bg-emerald-600 h-full"
                    style={{
                      width: `${(columnRoleDistribution.measures / profile.column_count) * 100}%`,
                    }}
                  />
                  <div
                    className="bg-amber-600 h-full"
                    style={{
                      width: `${(columnRoleDistribution.temporal / profile.column_count) * 100}%`,
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Key Insights */}
            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
              <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
                <Lightbulb className="w-5 h-5 text-yellow-600" />
                Key Insights
              </h3>
              <div className="grid grid-cols-1 gap-3">
                {keyInsights.map((insight, index) => (
                  <div
                    key={index}
                    className="flex items-start gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200"
                  >
                    <div className="w-6 h-6 rounded-full bg-indigo-100 flex items-center justify-center shrink-0 mt-0.5">
                      <span className="text-xs text-[#4F46E5] font-medium">{index + 1}</span>
                    </div>
                    <p className="text-slate-700 text-sm">{insight}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Suggested Questions */}
            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
              <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
                <HelpCircle className="w-5 h-5 text-cyan-600" />
                Suggested Questions
              </h3>
              <div className="flex flex-wrap gap-2">
                {suggestedQuestions.map((question, index) => (
                  <button
                    key={index}
                    className="px-4 py-2 bg-slate-50 hover:bg-indigo-50 border border-slate-200 hover:border-indigo-200 rounded-full text-sm text-slate-700 hover:text-[#4F46E5] transition-all"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          </motion.div>
        ) : null}
      </div>
    </div>
  );
}
