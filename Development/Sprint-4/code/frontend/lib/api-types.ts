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
  kpi_coverage: number;
  rule_readiness: number;
  hierarchy_readiness: number;
  data_readiness: number;
  explanation?: string | null;
}

export interface ReadinessFlags {
  kpis_defined: boolean;
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

export interface StrategyAgentReconcileResponse {
  revision: string;
  reconciled: Array<StrategyKpi & { status?: string }>;
  missing: StrategyAgentMissingItem[];
  suggestions: Array<{
    kpi_id: string;
    mart: string;
    missing_column: string;
    suggested_columns: string[];
  }>;
}
