import type { ChartSemanticContext, ChartSpecV1 } from './chartspec';
import type {
  AnalysisContext,
  AnalysisResponse,
  MetricAggregation,
  PlanSpec,
  QuerySpec,
  SpecFilter as QuerySpecFilter,
  TimeGrain,
} from './analysis';
export type { AnalysisResponse, PlanSpec, QuerySpec, QuerySpecFilter };

export type ChatMode = 'auto' | 'chart' | 'explain';
export type MissingField = 'metric' | 'x_axis' | 'time_grain' | 'table';
export type ChatRole = 'user' | 'assistant';
export type ChatResponseType = 'chart' | 'chart_patch' | 'explain' | 'clarify' | 'refuse';
export type ChatFallbackReason = 'missing_key' | 'openai_error';
export type ChatPromptKind = 'ask' | 'task' | 'chart_edit' | 'follow_up' | 'compare' | 'drill';
export type ChatPromptRoute = 'explain' | 'analysis' | 'chart' | 'chart_patch' | 'guidance';
export type ChatPromptAnswerMode =
  | 'explain'
  | 'what_happened'
  | 'diagnose'
  | 'recommend'
  | 'next_best_action'
  | 'drill_priority'
  | 'segment_differentiation'
  | 'segment_comparison'
  | 'forecast_interpretation'
  | 'risk_explanation'
  | 'strategy_alignment'
  | 'kpi_strategy_relationship';
export type ChatPromptArtifactAction =
  | 'explain_chart'
  | 'explain_kpi'
  | 'next_step'
  | 'drill_next'
  | 'chart_change'
  | 'forecast_drivers'
  | 'forecast_target_gap'
  | 'anomaly_driver'
  | 'anomaly_scope'
  | 'segment_differentiators'
  | 'segment_compare_extremes'
  | 'segment_drill_priority'
  | 'risk_driver'
  | 'risk_slice'
  | 'risk_next_step'
  | 'strategy_alignment'
  | 'kpi_strategy_relationship';

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

export type ChatFocusType = 'chart' | 'dashboard' | 'kpi' | 'analysis_result' | 'drill_state';

export interface ChatFocusContext {
  focus_type: ChatFocusType;
  title?: string | null;
  table?: string | null;
  kpi_id?: string | null;
  chart_spec?: ChartSpecV1 | null;
  chart_rows?: Array<Record<string, unknown>>;
  analysis_context?: AnalysisContext | null;
  semantic_context?: ChartSemanticContext | null;
  active_task?: string | null;
  analysis_result?: AnalysisResponse | null;
  summary?: string | null;
  breadcrumbs?: string[];
}

export interface ChatQuickPrompt {
  label: string;
  prompt_text: string;
  prompt_kind: ChatPromptKind;
  preferred_route: ChatPromptRoute;
  answer_mode?: ChatPromptAnswerMode | null;
  focus_type?: ChatFocusType | null;
  analysis_result_type?: string | null;
  artifact_action?: ChatPromptArtifactAction | null;
  task_type?: string | null;
}

export interface ChatRequest {
  message: string;
  table?: string | null;
  mode?: ChatMode;
  state?: ChatStatePayload;
  history?: ChatHistoryTurn[];
  focus?: ChatFocusContext | null;
  quick_prompt?: ChatQuickPrompt | null;
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

export interface ChatChartResponse extends ChatDebugMetadata {
  response_type: 'chart';
  chart_spec: ChartSpecV1;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  narrative: string;
  meta: Record<string, unknown>;
  query_spec?: QuerySpec | null;
  plan_spec?: PlanSpec | null;
  analysis?: AnalysisResponse | null;
}

export interface ChatPatchResponse extends ChatDebugMetadata {
  response_type: 'chart_patch';
  patch: ChartSpecPatch;
  narrative?: string;
  meta: Record<string, unknown>;
  query_spec?: QuerySpec | null;
  plan_spec?: PlanSpec | null;
  analysis?: AnalysisResponse | null;
}

export interface ChatExplainResponse extends ChatDebugMetadata {
  response_type: 'explain';
  message: string;
  citations: string[];
  meta: Record<string, unknown>;
  query_spec?: QuerySpec | null;
  plan_spec?: PlanSpec | null;
  analysis?: AnalysisResponse | null;
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
  plan_spec?: PlanSpec | null;
  analysis?: AnalysisResponse | null;
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
  plan_spec?: PlanSpec | null;
  analysis?: AnalysisResponse | null;
}

export type ChatResponse =
  | ChatChartResponse
  | ChatPatchResponse
  | ChatExplainResponse
  | ChatClarifyResponse
  | ChatRefuseResponse;
