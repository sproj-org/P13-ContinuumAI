"use client";

import ProtectedRoute from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/auth-context";
import { useAppStore, WorkspaceTab } from "@/lib/store";
import { useRouter, useParams } from "next/navigation";
import { useEffect } from "react";
import { motion } from "framer-motion";
import {
  Database,
  Table2,
  Columns3,
  BarChart3,
  ArrowLeft,
  LogOut,
} from "lucide-react";

// Tab components
import { TableProfilingTab, ColumnProfilingTab, ChartBuilderTab } from "@/components/workspace";

const tabs: { id: WorkspaceTab; label: string; icon: React.ReactNode }[] = [
  { id: "table-profiling", label: "Table Profiling", icon: <Table2 className="w-4 h-4" /> },
  { id: "column-profiling", label: "Column Profiling", icon: <Columns3 className="w-4 h-4" /> },
  { id: "chart-builder", label: "Chart Builder", icon: <BarChart3 className="w-4 h-4" /> },
];

function WorkspaceContent() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const params = useParams();
  const datasetId = params.datasetId as string;

  const {
    activeTab,
    setActiveTab,
    setActiveDataset,
    selectedDatasetId,
    setSelectedDatasetId,
  } = useAppStore();

  // Set active dataset on mount
  useEffect(() => {
    if (datasetId) {
      setSelectedDatasetId(datasetId);
      setActiveDataset(datasetId);
    }
  }, [datasetId, setActiveDataset, setSelectedDatasetId]);

  const handleBack = () => {
    setActiveDataset(null);
    router.push("/dashboard");
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case "table-profiling":
        return <TableProfilingTab />;
      case "column-profiling":
        return <ColumnProfilingTab />;
      case "chart-builder":
        return <ChartBuilderTab />;
      default:
        return <TableProfilingTab />;
    }
  };

  return (
    <div className="min-h-screen bg-[#060010]">
      {/* Nav */}
      <nav className="border-b border-white/10 bg-[#060010]/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-14">
            <div className="flex items-center gap-4">
              <button
                onClick={handleBack}
                className="flex items-center gap-1 text-gray-400 hover:text-white transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-white font-medium font-[family-name:var(--font-special-gothic)]">ContinuumAi</span>
                  <span className="text-gray-600">/</span>
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-[#5237ff]" />
                    <span className="text-[#5237ff] font-medium capitalize">
                      {selectedDatasetId || datasetId}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Tabs */}
            <div className="flex items-center gap-1">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all ${
                    activeTab === tab.id
                      ? "bg-[#5237ff]/20 text-[#5237ff] border border-[#5237ff]/30"
                      : "text-gray-400 hover:text-white hover:bg-white/5"
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-4">
              <span className="text-gray-400 text-sm">{user?.username}</span>
              <button
                onClick={logout}
                className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Tab Content */}
      <motion.main
        key={activeTab}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="h-[calc(100vh-3.5rem)]"
      >
        {renderTabContent()}
      </motion.main>
    </div>
  );
}

export default function WorkspacePage() {
  return (
    <ProtectedRoute>
      <WorkspaceContent />
    </ProtectedRoute>
  );
}
