import type { ChartSpecV1 } from './chartspec';

export type ChatMode = 'auto' | 'chart' | 'explain';
export type TimeGrain = 'day' | 'week' | 'month' | 'quarter' | 'year';
export type MetricAggregation = 'sum' | 'avg' | 'count' | 'min' | 'max';
export type MissingField = 'metric' | 'x_axis' | 'time_grain' | 'table';

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
  debug?: boolean;
}

export interface ChartSpecPatch {
  set?: Record<string, unknown>;
  unset?: string[];
  add?: Record<string, unknown>;
}

export interface ChatChartResponse {
  response_type: 'chart';
  chart_spec: ChartSpecV1;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  narrative: string;
  meta: Record<string, unknown>;
}

export interface ChatPatchResponse {
  response_type: 'chart_patch';
  patch: ChartSpecPatch;
  narrative?: string;
  meta: Record<string, unknown>;
}

export interface ChatExplainResponse {
  response_type: 'explain';
  message: string;
  citations: string[];
  meta: Record<string, unknown>;
}

export interface ClarifyOptions {
  metrics: string[];
  dimensions: string[];
  temporals: string[];
  time_grains: TimeGrain[];
}

export interface ChatClarifyResponse {
  response_type: 'clarify';
  clarify_id: string;
  question: string;
  missing: MissingField[];
  options: ClarifyOptions;
  message?: string;
  questions?: string[];
  meta: Record<string, unknown>;
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

export interface ChatRefuseResponse {
  response_type: 'refuse';
  message: string;
  meta: Record<string, unknown>;
}

export type ChatResponse =
  | ChatChartResponse
  | ChatPatchResponse
  | ChatExplainResponse
  | ChatClarifyResponse
  | ChatRefuseResponse;
