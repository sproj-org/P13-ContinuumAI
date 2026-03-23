import type { ChartSpecV1 } from "./chartspec";

export type AnalysisTaskType =
  | "auto"
  | "query"
  | "insight"
  | "profile"
  | "forecast"
  | "anomaly"
  | "segment"
  | "strategy_risk";

export type AgentRole =
  | "viz_agent"
  | "profiling_agent"
  | "strategy_agent"
  | "insight_agent"
  | "ml_agent";

export type TimeGrain = "day" | "week" | "month" | "quarter" | "year";
export type MetricAggregation = "sum" | "avg" | "count" | "min" | "max";
export type RiskBand = "low" | "medium" | "high" | "unknown";

export interface SpecFilter {
  field: string;
  op: "=" | "!=" | "in" | "between" | ">" | ">=" | "<" | "<=";
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
  filters: SpecFilter[];
  limit?: number | null;
  kpi_id?: string | null;
  semantic_family?: string | null;
  drill_dimensions?: string[];
  recommendation_source?: string | null;
}

export interface PredictionSpec {
  mode?: "forecast" | "anomaly" | "risk";
  dataset_id?: string | null;
  table: string;
  metric: string;
  aggregation?: MetricAggregation;
  time_field: string;
  time_grain?: TimeGrain;
  filters?: SpecFilter[];
  horizon?: number;
  kpi_id?: string | null;
  target_value?: number | null;
  target_direction?: "up" | "down" | null;
}

export interface SegmentSpec {
  dataset_id?: string | null;
  table: string;
  entity_field: string;
  features?: string[];
  filters?: SpecFilter[];
  cluster_count?: number;
  metric_focus?: string | null;
}

export interface StrategySpec {
  dataset_id?: string | null;
  kpi_id: string;
  table?: string | null;
  target_value?: number | null;
  direction?: "up" | "down" | null;
  time_grain?: TimeGrain;
  horizon?: number;
  filters?: SpecFilter[];
}

export interface AgentTaskSpec {
  task_id: string;
  task_type: Exclude<AnalysisTaskType, "auto">;
  agent_role: AgentRole;
  title: string;
  priority: number;
  query_spec?: QuerySpec | null;
  prediction_spec?: PredictionSpec | null;
  segment_spec?: SegmentSpec | null;
  strategy_spec?: StrategySpec | null;
}

export interface PlanSpec {
  plan_id: string;
  dataset_id: string;
  table?: string | null;
  user_message: string;
  primary_task: Exclude<AnalysisTaskType, "auto">;
  route_reason: string;
  matched_kpi_id?: string | null;
  matched_kpi_label?: string | null;
  tasks: AgentTaskSpec[];
  suggested_follow_ups: string[];
}

export interface InsightCard {
  title: string;
  summary: string;
  severity: "info" | "warn" | "critical";
  source: AgentRole;
  recommended_action?: string | null;
  evidence: string[];
}

export interface PredictionPoint {
  label: string;
  actual?: number | null;
  forecast?: number | null;
  lower?: number | null;
  upper?: number | null;
  anomaly_score?: number | null;
  anomaly_flag: boolean;
  is_forecast: boolean;
  target_value?: number | null;
}

export interface PredictionAnomaly {
  label: string;
  value: number;
  deviation: number;
  severity: "low" | "medium" | "high";
}

export interface PredictionSummary {
  mode: "forecast" | "anomaly" | "risk";
  metric: string;
  time_field: string;
  time_grain: TimeGrain;
  horizon: number;
  points: PredictionPoint[];
  anomalies: PredictionAnomaly[];
  projected_change_pct?: number | null;
  risk_band?: RiskBand | null;
  target_value?: number | null;
  target_direction?: "up" | "down" | null;
  explanation?: string | null;
}

export interface SegmentAssignment {
  entity_id: string;
  cluster_id: number;
  projection_x?: number | null;
  projection_y?: number | null;
  feature_values: Record<string, number>;
}

export interface SegmentProfile {
  cluster_id: number;
  label: string;
  entity_count: number;
  centroid: Record<string, number>;
  metric_highlights: string[];
}

export interface SegmentSummary {
  entity_field: string;
  cluster_count: number;
  features: string[];
  assignments: SegmentAssignment[];
  profiles: SegmentProfile[];
  silhouette_hint?: number | null;
}

export interface StrategyRiskSummary {
  kpi_id: string;
  target_value?: number | null;
  current_value?: number | null;
  projected_value?: number | null;
  variance_to_target?: number | null;
  direction?: "up" | "down" | null;
  risk_band: RiskBand;
  explanation?: string | null;
}

export interface SuggestedAction {
  action_type: "forecast" | "anomaly" | "segment" | "drill" | "strategy_risk" | "open_chart_builder";
  label: string;
  description?: string | null;
  payload: Record<string, unknown>;
}

export interface NormalizedDataView {
  chart_spec?: ChartSpecV1 | null;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  summary?: string | null;
}

export interface AnalysisRequest {
  message?: string | null;
  task_type?: AnalysisTaskType;
  table?: string | null;
  chart_spec?: ChartSpecV1 | null;
  chart_rows?: Array<Record<string, unknown>>;
  query_spec?: QuerySpec | null;
  prediction_spec?: PredictionSpec | null;
  segment_spec?: SegmentSpec | null;
  strategy_spec?: StrategySpec | null;
  kpi_id?: string | null;
  metric?: string | null;
  time_field?: string | null;
  time_grain?: TimeGrain | null;
  horizon?: number | null;
  entity_field?: string | null;
  features?: string[];
  filters?: SpecFilter[];
  cluster_count?: number | null;
}

export interface AnalysisResponse {
  task_type: Exclude<AnalysisTaskType, "auto">;
  agent_role: AgentRole;
  plan_spec: PlanSpec;
  query_spec?: QuerySpec | null;
  primary_view?: NormalizedDataView | null;
  insight_cards: InsightCard[];
  prediction?: PredictionSummary | null;
  segmentation?: SegmentSummary | null;
  strategy?: StrategyRiskSummary | null;
  suggested_actions: SuggestedAction[];
  meta: Record<string, unknown>;
}
