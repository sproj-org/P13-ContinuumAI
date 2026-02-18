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

export interface ChartSpecV1 {
  version: ChartVersion;
  dataset_id?: string;
  table: string;
  chart: ChartVisualSpec;
  encoding: ChartEncodingSpec;
  filters?: FilterSpec[];
  sort?: SortSpec[];
  limit?: number;
}

export interface ChartsPreviewResponse {
  chart_spec: ChartSpecV1;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  meta: Record<string, unknown>;
}

export interface ChatRequest {
  message: string;
  table: string;
  state?: Record<string, unknown>;
}

export interface ChatResponse {
  response_type: "chart" | string;
  chart_spec: ChartSpecV1;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  narrative: string;
  meta: Record<string, unknown>;
}
