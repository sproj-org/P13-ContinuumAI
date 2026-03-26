import type { ChatStatePayload, ChatHistoryTurn, ChatResponse } from "@/lib/types/chat";
import type { ChartSpecV1 } from "@/lib/types/chartspec";
import { ApiRequestError } from "@/lib/api";

export const EMPTY_CHAT_SELECTIONS = {
  metric: null,
  dimension: null,
  temporal: null,
  time_grain: null,
  aggregation: null,
  limit: null,
} as const;

export function assistantText(response: ChatResponse): string {
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

export function toRequestState(
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
  },
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

export function buildChatHistory(
  turns: Array<{ role: "user" | "assistant"; message: string; response?: ChatResponse | null }>,
  nextMessage: string,
): ChatHistoryTurn[] {
  const history = turns.slice(-7).map((turn) => ({
    role: turn.role,
    message: turn.message,
    response_type: turn.response?.response_type ?? null,
  }));
  return [...history, { role: "user", message: nextMessage }];
}

export function applyChatResponseState(
  response: ChatResponse,
  originalIntent: string,
  update: {
    chatKey: string;
    setLastChartSpec: (key: string, spec: ChartSpecV1 | null) => void;
    patchChatState: (
      key: string,
      patch: Partial<{
        clarify_id: string | null;
        original_user_intent: string | null;
        selections: Partial<{
          metric: string | null;
          dimension: string | null;
          temporal: string | null;
          time_grain: "day" | "week" | "month" | "quarter" | "year" | null;
          aggregation: "sum" | "avg" | "count" | "min" | "max" | null;
          limit: number | null;
        }>;
      }>,
    ) => void;
  },
): void {
  const { chatKey, setLastChartSpec, patchChatState } = update;
  if (response.response_type === "chart") {
    setLastChartSpec(chatKey, response.chart_spec);
    patchChatState(chatKey, {
      clarify_id: null,
      original_user_intent: originalIntent,
      selections: EMPTY_CHAT_SELECTIONS,
    });
    return;
  }

  if (response.response_type === "clarify") {
    patchChatState(chatKey, {
      clarify_id: response.clarify_id,
      original_user_intent: originalIntent,
    });
    return;
  }

  patchChatState(chatKey, {
    clarify_id: null,
    original_user_intent: originalIntent,
  });
}

export function formatChatError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    return error.hint ? `${error.message} ${error.hint}` : error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Chat request failed.";
}
