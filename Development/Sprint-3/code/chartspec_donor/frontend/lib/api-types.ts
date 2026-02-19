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
