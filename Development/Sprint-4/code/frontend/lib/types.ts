// Column roles
export type ColumnRole = 'dimension' | 'measure' | 'temporal';

// Column profile metadata
export interface ColumnProfile {
  name: string;
  role: ColumnRole;
  dataType: string;
  nullPercentage: number;
  uniqueCount: number;
  totalCount: number;
  
  // Dimension-specific
  topValues?: { value: string; count: number }[];
  cardinality?: 'low' | 'medium' | 'high';
  
  // Measure-specific
  min?: number;
  max?: number;
  mean?: number;
  median?: number;
  outlierCount?: number;
  histogram?: { bin: string; count: number }[];
  
  // Temporal-specific
  minDate?: string;
  maxDate?: string;
  granularity?: 'day' | 'week' | 'month' | 'year';
  timeSeriesData?: { date: string; count: number }[];

  // Suggestions
  suggestedCharts?: SuggestedChart[];
}

export interface SuggestedChart {
  type: 'bar' | 'line' | 'pie' | 'histogram';
  title: string;
  xAxis?: string;
  yAxis?: string;
}

// Table profile
export interface TableProfile {
  tableName: string;
  rowCount: number;
  columnCount: number;
  missingPercentage: number;
  lastUpdated: string;
  
  // Data quality
  duplicateRows: number;
  hasOutliers: boolean;
  
  // Column distribution
  columnRoleDistribution: {
    dimensions: number;
    measures: number;
    temporal: number;
  };
  
  // Columns
  columns: ColumnProfile[];
  
  // Insights
  keyInsights: string[];
  suggestedQuestions: string[];
}

// Chart query and response
export interface ChartQuery {
  aggregation: string;
  x: string;
  y: string;
  aggregationFn: 'sum' | 'avg' | 'count' | 'min' | 'max';
  chartType: 'bar' | 'line' | 'pie' | 'histogram' | 'kpi';
  colorBy?: string;
}

export interface ChartResponse {
  chartType: string;
  data: {
    x: (string | number)[];
    y: number[];
    colors?: string[];
  };
  layout: {
    title: string;
    xaxis?: { title: string };
    yaxis?: { title: string };
  };
}

// Dataset info
export interface DatasetInfo {
  id: string;
  name: string;
  status: 'ready' | 'loading' | 'error';
  tables: string[];
  description?: string;
}
