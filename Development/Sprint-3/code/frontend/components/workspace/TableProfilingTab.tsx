"use client";

import { useAppStore, AggregationTable } from "@/lib/store";
import { tableProfiles } from "@/lib/mock-data";
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
  CheckCircle,
  XCircle,
} from "lucide-react";

const aggregationTables: { id: AggregationTable; label: string; description: string }[] = [
  { id: "sales_detailed", label: "Sales Detailed", description: "Transaction-level sales data" },
  { id: "customer_360", label: "Customer 360", description: "Customer profiles and metrics" },
  { id: "store_daily_performance", label: "Store Daily Performance", description: "Store KPIs by day" },
];

export default function TableProfilingTab() {
  const { selectedAggregation, setSelectedAggregation } = useAppStore();
  const profile = selectedAggregation ? tableProfiles[selectedAggregation] : null;

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
      <div className="w-72 border-r border-white/10 bg-[#060010]/50 p-4 overflow-y-auto">
        <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
          Aggregation Tables
        </h3>
        <div className="space-y-2">
          {aggregationTables.map((table) => (
            <button
              key={table.id}
              onClick={() => setSelectedAggregation(table.id)}
              className={`w-full text-left p-3 rounded-xl transition-all ${
                selectedAggregation === table.id
                  ? "bg-[#5237ff]/20 border border-[#5237ff]/30 text-white"
                  : "bg-white/5 border border-white/10 text-gray-300 hover:bg-white/10 hover:border-white/20"
              }`}
            >
              <div className="flex items-center gap-3">
                <Table2 className={`w-5 h-5 ${selectedAggregation === table.id ? "text-[#5237ff]" : "text-gray-500"}`} />
                <div>
                  <div className="font-medium text-sm">{table.label}</div>
                  <div className="text-xs text-gray-500">{table.description}</div>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Main Panel - Profile View */}
      <div className="flex-1 overflow-y-auto p-6">
        {!selectedAggregation ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <Table2 className="w-16 h-16 text-gray-600 mx-auto mb-4" />
              <h3 className="text-xl font-medium text-gray-400 mb-2">Select a Table</h3>
              <p className="text-gray-500">Choose an aggregation table from the left panel</p>
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
                <h2 className="text-2xl font-bold text-white">{profile.tableName.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}</h2>
                <p className="text-gray-400 mt-1">aggregations.{profile.tableName}</p>
              </div>
              <div className="flex items-center gap-2 text-gray-400 text-sm">
                <Clock className="w-4 h-4" />
                Last updated: {profile.lastUpdated}
              </div>
            </div>

            {/* Summary Cards */}
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
                  <TrendingUp className="w-4 h-4" />
                  Row Count
                </div>
                <div className="text-2xl font-bold text-white">
                  {profile.rowCount.toLocaleString()}
                </div>
              </div>

              <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
                  <Columns3 className="w-4 h-4" />
                  Columns
                </div>
                <div className="text-2xl font-bold text-white">
                  {profile.columnCount}
                </div>
              </div>

              <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
                  <AlertTriangle className="w-4 h-4" />
                  Missing Data
                </div>
                <div className={`text-2xl font-bold ${getMissingDataColor(profile.missingPercentage)}`}>
                  {profile.missingPercentage}%
                </div>
              </div>

              <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
                  <CheckCircle className="w-4 h-4" />
                  Duplicates
                </div>
                <div className={`text-2xl font-bold ${profile.duplicateRows === 0 ? "text-emerald-400" : "text-amber-400"}`}>
                  {profile.duplicateRows}
                </div>
              </div>
            </div>

            {/* Data Quality & Column Distribution */}
            <div className="grid grid-cols-2 gap-6">
              {/* Data Quality */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-5">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-amber-400" />
                  Data Quality
                </h3>
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-400">Missing Data %</span>
                      <span className={getMissingDataColor(profile.missingPercentage)}>
                        {profile.missingPercentage}%
                      </span>
                    </div>
                    <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${getMissingDataBg(profile.missingPercentage)} transition-all`}
                        style={{ width: `${Math.min(profile.missingPercentage * 2, 100)}%` }}
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between py-2 border-t border-white/10">
                    <span className="text-gray-400">Duplicate Rows</span>
                    <div className="flex items-center gap-2">
                      {profile.duplicateRows === 0 ? (
                        <CheckCircle className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-400" />
                      )}
                      <span className={profile.duplicateRows === 0 ? "text-emerald-400" : "text-red-400"}>
                        {profile.duplicateRows}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between py-2 border-t border-white/10">
                    <span className="text-gray-400">Outliers Present</span>
                    <div className="flex items-center gap-2">
                      {profile.hasOutliers ? (
                        <>
                          <AlertTriangle className="w-4 h-4 text-amber-400" />
                          <span className="text-amber-400">Yes</span>
                        </>
                      ) : (
                        <>
                          <CheckCircle className="w-4 h-4 text-emerald-400" />
                          <span className="text-emerald-400">No</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Column Role Distribution */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-5">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <PieChart className="w-5 h-5 text-[#5237ff]" />
                  Column Role Distribution
                </h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-blue-500" />
                      <span className="text-gray-300">Dimensions</span>
                    </div>
                    <span className="text-white font-medium">{profile.columnRoleDistribution.dimensions}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-emerald-500" />
                      <span className="text-gray-300">Measures</span>
                    </div>
                    <span className="text-white font-medium">{profile.columnRoleDistribution.measures}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-amber-500" />
                      <span className="text-gray-300">Temporal</span>
                    </div>
                    <span className="text-white font-medium">{profile.columnRoleDistribution.temporal}</span>
                  </div>
                </div>

                {/* Visual Bar */}
                <div className="mt-4 h-3 bg-white/10 rounded-full overflow-hidden flex">
                  <div
                    className="bg-blue-500 h-full"
                    style={{
                      width: `${(profile.columnRoleDistribution.dimensions / profile.columnCount) * 100}%`,
                    }}
                  />
                  <div
                    className="bg-emerald-500 h-full"
                    style={{
                      width: `${(profile.columnRoleDistribution.measures / profile.columnCount) * 100}%`,
                    }}
                  />
                  <div
                    className="bg-amber-500 h-full"
                    style={{
                      width: `${(profile.columnRoleDistribution.temporal / profile.columnCount) * 100}%`,
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Key Insights */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-5">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Lightbulb className="w-5 h-5 text-yellow-400" />
                Key Insights
              </h3>
              <div className="grid grid-cols-1 gap-3">
                {profile.keyInsights.map((insight, index) => (
                  <div
                    key={index}
                    className="flex items-start gap-3 p-3 bg-white/5 rounded-lg border border-white/10"
                  >
                    <div className="w-6 h-6 rounded-full bg-[#5237ff]/20 flex items-center justify-center shrink-0 mt-0.5">
                      <span className="text-xs text-[#5237ff] font-medium">{index + 1}</span>
                    </div>
                    <p className="text-gray-300 text-sm">{insight}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Suggested Questions */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-5">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <HelpCircle className="w-5 h-5 text-cyan-400" />
                Suggested Questions
              </h3>
              <div className="flex flex-wrap gap-2">
                {profile.suggestedQuestions.map((question, index) => (
                  <button
                    key={index}
                    className="px-4 py-2 bg-white/5 hover:bg-[#5237ff]/20 border border-white/10 hover:border-[#5237ff]/30 rounded-full text-sm text-gray-300 hover:text-[#5237ff] transition-all"
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
