export type ChartVersion = "v1";
export type ChartType = "bar" | "line" | "pie" | "histogram" | "kpi";
export type MetricAggregation = "sum" | "avg" | "count" | "min" | "max";
export type FilterOperator = "=" | "!=" | "in" | "between" | ">" | ">=" | "<" | "<=";
export type SortDirection = "asc" | "desc";

export interface ChartVisualSpec {
  type: ChartType;
}

export interface XEncodingSpec {
  field: string;
}

export interface YMetricSpec {
  field: string;
  aggregation: MetricAggregation;
  alias?: string;
}

export interface ChartEncodingSpec {
  x: XEncodingSpec;
  y: YMetricSpec[];
}

export interface FilterSpec {
  field: string;
  op: FilterOperator;
  value: unknown;
}

export interface SortSpec {
  field: string;
  direction: SortDirection;
}

export interface ChartSemanticContext {
  matched_kpi_id?: string | null;
  matched_kpi_label?: string | null;
  semantic_family?: string | null;
  preferred_drill_path?: string[];
  recommendation_source?: string | null;
  mart_hierarchy?: string[];
  terminal_dimensions?: string[];
  chart_family?: string | null;
}

export interface ChartSpecV1 {
  version: ChartVersion;
  dataset_id?: string;
  table: string;
  chart: ChartVisualSpec;
  encoding: ChartEncodingSpec;
  filters?: FilterSpec[];
  sort?: SortSpec[];
  limit?: number;
  semantic_context?: ChartSemanticContext;
}

export interface ChartsPreviewResponse {
  chart_spec: ChartSpecV1;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  meta: Record<string, unknown>;
}
