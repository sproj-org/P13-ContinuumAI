"use client";

import ProtectedRoute from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/auth-context";
import { useAppStore } from "@/lib/store";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Database, Plus, LogOut, BarChart3, TrendingUp, Sparkles, Activity, CheckCircle2 } from "lucide-react";

function DashboardContent() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const setActiveDataset = useAppStore((state) => state.setActiveDataset);
  const setSelectedDatasetId = useAppStore((state) => state.setSelectedDatasetId);

  const handleDatasetSelect = (datasetId: "silkroute") => {
    setSelectedDatasetId(datasetId);
    setActiveDataset(datasetId);
    router.push(`/workspace/${datasetId}`);
  };

  const capitalizedName = user?.username 
    ? user.username.charAt(0).toUpperCase() + user.username.slice(1) 
    : "there";

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50/20 relative overflow-hidden">
      {/* Decorative background elements */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-gradient-to-br from-indigo-100/40 to-violet-100/40 rounded-full blur-3xl opacity-50" />
      <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-gradient-to-tr from-blue-100/30 to-slate-100/30 rounded-full blur-3xl opacity-40" />
      
      {/* Nav */}
      <nav className="relative z-10 border-b border-slate-200/50 bg-white/60 backdrop-blur-md shadow-sm">
        <div className="px-6">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 className="text-2xl font-bold text-slate-900 font-[family-name:var(--font-special-gothic)]">
                ContinuumAI
              </h1>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-slate-700 text-sm font-medium">
                {user?.username || "User"}
              </span>
              <button
                onClick={logout}
                className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 rounded-lg hover:bg-slate-100 transition-colors"
              >
                <LogOut className="w-4 h-4" />
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="relative z-10 max-w-6xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        {/* Welcome Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-12"
        >
          <h2 className="text-4xl font-bold text-slate-900 mb-3">
            Hello, {capitalizedName}!
          </h2>
          <p className="text-lg text-slate-600 max-w-2xl mx-auto">
            Your data has stories — let&apos;s uncover them.
          </p>
        </motion.div>

        {/* Quick Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12"
        >
          <div className="bg-white/70 backdrop-blur-sm border border-slate-200/50 rounded-xl p-4 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">
                <Database className="w-5 h-5 text-indigo-600" />
              </div>
              <div>
                <p className="text-xs text-slate-500 font-medium">Active Datasets</p>
                <p className="text-2xl font-bold text-slate-900">1</p>
              </div>
            </div>
          </div>
          <div className="bg-white/70 backdrop-blur-sm border border-slate-200/50 rounded-xl p-4 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
                <BarChart3 className="w-5 h-5 text-emerald-600" />
              </div>
              <div>
                <p className="text-xs text-slate-500 font-medium">Data Quality</p>
                <p className="text-2xl font-bold text-slate-900">98%</p>
              </div>
            </div>
          </div>
          <div className="bg-white/70 backdrop-blur-sm border border-slate-200/50 rounded-xl p-4 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-violet-100 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5 text-violet-600" />
              </div>
              <div>
                <p className="text-xs text-slate-500 font-medium">Data Status</p>
                <div className="flex items-center gap-2">
                  <p className="text-2xl font-bold text-emerald-600">Synced</p>
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500 shadow-lg shadow-emerald-500/50"></span>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Datasets Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Your Datasets</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Connect New Database Card */}
            <div className="group relative p-6 rounded-2xl border border-slate-200/60 bg-white/40 backdrop-blur-sm opacity-60 cursor-not-allowed shadow-sm">
              <div className="absolute top-4 right-4">
                <span className="px-2 py-1 text-xs font-medium rounded-full bg-slate-200 text-slate-500">
                  Coming Soon
                </span>
              </div>
              <div className="w-14 h-14 rounded-xl bg-slate-200 flex items-center justify-center mb-4">
                <Plus className="w-7 h-7 text-slate-400" />
              </div>
              <h3 className="text-lg font-semibold text-slate-500 mb-2">
                Connect New Database
              </h3>
              <p className="text-sm text-slate-400">
                Connect your own PostgreSQL, MySQL, or other data sources
              </p>
            </div>

            {/* SilkRoute Dataset Card */}
            <button
              onClick={() => handleDatasetSelect("silkroute")}
              className="w-full text-left group relative p-6 rounded-2xl border border-slate-200/60 bg-white/70 backdrop-blur-sm hover:bg-white hover:border-indigo-300 transition-all duration-300 shadow-sm hover:shadow-lg"
            >
              <div className="absolute top-4 right-4">
                <span className="px-2 py-1 text-xs font-medium rounded-full bg-emerald-100 text-emerald-700">
                  Ready
                </span>
              </div>
              <div className="w-14 h-14 rounded-xl bg-indigo-100 border border-indigo-200 flex items-center justify-center mb-4 group-hover:scale-105 transition-transform">
                <Database className="w-7 h-7 text-indigo-600" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2 group-hover:text-indigo-600 transition-colors">
                SilkRoute
              </h3>
              <p className="text-sm text-slate-600 mb-4">
                Retail benchmark dataset with sales, customers, stores, and inventory data
              </p>
              <div className="flex flex-wrap gap-2">
                <span className="px-2 py-1 text-xs rounded-md bg-slate-100 text-slate-700">
                  45K+ transactions
                </span>
                <span className="px-2 py-1 text-xs rounded-md bg-slate-100 text-slate-700">
                  2.5K customers
                </span>
                <span className="px-2 py-1 text-xs rounded-md bg-slate-100 text-slate-700">
                  6 stores
                </span>
              </div>
            </button>
          </div>
        </motion.div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 mt-20 border-t border-slate-200/50 bg-white/40 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-center items-center text-xs text-slate-500">
            <p>© 2026 ContinuumAI • Build 4.12.0</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
