import type { ChartSpecV1 } from './chartspec';

export interface ChatRequest {
  message: string;
  table: string;
  state?: Record<string, unknown>;
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

export interface ChatClarifyResponse {
  response_type: 'clarify';
  message: string;
  questions: string[];
  meta: Record<string, unknown>;
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
