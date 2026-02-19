"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useAppStore } from "@/lib/store";
import { apiClient } from "@/lib/api";
import type { ChatClarifyResponse, ChatRequest, ChatResponse, ChatStatePayload } from "@/lib/types/chat";
import { renderChart } from "@/components/workspace/renderChart";
import { Loader2, MessageSquare, Send, AlertTriangle, Trash2 } from "lucide-react";

function assistantText(response: ChatResponse): string {
  if (response.response_type === "chart") {
    return response.narrative;
  }
  if (response.response_type === "chart_patch") {
    return response.narrative ?? "Applied a chart update request.";
  }
  if (response.response_type === "clarify") {
    return response.question || "Could you clarify your request?";
  }
  if (response.response_type === "refuse") {
    return response.message;
  }
  return response.message;
}

const modeOptions: Array<{ id: "auto" | "chart" | "explain"; label: string }> = [
  { id: "auto", label: "Auto" },
  { id: "chart", label: "Chart" },
  { id: "explain", label: "Explain" },
];

const EMPTY_SELECTIONS = {
  metric: null,
  dimension: null,
  temporal: null,
  time_grain: null,
  aggregation: null,
  limit: null,
} as const;

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

export default function ChatPanel() {
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
    appendChatTurn,
    clearChat,
    setLastChartSpec,
    patchChatState,
  } = useAppStore();
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const routeDatasetId = params?.datasetId || selectedDatasetId;

  const chatKey = useMemo(
    () => (selectedAggregation ? `${routeDatasetId}:${selectedAggregation}` : null),
    [routeDatasetId, selectedAggregation]
  );
  const turns = chatKey ? chatTurnsByKey[chatKey] ?? [] : [];
  const lastChartSpec = chatKey ? lastChartSpecByKey[chatKey] ?? null : null;
  const chatState = chatKey ? chatStateByKey[chatKey] : undefined;
  const firstUserIntent = useMemo(
    () => turns.find((turn) => turn.role === "user")?.message ?? null,
    [turns]
  );

  useEffect(() => {
    setError(null);
    setMessage("");
  }, [chatKey]);

  const placeholder = useMemo(() => {
    if (!selectedAggregation) {
      return "Select a mart to start chatting...";
    }
    if (chatMode === "chart") {
      return "Request a chart... (e.g., revenue by month)";
    }
    if (chatMode === "explain") {
      return "Ask for an explanation... (e.g., what does this mart represent?)";
    }
    return "Ask a business question... (e.g., sales by region)";
  }, [chatMode, selectedAggregation]);

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
      };
      const response = await apiClient.postChat(routeDatasetId, request);
      appendChatTurn(chatKey, {
        role: "assistant",
        message: assistantText(response),
        response,
        createdAt: new Date().toISOString(),
      });
      applyResponseState(chatKey, response, state?.original_user_intent ?? requestMessage);
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

  const handleClarifyChip = async (
    clarifyResponse: ChatClarifyResponse,
    prefix: "metric" | "dimension" | "temporal",
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

  return (
    <div className="h-full flex flex-col">
      <div className="border-b border-white/10 p-4 flex items-center gap-2">
        <MessageSquare className="w-5 h-5 text-[#5237ff]" />
        <div className="flex-1">
          <h2 className="text-white font-semibold">Chat Analyst</h2>
          <p className="text-xs text-gray-400">
            {selectedAggregation ? `Chat scoped to: ${selectedAggregation}` : "Select a mart to chat"}
          </p>
          <div className="mt-2">
            <select
              value={selectedAggregation ?? ""}
              onChange={(event) => setSelectedAggregation(event.target.value || null)}
              className="w-full max-w-xs bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-[#5237ff]/50"
            >
              <option value="">Select mart</option>
              {availableMarts.map((mart) => (
                <option key={mart.id} value={mart.id}>
                  {mart.label ?? mart.id}
                </option>
              ))}
            </select>
          </div>
          <div className="mt-2 inline-flex rounded-lg border border-white/10 bg-white/5 p-1">
            {modeOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => setChatMode(option.id)}
                className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                  chatMode === option.id
                    ? "bg-[#5237ff]/30 text-[#c7beff]"
                    : "text-gray-300 hover:bg-white/10"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <button
          type="button"
          onClick={() => chatKey && clearChat(chatKey)}
          disabled={!chatKey || turns.length === 0}
          className="px-2 py-1 text-xs text-gray-300 border border-white/10 rounded-lg hover:bg-white/5 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span className="inline-flex items-center gap-1">
            <Trash2 className="w-3.5 h-3.5" />
            Clear
          </span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {!selectedAggregation ? (
          <div className="h-full flex items-center justify-center text-center">
            <div>
              <MessageSquare className="w-12 h-12 text-gray-600 mx-auto mb-3" />
              <p className="text-gray-400">Select a mart to chat.</p>
            </div>
          </div>
        ) : turns.length === 0 ? (
          <div className="h-full flex items-center justify-center text-center">
            <div>
              <MessageSquare className="w-12 h-12 text-gray-600 mx-auto mb-3" />
              <p className="text-gray-400">Ask for a chart or explanation using the selected mart.</p>
            </div>
          </div>
        ) : (
          turns.map((turn, index) => {
            const response = turn.response;
            const isAssistant = turn.role === "assistant";
            const clarifyOptions =
              response?.response_type === "clarify" && response.options && typeof response.options === "object"
                ? response.options
                : { metrics: [], dimensions: [], temporals: [] };
            const metrics = Array.isArray(clarifyOptions.metrics) ? clarifyOptions.metrics : [];
            const dimensions = Array.isArray(clarifyOptions.dimensions) ? clarifyOptions.dimensions : [];
            const temporals = Array.isArray(clarifyOptions.temporals) ? clarifyOptions.temporals : [];
            return (
              <div
                key={`${turn.createdAt}-${index}`}
                className={`rounded-xl p-3 border ${
                  isAssistant ? "bg-white/5 border-white/10" : "bg-[#5237ff]/10 border-[#5237ff]/30"
                }`}
              >
                <p className="text-xs text-gray-400 mb-1">{isAssistant ? "Assistant" : "You"}</p>
                <p className={`text-sm ${isAssistant ? "text-gray-200" : "text-white"}`}>{turn.message}</p>
                {isAssistant && response?.response_type === "chart" ? (
                  <div className="mt-4 min-h-[320px]">
                    {renderChart(response.chart_spec, response.rows)}
                  </div>
                ) : null}
                {isAssistant && response?.response_type === "clarify" ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {metrics.length > 0
                      ? metrics.map((item) => (
                      <button
                        key={`metric-${item}`}
                        type="button"
                        disabled={isLoading || !selectedAggregation}
                        onClick={() => handleClarifyChip(response, "metric", item)}
                        className="px-2 py-1 text-xs rounded-full border border-[#5237ff]/40 text-[#c7beff] bg-[#5237ff]/15 hover:bg-[#5237ff]/25 disabled:opacity-50"
                      >
                        {item}
                      </button>
                        ))
                      : null}
                    {dimensions.length > 0
                      ? dimensions.map((item) => (
                      <button
                        key={`dimension-${item}`}
                        type="button"
                        disabled={isLoading || !selectedAggregation}
                        onClick={() => handleClarifyChip(response, "dimension", item)}
                        className="px-2 py-1 text-xs rounded-full border border-blue-500/40 text-blue-300 bg-blue-500/10 hover:bg-blue-500/20 disabled:opacity-50"
                      >
                        {item}
                      </button>
                        ))
                      : null}
                    {temporals.length > 0
                      ? temporals.map((item) => (
                      <button
                        key={`temporal-${item}`}
                        type="button"
                        disabled={isLoading || !selectedAggregation}
                        onClick={() => handleClarifyChip(response, "temporal", item)}
                        className="px-2 py-1 text-xs rounded-full border border-amber-500/40 text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 disabled:opacity-50"
                      >
                        {item}
                      </button>
                        ))
                      : null}
                  </div>
                ) : null}
              </div>
            );
          })
        )}
      </div>

      <form onSubmit={handleSubmit} className="border-t border-white/10 p-4 space-y-2">
        {error ? (
          <div className="flex items-center gap-2 text-red-300 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
            <AlertTriangle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        ) : null}

        <div className="flex gap-2">
          <input
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder={placeholder}
            disabled={!selectedAggregation || isLoading}
            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-[#5237ff]/50"
          />
          <button
            type="submit"
            disabled={!canSend}
            className="px-3 py-2 rounded-lg bg-[#5237ff]/20 border border-[#5237ff]/30 text-[#a397ff] hover:text-white disabled:opacity-60"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
        <p className="text-[11px] text-gray-500">
          Mode: {chatMode.toUpperCase()} | Mart: {selectedAggregation ?? "none"}
        </p>
      </form>
    </div>
  );
}
