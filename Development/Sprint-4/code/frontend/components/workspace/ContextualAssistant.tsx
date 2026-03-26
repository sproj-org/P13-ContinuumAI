"use client";

import { FormEvent, useMemo, useState } from "react";
import { BrainCircuit, Loader2, MessageSquareText, Send, Sparkles, TrendingUp } from "lucide-react";

import MarkdownMessage from "@/components/common/MarkdownMessage";
import { ApiRequestError, apiClient } from "@/lib/api";
import { applyChartSpecPatch } from "@/lib/chart-spec-patch";
import type { DecisionTaskType } from "@/lib/types/analysis";
import type { ChartSpecV1 } from "@/lib/types/chartspec";
import type { ChatFocusContext, ChatHistoryTurn, ChatRequest, ChatResponse } from "@/lib/types/chat";

type ContextualTurn = {
  role: "user" | "assistant";
  message: string;
  response?: ChatResponse | null;
};

export interface ContextualTaskAction {
  task: DecisionTaskType;
  label: string;
  onTrigger: () => void;
}

interface ContextualAssistantProps {
  datasetId: string;
  focus: ChatFocusContext;
  title: string;
  description: string;
  placeholder?: string;
  suggestions?: string[];
  taskActions?: ContextualTaskAction[];
  onChartSpecChange?: (chartSpec: ChartSpecV1) => void;
}

function assistantText(response: ChatResponse): string {
  if (response.response_type === "chart") {
    return response.narrative;
  }
  if (response.response_type === "chart_patch") {
    return response.narrative ?? "Applied the requested chart update.";
  }
  if (response.response_type === "clarify") {
    return response.question || "Could you clarify your request?";
  }
  return response.message;
}

function querySpecTags(response: ChatResponse | null | undefined): string[] {
  const spec = response?.query_spec;
  if (!spec) {
    return [];
  }

  const tags: string[] = [];
  if (spec.chart_type) {
    tags.push(`Chart ${spec.chart_type}`);
  }
  if (spec.aggregation && spec.measures[0]) {
    tags.push(`Metric ${spec.aggregation}(${spec.measures[0]})`);
  } else if (spec.measures[0]) {
    tags.push(`Metric ${spec.measures[0]}`);
  }
  if (spec.time_field) {
    tags.push(`Time ${spec.time_field}${spec.time_grain ? ` (${spec.time_grain})` : ""}`);
  } else if (spec.dimensions[0]) {
    tags.push(`Group ${spec.dimensions[0]}`);
  }
  return tags.slice(0, 3);
}

function formatError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    return error.hint ? `${error.message} ${error.hint}` : error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed.";
}

export default function ContextualAssistant({
  datasetId,
  focus,
  title,
  description,
  placeholder = "Ask a follow-up about this view...",
  suggestions = [],
  taskActions = [],
  onChartSpecChange,
}: ContextualAssistantProps) {
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turns, setTurns] = useState<ContextualTurn[]>([]);

  const history = useMemo<ChatHistoryTurn[]>(
    () =>
      turns.slice(-6).map((turn) => ({
        role: turn.role,
        message: turn.message,
        response_type: turn.response?.response_type ?? null,
      })),
    [turns],
  );

  const canSend = !isLoading && Boolean(focus.table || focus.chart_spec?.table || focus.analysis_context?.table);

  const sendPrompt = async (prompt: string) => {
    const trimmed = prompt.trim();
    if (!trimmed || !canSend) {
      return;
    }

    const nextUserTurn: ContextualTurn = { role: "user", message: trimmed };
    setTurns((previous) => [...previous, nextUserTurn]);
    setMessage("");
    setError(null);
    setIsLoading(true);

    const request: ChatRequest = {
      message: trimmed,
      table: focus.table ?? focus.chart_spec?.table ?? focus.analysis_context?.table ?? null,
      mode: "auto",
      focus,
      state: focus.chart_spec ? { last_chart_spec: focus.chart_spec } : undefined,
      history: [...history, { role: "user", message: trimmed }],
    };

    try {
      const response = await apiClient.postChat(datasetId, request);
      if (response.response_type === "chart" && response.chart_spec && onChartSpecChange) {
        onChartSpecChange(response.chart_spec);
      }
      if (response.response_type === "chart_patch" && focus.chart_spec && onChartSpecChange) {
        onChartSpecChange(applyChartSpecPatch(focus.chart_spec, response.patch));
      }
      setTurns((previous) => [...previous, { role: "assistant", message: assistantText(response), response }]);
    } catch (requestError) {
      setError(formatError(requestError));
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
        <div className="flex flex-wrap gap-2">
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
      </div>

      {focus.summary ? (
        <div className="mt-3 rounded-xl border border-indigo-100 bg-indigo-50 px-3 py-2 text-sm text-indigo-900">
          {focus.summary}
        </div>
      ) : null}

      {taskActions.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {taskActions.map((action) => (
            <button
              key={action.task}
              type="button"
              onClick={action.onTrigger}
              className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-slate-50 px-3 py-1.5 text-xs text-slate-700 hover:border-indigo-300 hover:bg-indigo-50"
            >
              <TrendingUp className="h-3.5 w-3.5" />
              <span>{action.label}</span>
            </button>
          ))}
        </div>
      ) : null}

      {suggestions.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {suggestions.slice(0, 4).map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => void sendPrompt(suggestion)}
              disabled={!canSend || isLoading}
              className="inline-flex items-center gap-1.5 rounded-full border border-indigo-200 bg-white px-3 py-1.5 text-xs text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>{suggestion}</span>
            </button>
          ))}
        </div>
      ) : null}

      {turns.length > 0 ? (
        <div className="mt-4 space-y-2">
          {turns.slice(-4).map((turn, index) => (
            <div
              key={`${turn.role}-${index}-${turn.message}`}
              className={`rounded-xl border px-3 py-2 ${
                turn.role === "assistant" ? "border-slate-200 bg-slate-50" : "border-indigo-200 bg-indigo-50"
              }`}
            >
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                {turn.role === "assistant" ? "Assistant" : "You"}
              </p>
              <div className="mt-1 text-sm text-slate-800">
                {turn.role === "assistant" ? <MarkdownMessage content={turn.message} /> : <p>{turn.message}</p>}
              </div>
              {turn.response?.analysis ? (
                <div className="mt-2 rounded-lg border border-slate-200 bg-white px-2 py-2 text-[11px] text-slate-700">
                  <div className="flex flex-wrap gap-1.5">
                    <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-600">
                      {turn.response.analysis.task_type.replace("_", " ")}
                    </span>
                    <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[10px] text-indigo-700">
                      {turn.response.analysis.agent_role}
                    </span>
                  </div>
                  {turn.response.analysis.insight_cards[0] ? (
                    <p className="mt-2 text-[11px] text-slate-700">
                      <span className="font-medium text-slate-900">{turn.response.analysis.insight_cards[0].title}:</span>{" "}
                      {turn.response.analysis.insight_cards[0].summary}
                    </p>
                  ) : null}
                </div>
              ) : null}
              {querySpecTags(turn.response).length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {querySpecTags(turn.response).map((tag) => (
                    <span key={tag} className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] text-slate-600">
                      {tag}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      {error ? (
        <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      ) : null}

      {!canSend ? (
        <div className="mt-3 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-3 py-3 text-xs text-slate-500">
          Select a mart or chart context before starting a contextual conversation.
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
          <span>Using the current artifact context to answer the follow-up.</span>
        </div>
      ) : null}
    </div>
  );
}
