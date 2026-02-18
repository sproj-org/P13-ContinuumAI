"use client";

import { FormEvent, useMemo, useState } from "react";
import { useAppStore } from "@/lib/store";
import { apiClient } from "@/lib/api";
import type { ChatResponse } from "@/lib/types/chat";
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
    return response.message;
  }
  if (response.response_type === "refuse") {
    return response.message;
  }
  return response.message;
}

export default function ChatPanel() {
  const {
    selectedDatasetId,
    selectedAggregation,
    chatTurnsByKey,
    lastChartSpecByKey,
    appendChatTurn,
    clearChat,
    setLastChartSpec,
  } = useAppStore();
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chatKey = useMemo(
    () => (selectedAggregation ? `${selectedDatasetId}:${selectedAggregation}` : null),
    [selectedDatasetId, selectedAggregation]
  );
  const turns = chatKey ? chatTurnsByKey[chatKey] ?? [] : [];
  const lastChartSpec = chatKey ? lastChartSpecByKey[chatKey] ?? null : null;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) return;

    if (!selectedAggregation || !chatKey) {
      setError("Select a mart first");
      return;
    }

    appendChatTurn(chatKey, {
      role: "user",
      message: trimmed,
      createdAt: new Date().toISOString(),
    });
    setMessage("");
    setError(null);
    setIsLoading(true);
    try {
      const response = await apiClient.postChat(selectedDatasetId, {
        message: trimmed,
        table: selectedAggregation,
        state: lastChartSpec ? { last_chart_spec: lastChartSpec } : undefined,
      });
      appendChatTurn(chatKey, {
        role: "assistant",
        message: assistantText(response),
        response,
        createdAt: new Date().toISOString(),
      });
      if (response.response_type === "chart") {
        setLastChartSpec(chatKey, response.chart_spec);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Chat request failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col">
      <div className="border-b border-white/10 p-4 flex items-center gap-2">
        <MessageSquare className="w-5 h-5 text-[#5237ff]" />
        <div className="flex-1">
          <h2 className="text-white font-semibold">Chat Analyst</h2>
          <p className="text-xs text-gray-400">
            {selectedAggregation ? `Mart: ${selectedAggregation}` : "Select a mart to chat"}
          </p>
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
                {isAssistant && response?.response_type === "clarify" && response.questions.length > 0 ? (
                  <div className="mt-3 text-xs text-gray-400">
                    {response.questions.map((question, questionIndex) => (
                      <p key={`${questionIndex}-${question}`}>- {question}</p>
                    ))}
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
            placeholder={
              selectedAggregation
                ? "Show net sales by region for last 30 days"
                : "Select a mart to start chatting"
            }
            disabled={!selectedAggregation || isLoading}
            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-[#5237ff]/50"
          />
          <button
            type="submit"
            disabled={isLoading || !selectedAggregation}
            className="px-3 py-2 rounded-lg bg-[#5237ff]/20 border border-[#5237ff]/30 text-[#a397ff] hover:text-white disabled:opacity-60"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
      </form>
    </div>
  );
}
