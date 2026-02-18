"use client";

import { FormEvent, useState } from "react";
import { useAppStore } from "@/lib/store";
import { apiClient } from "@/lib/api";
import type { ChatResponse } from "@/lib/types/chartspec";
import { renderChart } from "@/components/workspace/renderChart";
import { Loader2, MessageSquare, Send, AlertTriangle } from "lucide-react";

interface ChatTurn {
  message: string;
  response: ChatResponse;
}

export default function ChatPanel() {
  const { selectedDatasetId, selectedAggregation } = useAppStore();
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) return;

    if (!selectedAggregation) {
      setError("Select a mart first");
      return;
    }

    setError(null);
    setIsLoading(true);
    try {
      const response = await apiClient.postChat(selectedDatasetId, {
        message: trimmed,
        table: selectedAggregation,
      });
      setTurns((prev) => [...prev, { message: trimmed, response }]);
      setMessage("");
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
        <h2 className="text-white font-semibold">Chat Analyst</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {turns.length === 0 ? (
          <div className="h-full flex items-center justify-center text-center">
            <div>
              <MessageSquare className="w-12 h-12 text-gray-600 mx-auto mb-3" />
              <p className="text-gray-400">Ask for a chart using the selected mart.</p>
            </div>
          </div>
        ) : (
          turns.map((turn, index) => (
            <div key={`${index}-${turn.message}`} className="space-y-3">
              <div className="bg-white/5 border border-white/10 rounded-xl p-3">
                <p className="text-xs text-gray-400 mb-1">You</p>
                <p className="text-sm text-white">{turn.message}</p>
              </div>

              <div className="bg-white/5 border border-white/10 rounded-xl p-3">
                <p className="text-xs text-gray-400 mb-1">Assistant</p>
                <p className="text-sm text-gray-200">{turn.response.narrative}</p>
                {turn.response.response_type === "chart" ? (
                  <div className="mt-4 min-h-[320px]">
                    {renderChart(turn.response.chart_spec, turn.response.rows)}
                  </div>
                ) : null}
              </div>
            </div>
          ))
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
            placeholder="Show net sales by region for last 30 days"
            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-[#5237ff]/50"
          />
          <button
            type="submit"
            disabled={isLoading}
            className="px-3 py-2 rounded-lg bg-[#5237ff]/20 border border-[#5237ff]/30 text-[#a397ff] hover:text-white disabled:opacity-60"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
      </form>
    </div>
  );
}
