"use client";

import ProtectedRoute from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/auth-context";
import { useAppStore, WorkspaceTab } from "@/lib/store";
import { useAggregations } from "@/lib/hooks";
import { useChatSync } from "@/lib/useChatSync";
import Link from "next/link";
import { useRouter, useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Database,
  BarChart3,
  LayoutGrid,
  ArrowLeft,
  Sparkles,
} from "lucide-react";

// Tab components
import { MartsTab, ChartBuilderTab, DashboardTab, NumiChatbot } from "@/components/workspace";

const tabs: { id: WorkspaceTab; label: string; icon: React.ReactNode }[] = [
  { id: "marts", label: "Profiling", icon: <Database className="w-4 h-4" /> },
  { id: "chart-builder", label: "Chart Builder", icon: <BarChart3 className="w-4 h-4" /> },
  { id: "dashboard", label: "Dashboard", icon: <LayoutGrid className="w-4 h-4" /> },
];

function WorkspaceContent() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const params = useParams();
  const datasetId = params.datasetId as string;
  const [isNumiOpen, setIsNumiOpen] = useState(false);

  const {
    activeTab,
    setActiveTab,
    setActiveDataset,
    selectedDatasetId,
    setSelectedDatasetId,
    selectedAggregation,
    setSelectedAggregation,
    availableMarts,
    setAvailableMarts,
  } = useAppStore();
  const { data: aggregationsData } = useAggregations(selectedDatasetId);

  // Bidirectional sync: hydrate chat state from DB + debounced write-back
  useChatSync();

  // Set active dataset on mount
  useEffect(() => {
    if (datasetId) {
      setSelectedDatasetId(datasetId);
      setActiveDataset(datasetId);
    }
  }, [datasetId, setActiveDataset, setSelectedDatasetId]);

  useEffect(() => {
    const marts = (aggregationsData?.aggregations ?? []).map((item) => ({
      id: item.table_name,
      label: item.label,
      description: item.description,
    }));
    setAvailableMarts(marts);
  }, [aggregationsData, setAvailableMarts]);

  useEffect(() => {
    if (availableMarts.length === 0) {
      if (selectedAggregation !== null) {
        setSelectedAggregation(null);
      }
      return;
    }

    const selectionStillValid = selectedAggregation
      ? availableMarts.some((item) => item.id === selectedAggregation)
      : false;

    if (!selectionStillValid) {
      setSelectedAggregation(availableMarts[0].id);
    }
  }, [availableMarts, selectedAggregation, setSelectedAggregation]);

  const handleBack = () => {
    setActiveDataset(null);
    router.push("/dashboard");
  };

  // Trigger window resize when Numi opens/closes to make charts resize properly
  useEffect(() => {
    window.dispatchEvent(new Event('resize'));
  }, [isNumiOpen]);

  const renderTabContent = () => {
    switch (activeTab) {
      case "marts":
        return <MartsTab />;
      case "chart-builder":
        return <ChartBuilderTab />;
      case "dashboard":
        return <DashboardTab />;
      default:
        return <MartsTab />;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/20 to-violet-50/30 relative">
      {/* Nav */}
      <nav className="border-b border-indigo-100 bg-gradient-to-r from-white via-indigo-50/30 to-violet-50/20 backdrop-blur-sm sticky top-0 z-50 shadow-sm">
        <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-14">
            <div className="flex items-center gap-4">
              <button
                onClick={handleBack}
                className="flex items-center gap-1 text-slate-600 hover:text-[#4f46e5] transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <Link href="/dashboard" className="text-slate-900 font-medium font-[family-name:var(--font-special-gothic)] hover:text-[#4f46e5] transition-colors">ContinuumAi</Link>
                  <span className="text-slate-300">/</span>
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-[#4f46e5]" />
                    <span className="text-[#4f46e5] font-medium capitalize">
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
                      ? "bg-gradient-to-r from-indigo-100 to-violet-100 text-[#4f46e5] border border-indigo-200 shadow-sm"
                      : "text-slate-600 hover:text-[#4f46e5] hover:bg-indigo-50/50"
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-4">
              <button
                onClick={() => setIsNumiOpen(!isNumiOpen)}
                className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-gradient-to-r from-[#4f46e5] to-indigo-600 rounded-lg hover:from-indigo-600 hover:to-indigo-700 transition-all shadow-md hover:shadow-lg"
              >
                <Sparkles className="w-4 h-4" />
                <span>Ask Numi</span>
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
        className={`h-[calc(100vh-3.5rem)] transition-all duration-100 ${
          isNumiOpen ? "mr-96" : "mr-0"
        }`}
      >
        {renderTabContent()}
      </motion.main>

      {/* Numi Chatbot Sidebar */}
      <NumiChatbot isOpen={isNumiOpen} onClose={() => setIsNumiOpen(false)} />
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
