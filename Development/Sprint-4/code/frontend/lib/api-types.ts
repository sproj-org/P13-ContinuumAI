/**
 * Backend API Types
 * These types match the exact schema from backend/services/profiling/profile_schema.py
 */

// Enums matching backend
export type PhysicalType = 'string' | 'int' | 'float' | 'boolean' | 'date' | 'datetime' | 'unknown';
export type LogicalType = 'numeric' | 'categorical' | 'datetime' | 'boolean' | 'text';
export type Role = 'id' | 'dimension' | 'measure' | 'datetime' | 'boolean' | 'text';
export type CardinalityBucket = 'low' | 'medium' | 'high';

// Stats types
export interface TopKItem {
  value: string;
  count: number;
  percent: number; // 0-1 range
}

export interface NumericStats {
  kind: 'numeric';
  null_count: number;
  min: number | null;
  max: number | null;
  mean: number | null;
  stddev: number | null;
  p05: number | null;
  p50: number | null; // median
  p95: number | null;
  zero_count: number;
}

export interface CategoricalStats {
  kind: 'categorical';
  null_count: number;
  distinct_count: number;
  top_k: TopKItem[];
}

export interface DatetimeStats {
  kind: 'datetime';
  null_count: number;
  min: string | null;
  max: string | null;
  distinct_days: number | null;
}

export interface BooleanStats {
  kind: 'boolean';
  true_count: number;
  false_count: number;
  null_count: number;
}

export interface TextStats {
  kind: 'text';
  min_len: number | null;
  max_len: number | null;
  avg_len: number | null;
  sample_values: string[];
  top_k: TopKItem[];
}

export type StatsUnion = NumericStats | CategoricalStats | DatetimeStats | BooleanStats | TextStats;

// Column profile from backend
export interface ColumnProfileAPI {
  name: string;
  physical_type: PhysicalType;
  logical_type: LogicalType;
  base_role: Role;
  effective_role: Role;
  
  row_count: number;
  distinct_count: number;
  null_count: number;
  null_fraction: number; // 0-1 range
  cardinality_bucket: CardinalityBucket;
  sample_values: string[];
  
  stats: StatsUnion | null;
  
  is_unique: boolean;
  base_needs_review: boolean;
  base_issues: string[];
  
  agent_meta: Record<string, unknown>;
  llm_meta: Record<string, unknown>;
  effective_meta: Record<string, unknown>;
}

// Dataset profile from backend
export interface DatasetProfileAPI {
  dataset_name: string;
  schema_name: string | null;
  table_name: string | null;
  row_count: number;
  column_count: number;
  profiled_at: string; // ISO datetime
  columns: ColumnProfileAPI[];
  dataset_meta: Record<string, unknown>;
}

// Aggregation summary for listing
export interface AggregationSummary {
  table_name: string;
  schema_name: string;
  row_count: number;
  column_count: number;
  profiled_at: string;
  label?: string;
  description?: string;
}

// API response for listing aggregations
export interface AggregationsResponse {
  aggregations: AggregationSummary[];
}

// ============================================
// Chart Data Types
// ============================================

export type AggregationFn = 'sum' | 'avg' | 'count' | 'min' | 'max';

export interface ChartDataRequest {
  table_name: string;
  x_axis: string;
  y_axis: string;
  aggregation_fn: AggregationFn;
  limit?: number;
}

export interface ChartDataResponse {
  x: string[];
  y: number[];
  title: string;
  x_axis_label: string;
  y_axis_label: string;
}

// ============================================
// Aggregate Query Types (dataset-scoped)
// ============================================

export interface AggregateFilter {
  column: string;
  op: 'eq' | 'ne' | 'gt' | 'gte' | 'lt' | 'lte' | 'in' | 'not_in' | 'like' | 'ilike' | 'contains' | 'is_null' | 'is_not_null';
  value?: unknown;
}

export interface AggregateSpec {
  column?: string | null;
  fn: AggregationFn;
}

export interface AggregateRequest {
  table_name: string;
  x?: string | null;
  y?: string | null;
  group_by?: string[];
  filters?: AggregateFilter[];
  agg: AggregateSpec;
  limit?: number;
}

export interface AggregateResponse {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  meta: Record<string, unknown>;
}

// ============================================
// Task-2 Strategy/Decision Types
// ============================================

export interface DecisionReadiness {
  overall_score: number;
  strategy_completeness: number;
  kpi_completeness: number;
  target_completeness: number;
  rule_completeness: number;
  reconciliation_completeness: number;
  data_readiness: number;
  explanation?: string | null;
}

export interface ReadinessFlags {
  kpis_defined: boolean;
  targets_defined: boolean;
  rules_defined: boolean;
  placeholders: string[];
}

export interface CoverageGap {
  kpi_id: string;
  reason: string;
  details?: {
    missing_marts?: string[];
    missing_columns_by_mart?: Record<string, string[]>;
  } | null;
}

export interface DecisionStateResponse {
  revision: string;
  generated_at: string;
  strategy_bundle: Record<string, unknown>;
  kpi_registry: Record<string, unknown>;
  readiness: DecisionReadiness;
  readiness_flags?: ReadinessFlags | null;
  readiness_notes?: string[] | null;
  coverage_gaps: CoverageGap[];
  summaries?: Record<string, unknown> | null;
}

export interface StrategyBundleEditorResponse {
  revision: string;
  mode: "merged";
  bundle: Record<string, unknown>;
  base_yaml: string;
  override_yaml: string;
}

export interface StrategyBundleUpdateRequest {
  expected_revision: string;
  mode: "base" | "override";
  yaml: string;
  author: string;
  reason: string;
}

export interface StrategyContextPayload {
  company: string;
  horizon: string;
  north_star_metric: string;
  narrative?: string | null;
}

export interface StrategyPillarPayload {
  id: string;
  description: string;
  owner?: string | null;
}

export interface StrategySwotPayload {
  strengths: string[];
  weaknesses: string[];
  opportunities: string[];
  threats: string[];
}

export interface StrategyOverviewResponse {
  revision: string;
  strategy_context: StrategyContextPayload;
  pillars: StrategyPillarPayload[];
  swot: StrategySwotPayload | null;
}

export interface StrategyOverviewUpdateRequest {
  expected_revision: string;
  strategy_context: StrategyContextPayload;
  pillars: StrategyPillarPayload[];
  swot: StrategySwotPayload | null;
  author: string;
  reason: string;
}

export interface StrategyKpi {
  id: string;
  description: string;
  formula: string;
  marts: string[];
  required_columns: string[];
  dimensions?: string[];
  default_grain?: string | null;
  pillar_id?: string | null;
  owner?: string | null;
  display_name?: string | null;
  semantic_family?: string | null;
  business_concepts?: string[];
  metric_aliases?: string[];
  preferred_drill_path?: string[];
  mart_drill_overrides?: Record<string, string[]>;
  terminal_dimensions?: string[];
  disallowed_drill_dimensions?: string[];
  preferred_chart_types?: Array<"bar" | "line" | "pie" | "histogram" | "kpi">;
  derived_metrics?: Record<string, string>;
}

export interface StrategyKpiLibraryResponse {
  revision: string;
  kpis: StrategyKpi[];
  available_marts: string[];
  mart_columns: Record<string, string[]>;
}

export interface StrategyKpiUpsertRequest {
  expected_revision: string;
  dataset_id: string;
  kpi: StrategyKpi;
  author: string;
  reason: string;
}

export interface StrategyKpiDeleteRequest {
  expected_revision: string;
  dataset_id: string;
  author: string;
  reason: string;
}

export interface StrategyTarget {
  kpi_id: string;
  target_value: number;
  red_threshold?: number | null;
  yellow_threshold?: number | null;
  direction: "up" | "down";
  owner?: string | null;
  horizon?: string | null;
}

export interface StrategyTargetsResponse {
  revision: string;
  targets: StrategyTarget[];
  available_kpis: string[];
}

export interface StrategyTargetUpsertRequest {
  expected_revision: string;
  target: StrategyTarget;
  author: string;
  reason: string;
}

export interface StrategyTargetDeleteRequest {
  expected_revision: string;
  author: string;
  reason: string;
}

export interface StrategyRule {
  id: string;
  condition: string;
  action: string;
  severity: "info" | "warn" | "block";
  rationale?: string | null;
  ai_suggested?: boolean | null;
  source?: string | null;
}

export interface StrategyRulesResponse {
  revision: string;
  rules: StrategyRule[];
  available_kpis: string[];
}

export interface StrategyWorkspaceStateResponse {
  decision_state: DecisionStateResponse;
  strategy_bundle: StrategyBundleEditorResponse;
  kpi_bundle: StrategyBundleEditorResponse;
  overview: StrategyOverviewResponse;
  targets: StrategyTargetsResponse;
  rules: StrategyRulesResponse;
  kpi_library: StrategyKpiLibraryResponse;
}

export interface StrategyRuleUpsertRequest {
  expected_revision: string;
  rule: StrategyRule;
  author: string;
  reason: string;
}

export interface StrategyRuleDeleteRequest {
  expected_revision: string;
  author: string;
  reason: string;
}

export interface StrategyEvaluationTimeRange {
  column: string;
  from?: string | number | null;
  to?: string | number | null;
}

export interface StrategyEvaluationRequest {
  dataset_id: string;
  filters?: Array<Record<string, unknown>>;
  time_range?: StrategyEvaluationTimeRange | null;
}

export interface StrategyEvaluationKpiResult {
  id: string;
  display_name?: string | null;
  description?: string | null;
  formula?: string | null;
  marts?: string[];
  required_columns?: string[];
  dimensions?: string[];
  default_grain?: string | null;
  pillar_id?: string | null;
  owner?: string | null;
  value: number | null;
  target: number | null;
  variance: number | null;
  status: string;
  computable?: boolean;
  dependency_status?: string;
  provenance?: Record<string, unknown> | null;
}

export interface StrategyEvaluationRuleResult {
  id: string;
  condition: string;
  action: string;
  severity: "info" | "warn" | "block";
  rationale?: string | null;
  affected_kpis?: string[];
}

export interface StrategyEvaluationResponse {
  dataset_id: string;
  revision: string;
  kpis: StrategyEvaluationKpiResult[];
  triggered_rules: StrategyEvaluationRuleResult[];
  evaluation_time: string;
}

export interface StrategyDecisionSignal {
  id: string;
  title: string;
  severity: "critical" | "warn" | "info";
  explanation: string;
  suggested_action: string;
  kpi_id?: string | null;
  kpi_ids?: string[];
  source?: string | null;
}

export interface StrategyDecisionSignalsResponse {
  dataset_id: string;
  revision: string;
  generated_at: string;
  executive_summary: {
    overall_readiness_score: number;
    kpis_on_track: number;
    kpis_warning: number;
    kpis_critical: number;
    triggered_rules: number;
    narrative: string;
  };
  decision_signals: StrategyDecisionSignal[];
  recommendations: string[];
}

export interface StrategyAgentExtractRequest {
  dataset_id: string;
  text: string;
  expected_revision?: string | null;
}

export interface StrategyAgentExtractResponse {
  revision: string;
  candidates: StrategyKpi[];
  notes: string[];
  suggested_patches: Array<Record<string, unknown>>;
  target_suggestions?: Array<Record<string, unknown>>;
  rule_suggestions?: Array<Record<string, unknown>>;
  alias_suggestions?: Record<string, string>;
  derived_metric_suggestions?: Record<string, string>;
}

export interface StrategyAgentReconcileRequest {
  dataset_id: string;
  candidates: StrategyKpi[];
  expected_revision?: string | null;
}

export interface StrategyAgentMissingItem {
  kpi_id: string;
  reason: string;
  details?: {
    missing_marts?: string[];
    missing_columns_by_mart?: Record<string, string[]>;
  } | null;
}

export interface StrategyAgentPatch {
  patch_id: string;
  type: "add_kpi" | "update_formula" | "replace_column" | "set_target" | "add_rule" | "legacy";
  target_id: string;
  before?: Record<string, unknown>;
  after: Record<string, unknown>;
  rationale: string;
  confidence: number;
  source: string;
}

export interface StrategyAgentReconcileResponse {
  revision: string;
  candidates: Array<StrategyKpi & { status?: string }>;
  reconciled: Array<StrategyKpi & { status?: string }>;
  missing: StrategyAgentMissingItem[];
  missing_dependencies: StrategyAgentMissingItem[];
  suggestions: Array<{
    kpi_id: string;
    mart: string;
    missing_column: string;
    suggested_columns: string[];
  }>;
  column_matches: Array<{
    kpi_id: string;
    mart: string;
    missing_column: string;
    suggested_columns: string[];
  }>;
  patches: StrategyAgentPatch[];
}

export interface StrategyAgentApplyRequest {
  dataset_id: string;
  expected_revision: string;
  selected_patch_ids?: string[];
  patches?: StrategyAgentPatch[] | null;
  patch?: Record<string, unknown> | null;
  author: string;
  reason: string;
}

export interface StrategyAgentApplyResponse {
  revision: string;
  previous_revision?: string;
  applied_summary: {
    selected_patch_ids?: string[];
    applied_patch_types?: string[];
    applied_count: number;
    kpi_count: number;
  };
}

export interface StrategyAgentUndoRequest {
  dataset_id: string;
  revision_to_restore: string;
  expected_revision?: string | null;
  author: string;
  reason: string;
}

export interface StrategyAgentUndoResponse {
  revision: string;
  restored_from_revision: string;
}
