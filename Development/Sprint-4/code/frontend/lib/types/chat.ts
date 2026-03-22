import type { ChartSpecV1 } from './chartspec';

export type ChatMode = 'auto' | 'chart' | 'explain';
export type TimeGrain = 'day' | 'week' | 'month' | 'quarter' | 'year';
export type MetricAggregation = 'sum' | 'avg' | 'count' | 'min' | 'max';
export type MissingField = 'metric' | 'x_axis' | 'time_grain' | 'table';
export type ChatRole = 'user' | 'assistant';
export type ChatResponseType = 'chart' | 'chart_patch' | 'explain' | 'clarify' | 'refuse';
export type ChatFallbackReason = 'missing_key' | 'openai_error';

export interface ChatDebugMetadata {
  used_fallback?: boolean;
  openai_configured?: boolean;
  fallback_reason?: ChatFallbackReason;
  openai_error_type?: string | null;
  openai_status_code?: number | null;
  openai_error_hint?: string | null;
}

export interface ChatSelections {
  metric?: string;
  dimension?: string;
  temporal?: string;
  time_grain?: TimeGrain;
  aggregation?: MetricAggregation;
  limit?: number;
}

export interface ChatStatePayload {
  last_chart_spec?: ChartSpecV1;
  clarify_id?: string;
  selections?: ChatSelections;
  original_user_intent?: string;
}

export interface ChatRequest {
  message: string;
  table: string;
  mode?: ChatMode;
  state?: ChatStatePayload;
  history?: ChatHistoryTurn[];
  debug?: boolean;
}

export interface ChatHistoryTurn {
  role: ChatRole;
  message: string;
  response_type?: ChatResponseType | null;
}

export interface ChartSpecPatch {
  set?: Record<string, unknown>;
  unset?: string[];
  add?: Record<string, unknown>;
}

export interface QuerySpecFilter {
  field: string;
  op: string;
  value?: unknown;
}

export interface QuerySpec {
  dataset_id?: string | null;
  table?: string | null;
  chart_type?: "bar" | "line" | "pie" | "histogram" | "kpi" | null;
  measures: string[];
  dimensions: string[];
  time_field?: string | null;
  aggregation?: MetricAggregation | null;
  time_grain?: TimeGrain | null;
  filters: QuerySpecFilter[];
  limit?: number | null;
}

export interface ChatChartResponse extends ChatDebugMetadata {
  response_type: 'chart';
  chart_spec: ChartSpecV1;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  narrative: string;
  meta: Record<string, unknown>;
  query_spec?: QuerySpec | null;
}

export interface ChatPatchResponse extends ChatDebugMetadata {
  response_type: 'chart_patch';
  patch: ChartSpecPatch;
  narrative?: string;
  meta: Record<string, unknown>;
  query_spec?: QuerySpec | null;
}

export interface ChatExplainResponse extends ChatDebugMetadata {
  response_type: 'explain';
  message: string;
  citations: string[];
  meta: Record<string, unknown>;
  query_spec?: QuerySpec | null;
}

export interface ClarifyOptions {
  metrics: string[];
  dimensions: string[];
  temporals: string[];
  time_grains: TimeGrain[];
}

export interface ChatClarifyResponse extends ChatDebugMetadata {
  response_type: 'clarify';
  clarify_id: string;
  question: string;
  missing: MissingField[];
  options: ClarifyOptions;
  message?: string;
  questions?: string[];
  meta: Record<string, unknown>;
  query_spec?: QuerySpec | null;
}

export interface ChatHintsResponse {
  measures: string[];
  dimensions: string[];
  temporals: string[];
  example_prompts: {
    auto: string[];
    chart: string[];
    explain: string[];
  };
}

export interface ChatRefuseResponse extends ChatDebugMetadata {
  response_type: 'refuse';
  message: string;
  meta: Record<string, unknown>;
  query_spec?: QuerySpec | null;
}

export type ChatResponse =
  | ChatChartResponse
  | ChatPatchResponse
  | ChatExplainResponse
  | ChatClarifyResponse
  | ChatRefuseResponse;
