"use client";

import ProtectedRoute from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/auth-context";
import { useAppStore } from "@/lib/store";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Database, Plus, LogOut } from "lucide-react";

function DashboardContent() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const setActiveDataset = useAppStore((state) => state.setActiveDataset);

  const handleDatasetSelect = (datasetId: "silkroute") => {
    setActiveDataset(datasetId);
    router.push(`/workspace/${datasetId}`);
  };

  const capitalizedName = user?.username 
    ? user.username.charAt(0).toUpperCase() + user.username.slice(1) 
    : "there";

  return (
    <div className="min-h-screen bg-[#060010] relative">
      {/* Nav */}
      <nav className="relative z-10 border-b border-white/10 bg-[#060010]/80 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-semibold text-white font-[family-name:var(--font-special-gothic)]">
                ContinuumAi
              </h1>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-gray-400 text-sm">
                {user?.username || "User"}
              </span>
              <button
                onClick={logout}
                className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors"
              >
                <LogOut className="w-4 h-4" />
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="relative z-10 max-w-5xl mx-auto py-16 px-4 sm:px-6 lg:px-8">
        {/* Welcome Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl font-bold text-white mb-4">
            Hello, {capitalizedName}!
          </h2>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto">
            Your data has stories — let&apos;s uncover them.
          </p>
        </motion.div>

        {/* Dataset Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Connect New Database Card */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            <div className="group relative p-6 rounded-2xl border border-white/10 bg-white/5 opacity-60 cursor-not-allowed">
              <div className="absolute top-4 right-4">
                <span className="px-2 py-1 text-xs font-medium rounded-full bg-white/10 text-gray-500">
                  Coming Soon
                </span>
              </div>
              <div className="w-14 h-14 rounded-xl bg-white/5 flex items-center justify-center mb-4">
                <Plus className="w-7 h-7 text-gray-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-500 mb-2">
                Connect New Database
              </h3>
              <p className="text-sm text-gray-600">
                Connect your own PostgreSQL, MySQL, or other data sources
              </p>
            </div>
          </motion.div>

          {/* SilkRoute Dataset Card */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <button
              onClick={() => handleDatasetSelect("silkroute")}
              className="w-full text-left group relative p-6 rounded-2xl border border-white/10 bg-white/5 hover:bg-[#5237ff]/10 hover:border-[#5237ff]/50 transition-all duration-300"
            >
              <div className="absolute top-4 right-4">
                <span className="px-2 py-1 text-xs font-medium rounded-full bg-emerald-500/20 text-emerald-400">
                  Ready
                </span>
              </div>
              <div className="w-14 h-14 rounded-xl bg-[#5237ff]/20 border border-[#5237ff]/30 flex items-center justify-center mb-4 group-hover:scale-105 transition-transform">
                <Database className="w-7 h-7 text-[#5237ff]" />
              </div>
              <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-[#5237ff] transition-colors">
                SilkRoute
              </h3>
              <p className="text-sm text-gray-400 mb-4">
                Retail benchmark dataset with sales, customers, stores, and inventory data
              </p>
              <div className="flex flex-wrap gap-2">
                <span className="px-2 py-1 text-xs rounded-md bg-white/10 text-gray-300">
                  45K+ transactions
                </span>
                <span className="px-2 py-1 text-xs rounded-md bg-white/10 text-gray-300">
                  2.5K customers
                </span>
                <span className="px-2 py-1 text-xs rounded-md bg-white/10 text-gray-300">
                  6 stores
                </span>
              </div>
            </button>
          </motion.div>
        </div>
      </main>
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
