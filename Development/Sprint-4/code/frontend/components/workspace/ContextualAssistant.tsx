"use client";

import { FormEvent, useState } from "react";
import { ArrowUpRight, BrainCircuit, Loader2, MessageSquareText, Send, Sparkles } from "lucide-react";

import MarkdownMessage from "@/components/common/MarkdownMessage";
import { apiClient } from "@/lib/api";
import { applyChartSpecPatch } from "@/lib/chart-spec-patch";
import { assistantText, applyChatResponseState, buildChatHistory, EMPTY_CHAT_SELECTIONS, formatChatError, toRequestState } from "@/lib/chat-runtime";
import { useAppStore } from "@/lib/store";
import type { ChartSpecV1 } from "@/lib/types/chartspec";
import type { ChatFocusContext, ChatQuickPrompt, ChatResponse } from "@/lib/types/chat";

type LocalPreview = {
  promptLabel: string;
  response: ChatResponse;
};

interface ContextualAssistantProps {
  datasetId: string;
  focus: ChatFocusContext;
  title: string;
  description: string;
  placeholder?: string;
  suggestions?: ChatQuickPrompt[];
  onChartSpecChange?: (chartSpec: ChartSpecV1) => void;
}

function promptMode(prompt: ChatQuickPrompt | null | undefined): "auto" | "chart" | "explain" {
  if (!prompt) {
    return "auto";
  }
  if (prompt.preferred_route === "chart_patch" || prompt.preferred_route === "chart") {
    return "chart";
  }
  if (prompt.preferred_route === "explain") {
    return "explain";
  }
  return "auto";
}

function promptBadge(prompt: ChatQuickPrompt): string {
  if (prompt.prompt_kind === "task" && prompt.task_type) {
    return prompt.task_type.replace("_", " ");
  }
  return prompt.prompt_kind.replace("_", " ");
}

export default function ContextualAssistant({
  datasetId,
  focus,
  title,
  description,
  placeholder = "Ask VizAgent about this artifact...",
  suggestions = [],
  onChartSpecChange,
}: ContextualAssistantProps) {
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastPreview, setLastPreview] = useState<LocalPreview | null>(null);

  const {
    chatTurnsByKey,
    lastChartSpecByKey,
    appendChatTurn,
    patchChatState,
    setLastChartSpec,
    setSelectedAggregation,
    setVizAgentOpen,
  } = useAppStore();

  const table = focus.table ?? focus.chart_spec?.table ?? focus.analysis_context?.table ?? null;
  const chatKey = table ? `${datasetId}:${table}` : null;
  const turns = chatKey ? chatTurnsByKey[chatKey] ?? [] : [];
  const lastChartSpec = chatKey ? lastChartSpecByKey[chatKey] ?? focus.chart_spec ?? null : focus.chart_spec ?? null;
  const canSend = !isLoading && Boolean(chatKey);

  const sendPrompt = async (promptText: string, quickPrompt?: ChatQuickPrompt | null) => {
    const trimmed = promptText.trim();
    if (!trimmed || !chatKey || !table) {
      return;
    }

    const originalIntent = quickPrompt?.prompt_text.trim() || trimmed;
    const userVisibleMessage = quickPrompt?.label || trimmed;

    setSelectedAggregation(table);
    setVizAgentOpen(true);
    setMessage("");
    setError(null);
    setIsLoading(true);

    patchChatState(chatKey, {
      clarify_id: null,
      selections: EMPTY_CHAT_SELECTIONS,
      original_user_intent: originalIntent,
    });
    appendChatTurn(chatKey, {
      role: "user",
      message: userVisibleMessage,
      createdAt: new Date().toISOString(),
    });

    const requestState = toRequestState(lastChartSpec, {
      clarify_id: null,
      original_user_intent: originalIntent,
      selections: EMPTY_CHAT_SELECTIONS,
    });

    try {
      const response = await apiClient.postChat(datasetId, {
        message: originalIntent,
        table,
        mode: promptMode(quickPrompt),
        state: requestState,
        history: buildChatHistory(turns, originalIntent),
        focus,
        quick_prompt: quickPrompt ?? undefined,
      });
      appendChatTurn(chatKey, {
        role: "assistant",
        message: assistantText(response),
        response,
        createdAt: new Date().toISOString(),
      });
      applyChatResponseState(response, originalIntent, {
        chatKey,
        setLastChartSpec,
        patchChatState,
      });
      if (response.response_type === "chart" && response.chart_spec && onChartSpecChange) {
        onChartSpecChange(response.chart_spec);
      }
      if (response.response_type === "chart_patch" && focus.chart_spec && onChartSpecChange) {
        onChartSpecChange(applyChartSpecPatch(focus.chart_spec, response.patch));
      }
      setLastPreview({
        promptLabel: userVisibleMessage,
        response,
      });
    } catch (requestError) {
      setError(formatChatError(requestError));
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await sendPrompt(message);
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <div className="rounded-xl bg-indigo-100 p-2 text-indigo-700">
              <MessageSquareText className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">{title}</p>
              <p className="text-xs text-slate-500">{description}</p>
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setVizAgentOpen(true)}
          className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-slate-50 px-3 py-1.5 text-xs text-slate-700 hover:border-indigo-300 hover:bg-indigo-50"
        >
          <ArrowUpRight className="h-3.5 w-3.5" />
          <span>Open VizAgent</span>
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-600">
          Focus: {focus.focus_type.replace("_", " ")}
        </span>
        {focus.active_task ? (
          <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-1 text-[11px] text-indigo-700">
            {focus.active_task.replace("_", " ")}
          </span>
        ) : null}
        {focus.kpi_id ? (
          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-[11px] text-emerald-700">
            KPI {focus.kpi_id}
          </span>
        ) : null}
      </div>

      {focus.summary ? (
        <div className="mt-3 rounded-xl border border-indigo-100 bg-indigo-50 px-3 py-2 text-sm text-indigo-900">
          {focus.summary}
        </div>
      ) : null}

      {suggestions.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {suggestions.slice(0, 4).map((suggestion) => (
            <button
              key={`${suggestion.prompt_kind}-${suggestion.label}`}
              type="button"
              onClick={() => void sendPrompt(suggestion.prompt_text, suggestion)}
              disabled={!canSend || isLoading}
              className="inline-flex items-center gap-1.5 rounded-full border border-indigo-200 bg-white px-3 py-1.5 text-xs text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>{suggestion.label}</span>
              <span className="rounded-full bg-indigo-50 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-indigo-600">
                {promptBadge(suggestion)}
              </span>
            </button>
          ))}
        </div>
      ) : null}

      {lastPreview ? (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Sent to VizAgent</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">{lastPreview.promptLabel}</p>
            </div>
            <button
              type="button"
              onClick={() => setVizAgentOpen(true)}
              className="inline-flex items-center gap-1 rounded-full border border-slate-300 bg-white px-3 py-1 text-[11px] text-slate-700 hover:bg-slate-100"
            >
              <ArrowUpRight className="h-3 w-3" />
              Continue there
            </button>
          </div>
          <div className="mt-2 text-sm text-slate-800">
            <MarkdownMessage content={assistantText(lastPreview.response)} />
          </div>
          {lastPreview.response.analysis ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-600">
                {lastPreview.response.analysis.task_type.replace("_", " ")}
              </span>
              <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[10px] text-indigo-700">
                {lastPreview.response.analysis.agent_role}
              </span>
            </div>
          ) : null}
        </div>
      ) : null}

      {error ? (
        <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      ) : null}

      {!canSend ? (
        <div className="mt-3 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-3 py-3 text-xs text-slate-500">
          Select a mart or chart context before handing this conversation to VizAgent.
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="mt-3 flex gap-2">
        <input
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          disabled={!canSend || isLoading}
          placeholder={placeholder}
          className="flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 disabled:bg-slate-50"
        />
        <button
          type="submit"
          disabled={!message.trim() || !canSend || isLoading}
          className="inline-flex items-center justify-center rounded-xl bg-gradient-to-r from-[#4f46e5] to-indigo-600 px-3 text-white disabled:opacity-60"
        >
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </button>
      </form>

      {isLoading ? (
        <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
          <BrainCircuit className="h-3.5 w-3.5 text-indigo-600" />
          <span>Sending the current artifact context into the shared VizAgent thread.</span>
        </div>
      ) : null}
    </div>
  );
}
