"use client";

import ProtectedRoute from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/auth-context";
import { useAppStore } from "@/lib/store";
import { useRouter } from "next/navigation";
<<<<<<< HEAD
import Link from "next/link";
import { motion } from "framer-motion";
import { Database, Plus, LogOut, BarChart3, TrendingUp, Sparkles, Activity, CheckCircle2, Headphones } from "lucide-react";
=======
import { motion } from "framer-motion";
import { Database, Plus, LogOut, BarChart3, TrendingUp, Sparkles, Activity, CheckCircle2 } from "lucide-react";
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2

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
<<<<<<< HEAD
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/30 to-violet-50/20 relative overflow-hidden">
      {/* Decorative background elements - mesh gradient style */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(79,70,229,0.12),transparent_50%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_60%,rgba(99,102,241,0.10),transparent_50%)]" />
=======
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50/30 to-emerald-50/20 relative overflow-hidden">
      {/* Decorative background elements - mesh gradient style */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(6,182,212,0.15),transparent_50%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_60%,rgba(16,185,129,0.12),transparent_50%)]" />
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_90%_90%,rgba(139,92,246,0.08),transparent_50%)]" />
      
      {/* Grid pattern overlay */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808008_1px,transparent_1px),linear-gradient(to_bottom,#80808008_1px,transparent_1px)] bg-[size:24px_24px]" />
      
<<<<<<< HEAD
      {/* Nav - Pill Shaped */}
      <nav className="relative z-10 py-4 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex justify-between items-center px-6 py-3 rounded-full bg-white/80 backdrop-blur-xl shadow-lg border border-slate-200/60">
            <h1 className="text-xl font-bold bg-gradient-to-r from-slate-900 to-[#4f46e5] bg-clip-text text-transparent font-[family-name:var(--font-special-gothic)]">
              ContinuumAI
            </h1>
            <div className="flex items-center gap-2">
              <Link
                href="/support"
                className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-slate-600 hover:text-[#4f46e5] rounded-full hover:bg-indigo-50 transition-all duration-200"
              >
                <Headphones className="w-4 h-4" />
                Support
              </Link>
              <button
                onClick={logout}
                className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 rounded-full hover:bg-slate-100 transition-all duration-200"
=======
      {/* Nav */}
      <nav className="relative z-10 border-b border-slate-200/60 bg-white/80 backdrop-blur-xl shadow-sm">
        <div className="px-6">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-emerald-500 flex items-center justify-center shadow-lg shadow-cyan-500/20">
                <Sparkles className="w-4 h-4 text-white" />
              </div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-slate-900 via-cyan-900 to-emerald-900 bg-clip-text text-transparent font-[family-name:var(--font-special-gothic)]">
                ContinuumAI
              </h1>
            </div>
            <div className="flex items-center gap-4">
              <div className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-cyan-50 to-emerald-50 border border-cyan-200/50">
                <span className="text-slate-700 text-sm font-medium">
                  {user?.username || "User"}
                </span>
              </div>
              <button
                onClick={logout}
                className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 rounded-lg hover:bg-slate-100 transition-all duration-200 hover:shadow-sm"
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
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
          className="text-center mb-12 relative"
        >
<<<<<<< HEAD
          <h2 className="text-5xl font-bold bg-gradient-to-r from-slate-900 via-[#4f46e5] to-indigo-800 bg-clip-text text-transparent mb-4">
            Hello, {capitalizedName}!
          </h2>
          <p className="text-lg text-slate-600 max-w-2xl mx-auto">
            Behind every dataset is an opportunity — let&apos;s uncover insights that power smarter decisions.
=======
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-cyan-100/80 to-emerald-100/80 border border-cyan-200/50 mb-6 backdrop-blur-sm shadow-sm">
            <Activity className="w-4 h-4 text-cyan-600 animate-pulse" />
            <span className="text-xs font-medium text-cyan-900">System Status: All Systems Operational</span>
          </div>
          <h2 className="text-5xl font-bold bg-gradient-to-r from-slate-900 via-cyan-800 to-emerald-800 bg-clip-text text-transparent mb-4">
            Hello, {capitalizedName}!
          </h2>
          <p className="text-lg text-slate-600 max-w-2xl mx-auto">
            Your data has stories — let&apos;s uncover them.
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
          </p>
        </motion.div>

        {/* Quick Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12"
        >
          {/* Active Datasets Card */}
          <motion.div 
            whileHover={{ y: -4, scale: 1.02 }}
            transition={{ type: "spring", stiffness: 300 }}
<<<<<<< HEAD
            className="group relative bg-white/90 backdrop-blur-xl border border-indigo-200/50 rounded-2xl p-6 shadow-lg shadow-indigo-500/10 hover:shadow-xl hover:shadow-indigo-500/20 transition-all duration-300 overflow-hidden"
          >
            <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-indigo-400/20 to-transparent rounded-full blur-2xl group-hover:w-40 group-hover:h-40 transition-all duration-500" />
            <div className="relative">
              <div className="flex items-start justify-between mb-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#4f46e5] to-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-500/30 group-hover:scale-110 transition-transform duration-300">
                  <Database className="w-6 h-6 text-white" />
                </div>
                <TrendingUp className="w-4 h-4 text-[#4f46e5] opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <div>
                <p className="text-sm text-slate-500 font-medium mb-1">Active Datasets</p>
                <p className="text-4xl font-bold bg-gradient-to-r from-[#4f46e5] to-indigo-700 bg-clip-text text-transparent">1</p>
=======
            className="group relative bg-white/90 backdrop-blur-xl border border-cyan-200/50 rounded-2xl p-6 shadow-lg shadow-cyan-500/10 hover:shadow-xl hover:shadow-cyan-500/20 transition-all duration-300 overflow-hidden"
          >
            <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-cyan-400/20 to-transparent rounded-full blur-2xl group-hover:w-40 group-hover:h-40 transition-all duration-500" />
            <div className="relative">
              <div className="flex items-start justify-between mb-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-cyan-500/30 group-hover:scale-110 transition-transform duration-300">
                  <Database className="w-6 h-6 text-white" />
                </div>
                <TrendingUp className="w-4 h-4 text-cyan-600 opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <div>
                <p className="text-sm text-slate-500 font-medium mb-1">Active Datasets</p>
                <p className="text-4xl font-bold bg-gradient-to-r from-cyan-600 to-cyan-800 bg-clip-text text-transparent">1</p>
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
              </div>
            </div>
          </motion.div>

<<<<<<< HEAD
          {/* Dashboards Card */}
=======
          {/* AI Insights Card */}
          <motion.div 
            whileHover={{ y: -4, scale: 1.02 }}
            transition={{ type: "spring", stiffness: 300 }}
            className="group relative bg-white/90 backdrop-blur-xl border border-emerald-200/50 rounded-2xl p-6 shadow-lg shadow-emerald-500/10 hover:shadow-xl hover:shadow-emerald-500/20 transition-all duration-300 overflow-hidden"
          >
            <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-emerald-400/20 to-transparent rounded-full blur-2xl group-hover:w-40 group-hover:h-40 transition-all duration-500" />
            <div className="relative">
              <div className="flex items-start justify-between mb-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shadow-lg shadow-emerald-500/30 group-hover:scale-110 transition-transform duration-300">
                  <Sparkles className="w-6 h-6 text-white" />
                </div>
                <Activity className="w-4 h-4 text-emerald-600 opacity-0 group-hover:opacity-100 transition-opacity animate-pulse" />
              </div>
              <div>
                <p className="text-sm text-slate-500 font-medium mb-1">AI Insights</p>
                <p className="text-4xl font-bold bg-gradient-to-r from-emerald-600 to-emerald-800 bg-clip-text text-transparent">127</p>
              </div>
            </div>
          </motion.div>

          {/* Data Status Card */}
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
          <motion.div 
            whileHover={{ y: -4, scale: 1.02 }}
            transition={{ type: "spring", stiffness: 300 }}
            className="group relative bg-white/90 backdrop-blur-xl border border-violet-200/50 rounded-2xl p-6 shadow-lg shadow-violet-500/10 hover:shadow-xl hover:shadow-violet-500/20 transition-all duration-300 overflow-hidden"
          >
            <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-violet-400/20 to-transparent rounded-full blur-2xl group-hover:w-40 group-hover:h-40 transition-all duration-500" />
            <div className="relative">
              <div className="flex items-start justify-between mb-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center shadow-lg shadow-violet-500/30 group-hover:scale-110 transition-transform duration-300">
<<<<<<< HEAD
                  <BarChart3 className="w-6 h-6 text-white" />
                </div>
                <Activity className="w-4 h-4 text-violet-600 opacity-0 group-hover:opacity-100 transition-opacity animate-pulse" />
              </div>
              <div>
                <p className="text-sm text-slate-500 font-medium mb-1">Dashboards</p>
                <p className="text-4xl font-bold bg-gradient-to-r from-violet-600 to-violet-800 bg-clip-text text-transparent">12</p>
              </div>
            </div>
          </motion.div>

          {/* Data Status Card */}
          <motion.div 
            whileHover={{ y: -4, scale: 1.02 }}
            transition={{ type: "spring", stiffness: 300 }}
            className="group relative bg-white/90 backdrop-blur-xl border border-green-200/50 rounded-2xl p-6 shadow-lg shadow-green-500/10 hover:shadow-xl hover:shadow-green-500/20 transition-all duration-300 overflow-hidden"
          >
            <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-green-400/20 to-transparent rounded-full blur-2xl group-hover:w-40 group-hover:h-40 transition-all duration-500" />
            <div className="relative">
              <div className="flex items-start justify-between mb-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-green-500 to-green-600 flex items-center justify-center shadow-lg shadow-green-500/30 group-hover:scale-110 transition-transform duration-300">
                  <CheckCircle2 className="w-6 h-6 text-white" />
                </div>
                <div className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
=======
                  <CheckCircle2 className="w-6 h-6 text-white" />
                </div>
                <div className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
                </div>
              </div>
              <div>
                <p className="text-sm text-slate-500 font-medium mb-1">Data Status</p>
<<<<<<< HEAD
                <p className="text-4xl font-bold bg-gradient-to-r from-green-600 to-green-800 bg-clip-text text-transparent">Synced</p>
=======
                <p className="text-4xl font-bold bg-gradient-to-r from-emerald-600 to-emerald-800 bg-clip-text text-transparent">Synced</p>
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
              </div>
            </div>
          </motion.div>
        </motion.div>

        {/* Datasets Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <div className="flex items-center gap-3 mb-6">
<<<<<<< HEAD
            <h3 className="text-2xl font-bold bg-gradient-to-r from-slate-900 to-[#4f46e5] bg-clip-text text-transparent">Your Datasets</h3>
            <div className="h-px flex-1 bg-gradient-to-r from-indigo-200 via-violet-200 to-transparent" />
=======
            <h3 className="text-2xl font-bold bg-gradient-to-r from-slate-900 to-cyan-900 bg-clip-text text-transparent">Your Datasets</h3>
            <div className="h-px flex-1 bg-gradient-to-r from-cyan-200 via-emerald-200 to-transparent" />
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Connect New Database Card */}
<<<<<<< HEAD
            <Link href="/support">
              <motion.div 
                whileHover={{ scale: 1.02 }}
                transition={{ type: "spring", stiffness: 300 }}
                className="group relative p-8 rounded-2xl border-2 border-dashed border-slate-300 bg-gradient-to-br from-slate-50/50 to-white/50 backdrop-blur-sm cursor-pointer hover:border-[#4f46e5]/50 overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-indigo-100/20 via-transparent to-indigo-100/20 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                <div className="relative">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-slate-200 to-slate-300 group-hover:from-[#4f46e5]/20 group-hover:to-indigo-200 flex items-center justify-center mb-5 shadow-lg transition-all duration-300">
                    <Plus className="w-8 h-8 text-slate-500 group-hover:text-[#4f46e5] transition-colors" />
                  </div>
                  <h3 className="text-xl font-bold text-slate-600 group-hover:text-[#4f46e5] mb-3 transition-colors">
                    Connect New Database
                  </h3>
                  <p className="text-sm text-slate-500 leading-relaxed">
                    Connect your own PostgreSQL, MySQL, or other data sources
                  </p>
                </div>
              </motion.div>
            </Link>
=======
            <motion.div 
              whileHover={{ scale: 1.02 }}
              transition={{ type: "spring", stiffness: 300 }}
              className="group relative p-8 rounded-2xl border-2 border-dashed border-slate-300 bg-gradient-to-br from-slate-50/50 to-white/50 backdrop-blur-sm cursor-not-allowed overflow-hidden"
            >
              <div className="absolute top-4 right-4 z-10">
                <span className="px-3 py-1.5 text-xs font-semibold rounded-full bg-gradient-to-r from-slate-200 to-slate-300 text-slate-600 shadow-sm">
                  Coming Soon
                </span>
              </div>
              <div className="absolute inset-0 bg-gradient-to-br from-slate-100/20 via-transparent to-slate-100/20 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
              <div className="relative">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-slate-200 to-slate-300 flex items-center justify-center mb-5 shadow-lg">
                  <Plus className="w-8 h-8 text-slate-500" />
                </div>
                <h3 className="text-xl font-bold text-slate-600 mb-3">
                  Connect New Database
                </h3>
                <p className="text-sm text-slate-500 leading-relaxed">
                  Connect your own PostgreSQL, MySQL, or other data sources
                </p>
              </div>
            </motion.div>
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2

            {/* SilkRoute Dataset Card */}
            <motion.button
              onClick={() => handleDatasetSelect("silkroute")}
              whileHover={{ scale: 1.02, y: -4 }}
              whileTap={{ scale: 0.98 }}
              transition={{ type: "spring", stiffness: 300 }}
<<<<<<< HEAD
              className="w-full text-left group relative p-8 rounded-2xl border-2 border-indigo-200/60 bg-gradient-to-br from-white via-indigo-50/30 to-violet-50/30 backdrop-blur-xl hover:border-[#4f46e5]/80 hover:shadow-2xl hover:shadow-indigo-500/20 transition-all duration-300 overflow-hidden"
            >
              {/* Animated gradient background */}
              <div className="absolute inset-0 bg-gradient-to-br from-indigo-400/10 via-violet-400/10 to-purple-400/10 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
              
              {/* Glowing orb effect */}
              <div className="absolute -top-10 -right-10 w-32 h-32 bg-gradient-to-br from-[#4f46e5]/30 to-violet-400/30 rounded-full blur-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
              
              <div className="relative">
                <div className="flex items-start justify-between mb-5">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#4f46e5] to-indigo-600 border-2 border-white flex items-center justify-center shadow-xl shadow-indigo-500/30 group-hover:scale-110 transition-transform duration-300">
                    <Database className="w-8 h-8 text-white" />
                  </div>
                  <span className="px-3 py-1.5 text-xs font-semibold rounded-full bg-gradient-to-r from-green-400 to-green-500 text-white shadow-lg shadow-green-500/30">
=======
              className="w-full text-left group relative p-8 rounded-2xl border-2 border-cyan-200/60 bg-gradient-to-br from-white via-cyan-50/30 to-emerald-50/30 backdrop-blur-xl hover:border-cyan-400/80 hover:shadow-2xl hover:shadow-cyan-500/20 transition-all duration-300 overflow-hidden"
            >
              {/* Animated gradient background */}
              <div className="absolute inset-0 bg-gradient-to-br from-cyan-400/10 via-emerald-400/10 to-violet-400/10 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
              
              {/* Glowing orb effect */}
              <div className="absolute -top-10 -right-10 w-32 h-32 bg-gradient-to-br from-cyan-400/30 to-emerald-400/30 rounded-full blur-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
              
              <div className="relative">
                <div className="flex items-start justify-between mb-5">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500 to-emerald-500 border-2 border-white flex items-center justify-center shadow-xl shadow-cyan-500/30 group-hover:scale-110 transition-transform duration-300">
                    <Database className="w-8 h-8 text-white" />
                  </div>
                  <span className="px-3 py-1.5 text-xs font-semibold rounded-full bg-gradient-to-r from-emerald-400 to-emerald-500 text-white shadow-lg shadow-emerald-500/30">
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
                    Ready
                  </span>
                </div>
                
<<<<<<< HEAD
                <h3 className="text-xl font-bold text-slate-900 mb-3 group-hover:text-[#4f46e5] transition-colors duration-200 flex items-center gap-2">
                  SilkRoute
                  <svg className="w-5 h-5 text-[#4f46e5] opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all duration-200" fill="none" viewBox="0 0 24 24" stroke="currentColor">
=======
                <h3 className="text-xl font-bold text-slate-900 mb-3 group-hover:text-cyan-700 transition-colors duration-200 flex items-center gap-2">
                  SilkRoute
                  <svg className="w-5 h-5 text-cyan-600 opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all duration-200" fill="none" viewBox="0 0 24 24" stroke="currentColor">
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                  </svg>
                </h3>
                
                <p className="text-sm text-slate-600 mb-6 leading-relaxed">
                  Retail benchmark dataset with sales, customers, stores, and inventory data
                </p>
                
                <div className="flex flex-wrap gap-2">
<<<<<<< HEAD
                  <span className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gradient-to-r from-indigo-50 to-indigo-100 border border-indigo-200 text-indigo-800 shadow-sm">
                    45K+ transactions
                  </span>
                  <span className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gradient-to-r from-violet-50 to-violet-100 border border-violet-200 text-violet-800 shadow-sm">
                    2.5K customers
                  </span>
                  <span className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gradient-to-r from-purple-50 to-purple-100 border border-purple-200 text-purple-800 shadow-sm">
=======
                  <span className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gradient-to-r from-cyan-50 to-cyan-100 border border-cyan-200 text-cyan-800 shadow-sm">
                    45K+ transactions
                  </span>
                  <span className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gradient-to-r from-emerald-50 to-emerald-100 border border-emerald-200 text-emerald-800 shadow-sm">
                    2.5K customers
                  </span>
                  <span className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gradient-to-r from-violet-50 to-violet-100 border border-violet-200 text-violet-800 shadow-sm">
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
                    6 stores
                  </span>
                </div>
              </div>
            </motion.button>
          </div>
        </motion.div>
      </main>

<<<<<<< HEAD
      {/* Footer - Single Line */}
      <footer className="relative z-10 mt-20 border-t border-slate-200/60 bg-white/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-center gap-3">
            <span className="text-sm font-medium bg-gradient-to-r from-slate-700 to-[#4f46e5] bg-clip-text text-transparent">
              ContinuumAI
            </span>
            <span className="text-slate-300">•</span>
            <p className="text-xs text-slate-500">© 2026 All rights reserved</p>
=======
      {/* Footer */}
      <footer className="relative z-10 mt-20 border-t border-slate-200/60 bg-white/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-col items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-cyan-500 to-emerald-500 flex items-center justify-center shadow-sm">
                <Sparkles className="w-3 h-3 text-white" />
              </div>
              <span className="text-sm font-medium bg-gradient-to-r from-slate-700 to-cyan-700 bg-clip-text text-transparent">
                ContinuumAI
              </span>
            </div>
            <p className="text-xs text-slate-500">© 2026 ContinuumAI • Build 4.12.0</p>
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
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
