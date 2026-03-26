"use client";

import React, { useState, useEffect, useMemo, useRef, FormEvent } from "react";
import { useParams } from "next/navigation";
import {
  X,
  Sparkles,
  Send,
  Loader2,
  ChevronDown,
  Search,
  Check,
  Trash2,
  BookmarkPlus,
  AlertTriangle,
  ChevronRight,
  Save,
  BarChart3,
  Edit3,
} from "lucide-react";
import { useAppStore } from "@/lib/store";
import { useToast } from "@/lib/toast-context";
import { apiClient } from "@/lib/api";
import { applyChartSpecPatch } from "@/lib/chart-spec-patch";
import type {
  ChatRequest,
  ChatResponse,
  ChatClarifyResponse,
  ChatChartResponse,
  ChatFocusContext,
  ChatHintsResponse,
  ChatHistoryTurn,
  QuerySpec,
  ChatStatePayload,
} from "@/lib/types/chat";
import DecisionIntelligencePanel from "@/components/workspace/DecisionIntelligencePanel";
import { buildAnalysisFocusContext, buildChartFocusContext, contextualPromptSuggestions } from "@/lib/contextual-focus";
import { renderChart } from "@/components/workspace/renderChart";
import MarkdownMessage from "@/components/common/MarkdownMessage";
import { useSavedCharts, useStrategyKpis } from "@/lib/hooks";
import { attachChartSemanticContext, resolveChartTitle } from "@/lib/chart-display";
import { createChartBuilderSeed } from "@/lib/chart-builder-seed";
import { getMartDrillAdvisory } from "@/lib/mart-drill-utils";

interface VizAgentChatbotProps {
  isOpen: boolean;
  onClose: () => void;
}

// Helper: extract readable text from assistant response
function assistantText(res: ChatResponse): string {
  if (res.response_type === "chart") {
    return res.narrative;
  }
  if (res.response_type === "chart_patch") {
    return res.narrative ?? "Applied a chart update request.";
  }
  if (res.response_type === "clarify") {
    return res.question || "Could you clarify your request?";
  }
  if (res.response_type === "refuse") {
    return res.message;
  }
  return res.message;
}

// Helper: normalize clarify stage
function normalizeStage(s: string | undefined): "metric" | "x_axis" | "time_grain" | null {
  if (!s) return null;
  const lower = s.toLowerCase();
  if (lower.includes("metric")) return "metric";
  if (lower.includes("dimension") || lower.includes("temporal") || lower.includes("x_axis")) return "x_axis";
  if (lower.includes("time_grain") || lower.includes("grain")) return "time_grain";
  return null;
}

function querySpecLabel(spec: QuerySpec | null | undefined): string[] {
  if (!spec) {
    return [];
  }

  const labels: string[] = [];
  if (spec.chart_type) {
    labels.push(`Chart: ${spec.chart_type}`);
  }
  if (spec.aggregation && spec.measures[0]) {
    labels.push(`Metric: ${spec.aggregation}(${spec.measures[0]})`);
  } else if (spec.measures[0]) {
    labels.push(`Metric: ${spec.measures[0]}`);
  }
  if (spec.time_field) {
    labels.push(`Time: ${spec.time_field}${spec.time_grain ? ` (${spec.time_grain})` : ""}`);
  } else if (spec.dimensions[0]) {
    labels.push(`Group by: ${spec.dimensions[0]}`);
  }
  if (spec.filters.length > 0) {
    labels.push(`Filters: ${spec.filters.length}`);
  }
  return labels;
}

// Helper: build request state
function toRequestState(
  lastChartSpec: ChatStatePayload["last_chart_spec"] | null,
  baseState: {
    clarify_id: string | null;
    original_user_intent: string | null;
    selections: {
      metric: string | null;
      dimension: string | null;
      temporal: string | null;
      time_grain: "day" | "week" | "month" | "quarter" | "year" | null;
      aggregation: "sum" | "avg" | "count" | "min" | "max" | null;
      limit: number | null;
    };
  }
): ChatStatePayload | undefined {
  const selections: NonNullable<ChatStatePayload["selections"]> = {};
  if (baseState.selections.metric) selections.metric = baseState.selections.metric;
  if (baseState.selections.dimension) selections.dimension = baseState.selections.dimension;
  if (baseState.selections.temporal) selections.temporal = baseState.selections.temporal;
  if (baseState.selections.time_grain) selections.time_grain = baseState.selections.time_grain;
  if (baseState.selections.aggregation) selections.aggregation = baseState.selections.aggregation;
  if (typeof baseState.selections.limit === "number") selections.limit = baseState.selections.limit;

  const payload: ChatStatePayload = {};
  if (lastChartSpec) {
    payload.last_chart_spec = lastChartSpec;
  }
  if (baseState.clarify_id) {
    payload.clarify_id = baseState.clarify_id;
  }
  if (Object.keys(selections).length > 0) {
    payload.selections = selections;
  }
  if (baseState.original_user_intent) {
    payload.original_user_intent = baseState.original_user_intent;
  }
  return Object.keys(payload).length > 0 ? payload : undefined;
}

const modeOptions = [
  { id: "auto", label: "Auto" },
  { id: "chart", label: "Chart" },
  { id: "explain", label: "Explain" },
] as const;

const EMPTY_SELECTIONS = {
  metric: null,
  dimension: null,
  temporal: null,
  time_grain: null,
  aggregation: null,
  limit: null,
} as const;

type ChartPreviewState = {
  chartSpec: ChatChartResponse["chart_spec"];
  rows: ChatChartResponse["rows"];
  title: string;
  analysis?: ChatChartResponse["analysis"];
};

export function VizAgentChatbot({ isOpen, onClose }: VizAgentChatbotProps) {
  const params = useParams<{ datasetId: string }>();
  const {
    selectedDatasetId,
    selectedAggregation,
    setSelectedAggregation,
    availableMarts,
    chatMode,
    setChatMode,
    chatTurnsByKey,
    lastChartSpecByKey,
    chatStateByKey,
    savedPromptsByKey,
    appendChatTurn,
    clearChat,
    setLastChartSpec,
    patchChatState,
    addSavedPrompt,
    removeSavedPrompt,
    clearSavedPrompts,
    saveChart,
    setActiveTab,
    setChartConfig,
    setChartBuilderSeed,
  } = useAppStore();

  const { showToast } = useToast();

  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chatHints, setChatHints] = useState<ChatHintsResponse | null>(null);
  const [isMartOpen, setIsMartOpen] = useState(false);
  const [martQuery, setMartQuery] = useState("");
  const [showSavedPrompts, setShowSavedPrompts] = useState(false);
  const [currentChartPreview, setCurrentChartPreview] = useState<ChartPreviewState | null>(null);
  const [selectedDashboardOption, setSelectedDashboardOption] = useState<string>("Default");
  const [newDashboardName, setNewDashboardName] = useState<string>("");
  const martPickerRef = useRef<HTMLDivElement | null>(null);
  const routeDatasetId = params?.datasetId || selectedDatasetId;

  const chatKey = useMemo(
    () => (selectedAggregation ? `${routeDatasetId}:${selectedAggregation}` : null),
    [routeDatasetId, selectedAggregation]
  );
  const turns = useMemo(() => (chatKey ? chatTurnsByKey[chatKey] ?? [] : []), [chatKey, chatTurnsByKey]);
  const { data: savedCharts } = useSavedCharts(routeDatasetId);
  const { data: strategyKpiLibrary } = useStrategyKpis(routeDatasetId);
  const lastChartSpec = chatKey ? lastChartSpecByKey[chatKey] ?? null : null;
  const chatState = chatKey ? chatStateByKey[chatKey] : undefined;
  const savedPrompts = chatKey ? savedPromptsByKey[chatKey] ?? [] : [];
  const currentChartPreviewTitle = useMemo(
    () =>
      currentChartPreview
        ? resolveChartTitle({
            chartSpec: currentChartPreview.chartSpec,
            preferredTitle: currentChartPreview.title,
            strategyKpis: strategyKpiLibrary?.kpis ?? [],
          })
        : "",
    [currentChartPreview, strategyKpiLibrary?.kpis],
  );
  const activeFocus = useMemo<ChatFocusContext | null>(() => {
    const analysisTask = currentChartPreview?.analysis?.task_type;
    const isDecisionTask =
      analysisTask === "forecast" ||
      analysisTask === "anomaly" ||
      analysisTask === "segment" ||
      analysisTask === "strategy_risk";
    if (currentChartPreview?.analysis && isDecisionTask) {
      return buildAnalysisFocusContext({
        title: currentChartPreviewTitle || currentChartPreview.title,
        table: currentChartPreview.chartSpec.table,
        kpiId: currentChartPreview.chartSpec.semantic_context?.matched_kpi_id ?? null,
        chartSpec: currentChartPreview.chartSpec,
        chartRows: currentChartPreview.rows,
        analysisContext: currentChartPreview.chartSpec.semantic_context?.analysis_context ?? null,
        semanticContext: currentChartPreview.chartSpec.semantic_context ?? null,
        analysis: currentChartPreview.analysis,
        task: analysisTask,
        breadcrumbs: ["VizAgent", selectedAggregation ?? "mart"],
      });
    }
    if (currentChartPreview) {
      return buildChartFocusContext({
        title: currentChartPreviewTitle || currentChartPreview.title,
        table: currentChartPreview.chartSpec.table,
        kpiId: currentChartPreview.chartSpec.semantic_context?.matched_kpi_id ?? null,
        chartSpec: currentChartPreview.chartSpec,
        chartRows: currentChartPreview.rows,
        analysisContext: currentChartPreview.chartSpec.semantic_context?.analysis_context ?? null,
        semanticContext: currentChartPreview.chartSpec.semantic_context ?? null,
        breadcrumbs: ["VizAgent", selectedAggregation ?? "mart"],
      });
    }
    if (lastChartSpec) {
      return buildChartFocusContext({
        title: "Current VizAgent chart",
        table: lastChartSpec.table,
        kpiId: lastChartSpec.semantic_context?.matched_kpi_id ?? null,
        chartSpec: lastChartSpec,
        chartRows: [],
        analysisContext: lastChartSpec.semantic_context?.analysis_context ?? null,
        semanticContext: lastChartSpec.semantic_context ?? null,
        breadcrumbs: ["VizAgent", selectedAggregation ?? "mart"],
      });
    }
    return null;
  }, [currentChartPreview, currentChartPreviewTitle, lastChartSpec, selectedAggregation]);
  const focusSuggestions = useMemo(
    () => (activeFocus ? contextualPromptSuggestions(activeFocus) : []),
    [activeFocus],
  );
  const selectedMart = useMemo(
    () => availableMarts.find((mart) => mart.id === selectedAggregation) ?? null,
    [availableMarts, selectedAggregation]
  );
  const filteredMarts = useMemo(() => {
    const query = martQuery.trim().toLowerCase();
    if (!query) {
      return availableMarts;
    }
    return availableMarts.filter((mart) => {
      const label = (mart.label ?? "").toLowerCase();
      const id = mart.id.toLowerCase();
      const description = (mart.description ?? "").toLowerCase();
      return label.includes(query) || id.includes(query) || description.includes(query);
    });
  }, [availableMarts, martQuery]);
  const dashboardOptions = useMemo(() => {
    const base = new Set<string>(["Default"]);
    for (const chart of savedCharts ?? []) {
      const name = chart.dashboard_name?.trim();
      if (name) {
        base.add(name);
      }
    }
    return Array.from(base).sort((a, b) => a.localeCompare(b));
  }, [savedCharts]);
  const firstUserIntent = useMemo(
    () => turns.find((turn) => turn.role === "user")?.message ?? null,
    [turns]
  );
  const latestAssistantResponse = useMemo(() => {
    for (let index = turns.length - 1; index >= 0; index -= 1) {
      const turn = turns[index];
      if (turn.role === "assistant" && turn.response) {
        return turn.response;
      }
    }
    return null;
  }, [turns]);
  const latestQuerySpec = useMemo(
    () => latestAssistantResponse?.query_spec ?? null,
    [latestAssistantResponse],
  );
  const contextTags = useMemo(() => querySpecLabel(latestQuerySpec), [latestQuerySpec]);
  const debugFlagsPresent = useMemo(() => {
    if (!latestAssistantResponse) {
      return false;
    }
    return (
      typeof latestAssistantResponse.used_fallback === "boolean" ||
      typeof latestAssistantResponse.openai_configured === "boolean" ||
      latestAssistantResponse.fallback_reason === "missing_key" ||
      latestAssistantResponse.fallback_reason === "openai_error"
    );
  }, [latestAssistantResponse]);
  const fallbackWarningText = useMemo(() => {
    if (!latestAssistantResponse) {
      return null;
    }

    if (
      latestAssistantResponse.openai_configured === false ||
      latestAssistantResponse.fallback_reason === "missing_key"
    ) {
      return "⚠️ VizAgent fallback: OPENAI_API_KEY not detected. Check backend/.env";
    }

    if (
      latestAssistantResponse.used_fallback === true &&
      latestAssistantResponse.fallback_reason === "openai_error"
    ) {
      const hint =
        typeof latestAssistantResponse.openai_error_hint === "string" && latestAssistantResponse.openai_error_hint.trim()
          ? latestAssistantResponse.openai_error_hint.trim()
          : "OpenAI call failed";
      const isSchemaMismatch = hint.toLowerCase().startsWith("schema mismatch:");
      const statusCode =
        typeof latestAssistantResponse.openai_status_code === "number"
          ? latestAssistantResponse.openai_status_code
          : null;
      if (isSchemaMismatch) {
        return `⚠️ VizAgent fallback: OpenAI response did not match the expected schema${statusCode !== null ? ` (${statusCode})` : ""}`;
      }
      return `⚠️ VizAgent fallback: OpenAI call failed. ${hint}${statusCode !== null ? ` (${statusCode})` : ""}`;
    }

    return null;
  }, [latestAssistantResponse]);
  const fallbackWarningDetails = useMemo(() => {
    if (!latestAssistantResponse || latestAssistantResponse.fallback_reason !== "openai_error") {
      return null;
    }
    const type =
      typeof latestAssistantResponse.openai_error_type === "string" && latestAssistantResponse.openai_error_type.trim()
        ? latestAssistantResponse.openai_error_type.trim()
        : "unknown";
    const status =
      typeof latestAssistantResponse.openai_status_code === "number"
        ? String(latestAssistantResponse.openai_status_code)
        : "n/a";
    const hint =
      typeof latestAssistantResponse.openai_error_hint === "string" && latestAssistantResponse.openai_error_hint.trim()
        ? latestAssistantResponse.openai_error_hint.trim()
        : null;
    return `${hint ? `${hint} • ` : ""}Type: ${type} • Status: ${status}`;
  }, [latestAssistantResponse]);
  const showMissingDebugFlags = useMemo(() => {
    return Boolean(latestAssistantResponse && !debugFlagsPresent);
  }, [latestAssistantResponse, debugFlagsPresent]);
  const chartPreviewAdvisory = useMemo(() => {
    if (!currentChartPreview) {
      return null;
    }

    const previewSpec = currentChartPreview.chartSpec;
    const xField = previewSpec?.encoding?.x?.field ?? null;
    const martId = typeof previewSpec?.table === "string" ? previewSpec.table : selectedAggregation;

    return getMartDrillAdvisory({
      xField,
      martId,
      availableMarts,
    });
  }, [currentChartPreview, selectedAggregation, availableMarts]);
  const martSummary = useMemo(() => {
    if (!selectedMart) {
      return null;
    }
    return selectedMart.description?.trim() || `Working in mart ${selectedMart.id}.`;
  }, [selectedMart]);

  useEffect(() => {
    setError(null);
    setMessage("");
  }, [chatKey]);

  useEffect(() => {
    if (!isMartOpen) {
      return;
    }
    const handleClickOutside = (event: MouseEvent) => {
      if (!martPickerRef.current) {
        return;
      }
      if (!martPickerRef.current.contains(event.target as Node)) {
        setIsMartOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isMartOpen]);

  useEffect(() => {
    let isActive = true;
    if (!selectedAggregation) {
      setChatHints(null);
      return () => {
        isActive = false;
      };
    }

    apiClient
      .getChatHints(routeDatasetId, selectedAggregation)
      .then((hints) => {
        if (isActive) {
          setChatHints(hints);
        }
      })
      .catch(() => {
        if (isActive) {
          setChatHints(null);
        }
      });

    return () => {
      isActive = false;
    };
  }, [routeDatasetId, selectedAggregation]);

  const placeholder = useMemo(() => {
    if (!selectedAggregation) {
      return "Select a mart to start...";
    }
    if (activeFocus) {
      return `Ask about ${activeFocus.title || "the current artifact"}...`;
    }
    if (chatMode === "chart") {
      return "Request a chart...";
    }
    if (chatMode === "explain") {
      return "Ask for an explanation...";
    }
    return "Ask a business question...";
  }, [activeFocus, chatMode, selectedAggregation]);

  const guidance = useMemo(() => {
    if (!selectedAggregation) {
      return {
        title: "Select a mart first",
        examples: [] as string[],
      };
    }

    const examples = chatHints?.example_prompts?.[chatMode] ?? [];
    return {
      title: chatMode === "chart" ? "Chart Mode" : chatMode === "explain" ? "Explain Mode" : "Auto Mode",
      examples,
    };
  }, [chatHints, chatMode, selectedAggregation]);

  const applyResponseState = (
    key: string,
    response: ChatResponse,
    originalIntent: string
  ) => {
    if (response.response_type === "chart") {
      setLastChartSpec(key, response.chart_spec);
      patchChatState(key, {
        clarify_id: null,
        original_user_intent: originalIntent,
        selections: EMPTY_SELECTIONS,
      });
      return;
    }

    if (response.response_type === "clarify") {
      patchChatState(key, {
        clarify_id: response.clarify_id,
        original_user_intent: originalIntent,
      });
      return;
    }

    patchChatState(key, {
      clarify_id: null,
      original_user_intent: originalIntent,
    });
  };

  const buildHistory = (items: typeof turns, nextMessage: string): ChatHistoryTurn[] => {
    const history = items
      .slice(-7)
      .map((turn) => ({
        role: turn.role,
        message: turn.message,
        response_type: turn.response?.response_type ?? null,
      }));
    return [...history, { role: "user", message: nextMessage }];
  };

  const sendChatRequest = async ({
    userVisibleMessage,
    requestMessage,
    state,
  }: {
    userVisibleMessage: string;
    requestMessage: string;
    state: ChatStatePayload | undefined;
  }) => {
    if (!selectedAggregation || !chatKey) {
      setError("Select a mart first");
      return;
    }

    appendChatTurn(chatKey, {
      role: "user",
      message: userVisibleMessage,
      createdAt: new Date().toISOString(),
    });
    setMessage("");
    setError(null);
    setIsLoading(true);
    try {
      const request: ChatRequest = {
        message: requestMessage,
        table: selectedAggregation,
        mode: chatMode,
        state,
        history: buildHistory(turns, requestMessage),
        focus: activeFocus,
      };
      const response = await apiClient.postChat(routeDatasetId, request);
      appendChatTurn(chatKey, {
        role: "assistant",
        message: assistantText(response),
        response,
        createdAt: new Date().toISOString(),
      });
      applyResponseState(chatKey, response, state?.original_user_intent ?? requestMessage);
      
      // Update chart preview if response is a chart
      if (response.response_type === "chart" && response.chart_spec && response.rows) {
        setCurrentChartPreview({
          chartSpec: response.chart_spec,
          rows: response.rows,
          title: response.narrative || requestMessage,
          analysis: response.analysis ?? null,
        });
      } else if (response.response_type === "chart_patch" && activeFocus?.chart_spec) {
        const patchedChartSpec = applyChartSpecPatch(activeFocus.chart_spec, response.patch);
        setLastChartSpec(chatKey, patchedChartSpec);
        setCurrentChartPreview((current) =>
          current
            ? {
                ...current,
                chartSpec: patchedChartSpec,
              }
            : {
                chartSpec: patchedChartSpec,
                rows: [],
                title: requestMessage,
                analysis: response.analysis ?? null,
              },
        );
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Chat request failed");
    } finally {
      setIsLoading(false);
    }
  };

  const submitPrompt = async (prompt: string) => {
    const trimmed = prompt.trim();
    if (!trimmed || !chatKey) {
      return;
    }

    const originalIntent = trimmed;
    patchChatState(chatKey, {
      clarify_id: null,
      selections: EMPTY_SELECTIONS,
      original_user_intent: originalIntent,
    });
    const requestState = toRequestState(lastChartSpec, {
      clarify_id: null,
      original_user_intent: originalIntent,
      selections: EMPTY_SELECTIONS,
    });
    await sendChatRequest({
      userVisibleMessage: trimmed,
      requestMessage: trimmed,
      state: requestState,
    });
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) return;
    setMessage("");
    await submitPrompt(trimmed);
  };

  const handleSavePrompt = () => {
    if (!chatKey) {
      setError("Select a mart first");
      return;
    }
    const trimmed = message.trim();
    if (!trimmed) {
      return;
    }
    addSavedPrompt(chatKey, trimmed);
  };

  const handleClarifyChip = async (
    clarifyResponse: ChatClarifyResponse,
    prefix: "metric" | "dimension" | "temporal" | "time_grain",
    value: string
  ) => {
    if (!chatKey || !selectedAggregation) {
      setError("Select a mart first");
      return;
    }
    const current = chatState ?? {
      clarify_id: null,
      selections: EMPTY_SELECTIONS,
      original_user_intent: null,
    };
    const mergedSelections = {
      ...current.selections,
      [prefix]: value,
    };
    const originalIntent = current.original_user_intent ?? firstUserIntent ?? clarifyResponse.question;
    patchChatState(chatKey, {
      clarify_id: clarifyResponse.clarify_id,
      selections: mergedSelections,
      original_user_intent: originalIntent,
    });
    const requestState = toRequestState(lastChartSpec, {
      clarify_id: clarifyResponse.clarify_id,
      original_user_intent: originalIntent,
      selections: mergedSelections,
    });
    await sendChatRequest({
      userVisibleMessage: `Selected ${prefix}: ${value}`,
      requestMessage: originalIntent,
      state: requestState,
    });
  };

  const canSend = Boolean(selectedAggregation && chatKey && !isLoading);
  const canSave = Boolean(selectedAggregation && chatKey && message.trim() && !isLoading);

  const handleSaveChartToDashboard = () => {
    if (!currentChartPreview || !selectedAggregation) return;

    const resolvedDashboardName =
      selectedDashboardOption === "__new__"
        ? newDashboardName.trim()
        : selectedDashboardOption.trim();
    if (!resolvedDashboardName) {
      showToast("Please select or enter a dashboard name.", "error");
      return;
    }
    
    const chartSpecWithSemanticContext = attachChartSemanticContext(currentChartPreview.chartSpec, {
      strategyKpis: strategyKpiLibrary?.kpis ?? [],
    });

    saveChart({
      title: currentChartPreviewTitle,
      dashboardName: resolvedDashboardName,
      chartSpec: chartSpecWithSemanticContext,
      rows: currentChartPreview.rows,
      datasetId: routeDatasetId,
      martId: selectedAggregation,
    });
    
    // Show success feedback
    showToast(`Chart "${currentChartPreviewTitle}" saved to "${resolvedDashboardName}" dashboard!`, "success");
    setCurrentChartPreview(null);
  };

  const handleEditInChartBuilder = () => {
    if (!currentChartPreview) return;
    
    const chartSpec = currentChartPreview.chartSpec;
    
    // Convert ChartSpecV1 to ChartConfig for the chart builder
    setChartConfig({
      chartType: chartSpec.chart.type,
      xAxis: chartSpec.encoding.x.field,
      yAxis: chartSpec.encoding.y[0]?.field || null,
      aggregationFn: chartSpec.encoding.y[0]?.aggregation || 'sum',
      colorBy: null, // ChartSpecV1 doesn't have colorBy, but we'll let user add it
    });
    setChartBuilderSeed(createChartBuilderSeed(chartSpec));

    if (chartPreviewAdvisory) {
      showToast(chartPreviewAdvisory, "warning", 5000);
    }
    
    // Switch to chart builder tab
    setActiveTab('chart-builder');
    
    // Close the chart preview
    setCurrentChartPreview(null);
  };

  return (
    <>
      {/* Chart Preview Panel - Left Side */}
      {currentChartPreview && isOpen && (
        <div className="fixed right-96 top-0 h-full w-[600px] bg-white border-l border-r border-slate-200 shadow-xl z-40 flex flex-col animate-in slide-in-from-right-full duration-300">
          {/* Chart Preview Header */}
          <div className="flex items-center justify-between p-4 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-indigo-50/30">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#4f46e5] to-indigo-600 flex items-center justify-center shadow-lg">
                <BarChart3 className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-900">Chart Preview</h3>
                <p className="text-xs text-slate-600">Ready to save to dashboard</p>
              </div>
            </div>
            <button
              onClick={() => setCurrentChartPreview(null)}
              className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-slate-600" />
            </button>
          </div>

          {/* Chart Content */}
          <div className="flex-1 overflow-y-auto p-8 flex items-center justify-center bg-gradient-to-br from-slate-50/50 via-indigo-50/30 to-violet-50/20">
            <div className="w-full max-w-5xl">
              <div className="bg-white rounded-3xl shadow-2xl border border-indigo-100/50 overflow-hidden">
                {/* Chart Title Section */}
                <div className="px-8 pt-8 pb-4 bg-gradient-to-r from-white to-indigo-50/30">
                  <h4 className="text-xl font-bold text-slate-900 text-center line-clamp-2">
                    {currentChartPreviewTitle}
                  </h4>
                </div>
                
                {/* Chart Display Area */}
                <div className="px-8 pb-8">
                  <div className="h-[520px] bg-gradient-to-br from-slate-50/30 to-white rounded-2xl p-8 border border-slate-200/50">
                    {renderChart(currentChartPreview.chartSpec, currentChartPreview.rows)}
                  </div>
                  <div className="mt-6">
                    <DecisionIntelligencePanel
                      key={`viz-agent-${currentChartPreview.chartSpec.table}-${currentChartPreview.chartSpec.encoding.x.field}-${currentChartPreview.chartSpec.encoding.y[0]?.field ?? "metric"}-${currentChartPreview.chartSpec.semantic_context?.matched_kpi_id ?? "none"}`}
                      datasetId={routeDatasetId}
                      martId={selectedAggregation}
                      chartSpec={currentChartPreview.chartSpec}
                      chartRows={currentChartPreview.rows}
                      chartTitle={currentChartPreviewTitle}
                      kpiId={currentChartPreview.chartSpec.semantic_context?.matched_kpi_id ?? null}
                      analysisSource="viz_agent"
                      onChartSpecChange={(nextChartSpec) => {
                        setCurrentChartPreview((current) =>
                          current ? { ...current, chartSpec: nextChartSpec } : current,
                        );
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Chart Actions */}
          <div className="border-t border-slate-200 p-6 bg-gradient-to-r from-slate-50 to-white">
            {chartPreviewAdvisory ? (
              <div className="mb-4 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-xs text-violet-800">
                {chartPreviewAdvisory}
              </div>
            ) : null}
            <div className="mb-4 space-y-2">
              <label className="text-xs font-medium text-slate-700">Target Dashboard</label>
              <select
                value={selectedDashboardOption}
                onChange={(event) => setSelectedDashboardOption(event.target.value)}
                className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50"
              >
                {dashboardOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
                <option value="__new__">+ Create new dashboard</option>
              </select>
              {selectedDashboardOption === "__new__" ? (
                <input
                  type="text"
                  value={newDashboardName}
                  onChange={(event) => setNewDashboardName(event.target.value)}
                  placeholder="Enter new dashboard name"
                  className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50"
                />
              ) : null}
            </div>
            <div className="grid grid-cols-3 gap-3">
              <button
                onClick={handleEditInChartBuilder}
                className="flex flex-col items-center gap-2 px-4 py-4 bg-white border-2 border-indigo-200 text-indigo-700 rounded-xl hover:border-indigo-300 hover:bg-indigo-50 transition-all shadow-sm hover:shadow-md font-medium group"
              >
                <Edit3 className="w-5 h-5 group-hover:scale-110 transition-transform" />
                <span className="text-xs">Edit in Builder</span>
              </button>
              <button
                onClick={handleSaveChartToDashboard}
                className="flex flex-col items-center gap-2 px-4 py-4 bg-gradient-to-br from-[#4f46e5] to-indigo-600 text-white rounded-xl hover:from-indigo-600 hover:to-indigo-700 transition-all shadow-md hover:shadow-lg font-medium group"
              >
                <Save className="w-5 h-5 group-hover:scale-110 transition-transform" />
                <span className="text-xs">Save</span>
              </button>
              <button
                onClick={() => setCurrentChartPreview(null)}
                className="flex flex-col items-center gap-2 px-4 py-4 bg-white border-2 border-slate-200 text-slate-600 rounded-xl hover:border-slate-300 hover:bg-slate-50 transition-all shadow-sm hover:shadow-md font-medium group"
              >
                <X className="w-5 h-5 group-hover:scale-110 transition-transform" />
                <span className="text-xs">Dismiss</span>
              </button>
            </div>
            <p className="text-xs text-slate-500 mt-3 text-center">
              Edit, save to dashboard, or dismiss this chart
            </p>
          </div>
        </div>
      )}

      {/* Chat Sidebar - Right Side */}
      <div
        className={`fixed right-0 top-0 h-full w-96 bg-gradient-to-br from-white via-indigo-50/30 to-violet-50/40 border-l border-indigo-200/50 shadow-2xl transform transition-transform duration-300 ease-in-out z-50 flex flex-col ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-indigo-200/50 bg-white/80 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <div className="relative">
            <Sparkles className="w-5 h-5 text-[#4f46e5]" />
            <div className="absolute -top-1 -right-1 w-2 h-2 bg-indigo-500 rounded-full animate-pulse" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">VizAgent</h3>
            <p className="text-[10px] text-slate-600">AI Data Assistant</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => chatKey && clearChat(chatKey)}
            disabled={!chatKey || turns.length === 0}
            className="p-1.5 text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            title="Clear chat"
          >
            <Trash2 className="w-4 h-4" />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Mart Selector */}
      <div className="p-3 border-b border-indigo-200/50 bg-white/60 backdrop-blur-sm space-y-2">
        <div className="relative" ref={martPickerRef}>
          <button
            type="button"
            onClick={() => setIsMartOpen((open) => !open)}
            className="w-full flex items-center justify-between gap-2 bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#4f46e5]/50 shadow-sm"
          >
            <span className="truncate">
              {selectedMart?.label ?? selectedMart?.id ?? "Select mart"}
            </span>
            <ChevronDown className={`w-4 h-4 transition-transform ${isMartOpen ? "rotate-180" : ""}`} />
          </button>
          {isMartOpen ? (
            <div className="absolute z-50 mt-2 w-full rounded-xl border border-indigo-200 bg-white/95 backdrop-blur-xl shadow-xl">
              <div className="p-2">
                <div className="flex items-center gap-2 rounded-lg border border-slate-300 bg-slate-50 px-2 py-1.5">
                  <Search className="w-3.5 h-3.5 text-slate-400" />
                  <input
                    value={martQuery}
                    onChange={(event) => setMartQuery(event.target.value)}
                    placeholder="Search marts..."
                    className="w-full bg-transparent text-xs text-slate-900 placeholder:text-slate-500 focus:outline-none"
                  />
                </div>
              </div>
              <div className="max-h-48 overflow-y-auto p-2 pt-0 space-y-1">
                {filteredMarts.length === 0 ? (
                  <div className="px-3 py-2 text-[11px] text-slate-500">No marts available.</div>
                ) : (
                  filteredMarts.map((mart) => {
                    const isSelected = mart.id === selectedAggregation;
                    return (
                      <button
                        key={mart.id}
                        type="button"
                        onClick={() => {
                          setSelectedAggregation(mart.id);
                          setIsMartOpen(false);
                          setMartQuery("");
                        }}
                        className={`w-full text-left rounded-lg border px-2 py-1.5 transition-colors ${
                          isSelected
                            ? "border-indigo-300 bg-indigo-100 shadow-sm"
                            : "border-slate-200 bg-white hover:bg-slate-50"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <p className="text-xs text-slate-900 font-semibold truncate flex-1">
                            {mart.label ?? mart.id}
                          </p>
                          {isSelected ? <Check className="w-3.5 h-3.5 text-[#4f46e5]" /> : null}
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          ) : null}
        </div>

        {/* Mode Selector */}
        <div className="inline-flex rounded-lg border border-slate-300 bg-slate-50 p-0.5 w-full">
          {modeOptions.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => setChatMode(option.id)}
              className={`flex-1 px-2 py-1 text-xs rounded-md transition-colors ${
                chatMode === option.id
                  ? "bg-gradient-to-r from-[#4f46e5] to-indigo-600 text-white shadow-sm"
                  : "text-slate-700 hover:bg-slate-100"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>

        {selectedAggregation ? (
          <div className="rounded-lg border border-indigo-200 bg-indigo-50/60 p-2">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-indigo-700">Active context</p>
            <p className="mt-1 text-[11px] text-slate-700">
              Dataset <span className="font-medium">{routeDatasetId}</span> using mart{" "}
              <span className="font-medium">{selectedMart?.label ?? selectedAggregation}</span>
            </p>
            {martSummary ? <p className="mt-1 text-[10px] text-slate-600">{martSummary}</p> : null}
            {contextTags.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-1">
                {contextTags.map((tag) => (
                  <span key={tag} className="rounded-full border border-indigo-200 bg-white px-2 py-0.5 text-[10px] text-indigo-700">
                    {tag}
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-[10px] text-slate-500">No structured query yet. Ask a chart question to build one.</p>
            )}
            {activeFocus ? (
              <div className="mt-3 rounded-lg border border-white/80 bg-white px-2 py-2">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Focused artifact</p>
                <p className="mt-1 text-[11px] text-slate-800">
                  {activeFocus.title || "Current artifact"}
                  {activeFocus.active_task ? ` • ${activeFocus.active_task.replace("_", " ")}` : ""}
                </p>
                {focusSuggestions.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {focusSuggestions.slice(0, 3).map((suggestion) => (
                      <button
                        key={suggestion}
                        type="button"
                        onClick={() => setMessage(suggestion)}
                        className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-700 hover:bg-slate-100"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {!selectedAggregation ? (
          <div className="h-full flex items-center justify-center text-center">
            <div>
              <Sparkles className="w-10 h-10 text-[#4f46e5] mx-auto mb-2" />
              <p className="text-sm text-slate-600">Select a mart to start chatting</p>
            </div>
          </div>
        ) : turns.length === 0 ? (
          <div className="h-full flex items-center justify-center text-center">
            <div>
              <Sparkles className="w-10 h-10 text-[#4f46e5] mx-auto mb-2" />
              <p className="text-sm text-slate-600">Ask me anything about your data!</p>
            </div>
          </div>
        ) : (
          turns.map((turn, index) => {
            const response = turn.response;
            const isAssistant = turn.role === "assistant";
            const clarifyOptions =
              response?.response_type === "clarify" && response.options && typeof response.options === "object"
                ? response.options
                : { metrics: [], dimensions: [], temporals: [], time_grains: [] };
            const stage = response?.response_type === "clarify" ? normalizeStage(response.missing?.[0]) : null;
            const metrics = Array.isArray(clarifyOptions.metrics) ? clarifyOptions.metrics : [];
            const dimensions = Array.isArray(clarifyOptions.dimensions) ? clarifyOptions.dimensions : [];
            const temporals = Array.isArray(clarifyOptions.temporals) ? clarifyOptions.temporals : [];
            const timeGrains = Array.isArray(clarifyOptions.time_grains) ? clarifyOptions.time_grains : [];
            return (
              <div
                key={`${turn.createdAt}-${index}`}
                className={`rounded-xl p-2.5 border ${
                  isAssistant ? "bg-white border-slate-200 shadow-sm" : "bg-indigo-100 border-indigo-200 shadow-sm"
                }`}
              >
                <p className="text-[10px] text-slate-600 mb-1">{isAssistant ? "VizAgent" : "You"}</p>
                {isAssistant ? (
                  turn.message ? (
                    <div className="text-sm">
                      <MarkdownMessage content={turn.message} />
                    </div>
                  ) : null
                ) : (
                  <p className="text-sm text-slate-900">{turn.message}</p>
                )}
                {isAssistant && response?.response_type === "chart" ? (
                  <div className="mt-2 px-3 py-2 bg-indigo-50 border border-indigo-200 rounded-lg">
                    <p className="text-xs text-indigo-700 font-medium">✨ Preview is being shown on the left panel</p>
                  </div>
                ) : null}
                {isAssistant && response?.query_spec && querySpecLabel(response.query_spec).length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {querySpecLabel(response.query_spec).map((tag) => (
                      <span key={`${turn.createdAt}-${tag}`} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-700">
                        {tag}
                      </span>
                    ))}
                  </div>
                ) : null}
                {isAssistant && response?.analysis ? (
                  <div className="mt-2 rounded-lg border border-indigo-200 bg-indigo-50/60 p-2">
                    <div className="flex flex-wrap gap-1.5">
                      <span className="rounded-full border border-indigo-200 bg-white px-2 py-0.5 text-[10px] uppercase tracking-wide text-indigo-700">
                        {response.analysis.task_type.replace("_", " ")}
                      </span>
                      <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] text-slate-600">
                        {response.analysis.agent_role}
                      </span>
                      {response.analysis.plan_spec.matched_kpi_label ? (
                        <span className="rounded-full border border-emerald-200 bg-white px-2 py-0.5 text-[10px] text-emerald-700">
                          {response.analysis.plan_spec.matched_kpi_label}
                        </span>
                      ) : null}
                    </div>
                    {response.analysis.insight_cards.slice(0, 2).map((card) => (
                      <p key={`${turn.createdAt}-${card.title}`} className="mt-1 text-[11px] text-slate-700">
                        <span className="font-medium text-slate-900">{card.title}:</span> {card.summary}
                      </p>
                    ))}
                  </div>
                ) : null}
                {isAssistant && response?.response_type === "clarify" ? (
                  <div className="mt-2 space-y-2">
                    {stage === "metric" ? (
                      metrics.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {metrics.map((item) => (
                            <button
                              key={`metric-${item}`}
                              type="button"
                              disabled={isLoading || !selectedAggregation}
                              onClick={() => handleClarifyChip(response, "metric", item)}
                              className="px-2 py-0.5 text-xs rounded-full border border-indigo-300 text-indigo-700 bg-indigo-100 hover:bg-indigo-200 disabled:opacity-50"
                            >
                              {item}
                            </button>
                          ))}
                        </div>
                      ) : null
                    ) : null}

                    {stage === "x_axis" ? (
                      <>
                        {dimensions.length > 0 ? (
                          <div>
                            <p className="text-[10px] uppercase tracking-wide text-blue-600 font-semibold mb-1">Dimensions</p>
                            <div className="flex flex-wrap gap-1.5">
                              {dimensions.map((item) => (
                                <button
                                  key={`dimension-${item}`}
                                  type="button"
                                  disabled={isLoading || !selectedAggregation}
                                  onClick={() => handleClarifyChip(response, "dimension", item)}
                                  className="px-2 py-0.5 text-xs rounded-full border border-blue-300 text-blue-700 bg-blue-100 hover:bg-blue-200 disabled:opacity-50"
                                >
                                  {item}
                                </button>
                              ))}
                            </div>
                          </div>
                        ) : null}
                        {temporals.length > 0 ? (
                          <div>
                            <p className="text-[10px] uppercase tracking-wide text-amber-600 font-semibold mb-1">Time Fields</p>
                            <div className="flex flex-wrap gap-1.5">
                              {temporals.map((item) => (
                                <button
                                  key={`temporal-${item}`}
                                  type="button"
                                  disabled={isLoading || !selectedAggregation}
                                  onClick={() => handleClarifyChip(response, "temporal", item)}
                                  className="px-2 py-0.5 text-xs rounded-full border border-amber-300 text-amber-700 bg-amber-100 hover:bg-amber-200 disabled:opacity-50"
                                >
                                  {item}
                                </button>
                              ))}
                            </div>
                          </div>
                        ) : null}
                      </>
                    ) : null}

                    {stage === "time_grain" ? (
                      timeGrains.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {timeGrains.map((item) => (
                            <button
                              key={`grain-${item}`}
                              type="button"
                              disabled={isLoading || !selectedAggregation}
                              onClick={() => handleClarifyChip(response, "time_grain", item)}
                              className="px-2 py-0.5 text-xs rounded-full border border-violet-300 text-violet-700 bg-violet-100 hover:bg-violet-200 disabled:opacity-50"
                            >
                              {item}
                            </button>
                          ))}
                        </div>
                      ) : null
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })
        )}
      </div>

      {/* Input Form */}
      <div className="border-t border-indigo-200/50 p-3 space-y-2 bg-white/80 backdrop-blur-sm">
        {/* Hints/Guidance */}
        {selectedAggregation && guidance.examples.length > 0 ? (
          <div className="rounded-lg border border-indigo-200 bg-indigo-50/50 p-2">
            <p className="text-[10px] text-indigo-900 font-medium mb-1">{guidance.title}</p>
            <div className="flex flex-wrap gap-1.5">
              {guidance.examples.slice(0, 2).map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setMessage(example)}
                  className="px-2 py-0.5 text-[10px] rounded-full border border-slate-300 text-slate-700 hover:bg-slate-100"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {activeFocus && focusSuggestions.length > 0 ? (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
            <p className="text-[10px] text-slate-900 font-medium mb-1">Ask about the focused artifact</p>
            <div className="flex flex-wrap gap-1.5">
              {focusSuggestions.slice(0, 3).map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => setMessage(suggestion)}
                  className="px-2 py-0.5 text-[10px] rounded-full border border-slate-300 text-slate-700 hover:bg-white"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {/* Saved Prompts */}
        {selectedAggregation && savedPrompts.length > 0 ? (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
            <button
              type="button"
              onClick={() => setShowSavedPrompts(!showSavedPrompts)}
              className="flex items-center justify-between w-full"
            >
              <p className="text-[10px] text-slate-900 font-medium">Saved prompts ({savedPrompts.length})</p>
              <ChevronRight className={`w-3 h-3 text-slate-600 transition-transform ${showSavedPrompts ? "rotate-90" : ""}`} />
            </button>
            {showSavedPrompts ? (
              <div className="mt-2 space-y-1">
                <button
                  type="button"
                  onClick={() => chatKey && clearSavedPrompts(chatKey)}
                  className="text-[10px] text-slate-600 hover:text-slate-900 mb-1"
                >
                  Clear all
                </button>
                {savedPrompts.map((prompt) => (
                  <div
                    key={prompt}
                    className="flex items-center gap-1 rounded-full border border-slate-300 bg-white px-2 py-0.5"
                  >
                    <button
                      type="button"
                      onClick={() => setMessage(prompt)}
                      className="flex-1 text-left text-[10px] text-slate-700 hover:text-slate-900 truncate"
                    >
                      {prompt}
                    </button>
                    <button
                      type="button"
                      onClick={() => chatKey && removeSavedPrompt(chatKey, prompt)}
                      className="text-slate-500 hover:text-slate-700"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {fallbackWarningText ? (
          <div className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1.5 space-y-0.5">
            <div>{fallbackWarningText}</div>
            {fallbackWarningDetails ? (
              <div className="text-[10px] text-amber-700">{fallbackWarningDetails}</div>
            ) : null}
          </div>
        ) : null}

        {showMissingDebugFlags ? (
          <div className="text-[10px] text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-2 py-1">
            ⚠️ Debug flags missing (check NEXT_PUBLIC_API_URL / backend version)
          </div>
        ) : null}

        {/* Error Display */}
        {error ? (
          <div className="flex items-center gap-2 text-red-700 text-xs bg-red-100 border border-red-300 rounded-lg px-2 py-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>{error}</span>
          </div>
        ) : null}

        {/* Input */}
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder={placeholder}
            disabled={!selectedAggregation || isLoading}
            className="flex-1 bg-white border border-slate-300 rounded-lg px-2.5 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 shadow-sm"
          />
          <button
            type="button"
            onClick={handleSavePrompt}
            disabled={!canSave}
            className="px-2 py-2 rounded-lg bg-white border border-slate-300 text-slate-700 hover:text-slate-900 disabled:opacity-60"
            title="Save prompt"
          >
            <BookmarkPlus className="w-4 h-4" />
          </button>
          <button
            type="submit"
            disabled={!canSend}
            className="px-3 py-2 rounded-lg bg-gradient-to-r from-[#4f46e5] to-indigo-600 text-white hover:from-indigo-600 hover:to-indigo-700 disabled:opacity-60 shadow-sm transition-colors"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </form>
      </div>
      </div>
    </>
  );
}
