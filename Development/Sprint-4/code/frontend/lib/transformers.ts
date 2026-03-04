/**
 * Transformers to convert backend API data to frontend-friendly formats
 */

import type { 
  ColumnProfileAPI, 
  DatasetProfileAPI, 
  Role,
  NumericStats,
  CategoricalStats,
  DatetimeStats,
  TopKItem
} from './api-types';

// Frontend column role (simplified from backend's Role enum)
export type ColumnRole = 'dimension' | 'measure' | 'temporal';

/**
 * Map backend role to frontend display role
 */
export function mapRoleToDisplay(role: Role): ColumnRole {
  switch (role) {
    case 'measure':
      return 'measure';
    case 'datetime':
      return 'temporal';
    case 'id':
    case 'dimension':
    case 'boolean':
    case 'text':
    default:
      return 'dimension';
  }
}

/**
 * Get column role distribution from profile
 */
export function getColumnRoleDistribution(profile: DatasetProfileAPI): { 
  dimensions: number; 
  measures: number; 
  temporal: number;
} {
  const distribution = { dimensions: 0, measures: 0, temporal: 0 };
  
  for (const col of profile.columns) {
    const role = mapRoleToDisplay(col.effective_role);
    if (role === 'dimension') distribution.dimensions++;
    else if (role === 'measure') distribution.measures++;
    else if (role === 'temporal') distribution.temporal++;
  }
  
  return distribution;
}

/**
 * Calculate overall missing percentage for table
 */
export function calculateTableMissingPercentage(profile: DatasetProfileAPI): number {
  if (profile.columns.length === 0 || profile.row_count === 0) return 0;
  
  const totalNulls = profile.columns.reduce((sum, col) => sum + col.null_count, 0);
  const totalCells = profile.row_count * profile.column_count;
  
  return totalCells > 0 ? (totalNulls / totalCells) * 100 : 0;
}

/**
 * Convert null_fraction (0-1) to percentage (0-100)
 */
export function nullFractionToPercentage(fraction: number): number {
  return fraction * 100;
}

/**
 * Get top values from column stats (for categorical columns)
 */
export function getTopValues(column: ColumnProfileAPI): TopKItem[] {
  if (column.stats?.kind === 'categorical') {
    return (column.stats as CategoricalStats).top_k || [];
  }
  if (column.stats?.kind === 'text') {
    return column.stats.top_k || [];
  }
  return [];
}

/**
 * Get numeric stats from column
 */
export function getNumericStats(column: ColumnProfileAPI): NumericStats | null {
  if (column.stats?.kind === 'numeric') {
    return column.stats as NumericStats;
  }
  return null;
}

/**
 * Get datetime stats from column
 */
export function getDatetimeStats(column: ColumnProfileAPI): DatetimeStats | null {
  if (column.stats?.kind === 'datetime') {
    return column.stats as DatetimeStats;
  }
  return null;
}

/**
 * Generate key insights from profile data
 */
export function generateInsights(profile: DatasetProfileAPI): string[] {
  const insights: string[] = [];
  
  // High null columns
  const highNullCols = profile.columns.filter(c => c.null_fraction > 0.1);
  if (highNullCols.length > 0) {
    const names = highNullCols.slice(0, 3).map(c => c.name).join(', ');
    insights.push(`${highNullCols.length} column(s) have >10% missing values: ${names}`);
  }
  
  // Unique columns (potential keys)
  const uniqueCols = profile.columns.filter(c => c.is_unique);
  if (uniqueCols.length > 0) {
    insights.push(`${uniqueCols.length} column(s) contain unique values (potential keys)`);
  }
  
  // Dominant values in categorical columns
  for (const col of profile.columns) {
    const topValues = getTopValues(col);
    if (topValues.length > 0 && topValues[0].percent > 0.5) {
      insights.push(
        `"${topValues[0].value}" dominates ${col.name} (${(topValues[0].percent * 100).toFixed(0)}%)`
      );
    }
    if (insights.length >= 5) break;
  }
  
  // High cardinality dimensions
  const highCardDimensions = profile.columns.filter(
    c => mapRoleToDisplay(c.effective_role) === 'dimension' && 
         c.cardinality_bucket === 'high' &&
         c.effective_role !== 'id'
  );
  if (highCardDimensions.length > 0) {
    insights.push(`${highCardDimensions.length} dimension(s) have high cardinality`);
  }
  
  return insights.slice(0, 5);
}

/**
 * Generate suggested questions based on profile
 */
export function generateSuggestedQuestions(profile: DatasetProfileAPI): string[] {
  const questions: string[] = [];
  
  const measures = profile.columns.filter(c => mapRoleToDisplay(c.effective_role) === 'measure');
  const dimensions = profile.columns.filter(c => mapRoleToDisplay(c.effective_role) === 'dimension');
  const temporals = profile.columns.filter(c => mapRoleToDisplay(c.effective_role) === 'temporal');
  
  // Measure by dimension questions
  if (measures.length > 0 && dimensions.length > 0) {
    const measure = measures[0];
    const dimension = dimensions.find(d => d.effective_role === 'dimension') || dimensions[0];
    questions.push(`How does ${measure.name} vary by ${dimension.name}?`);
  }
  
  // Time trend questions
  if (measures.length > 0 && temporals.length > 0) {
    questions.push(`What is the trend of ${measures[0].name} over time?`);
  }
  
  // Distribution questions
  if (measures.length > 0) {
    questions.push(`What is the distribution of ${measures[0].name}?`);
  }
  
  // Comparison questions
  if (dimensions.length >= 2) {
    const dim1 = dimensions[0];
    const dim2 = dimensions[1];
    questions.push(`How do ${dim1.name} and ${dim2.name} relate?`);
  }
  
  // Top performers
  if (measures.length > 0 && dimensions.length > 0) {
    questions.push(`Which ${dimensions[0].name} has the highest ${measures[0].name}?`);
  }
  
  return questions.slice(0, 4);
}

/**
 * Generate suggested charts for a column
 */
export function generateSuggestedCharts(
  column: ColumnProfileAPI, 
  allColumns: ColumnProfileAPI[]
): Array<{ type: string; title: string; xAxis: string; yAxis?: string }> {
  const charts: Array<{ type: string; title: string; xAxis: string; yAxis?: string }> = [];
  const role = mapRoleToDisplay(column.effective_role);
  
  if (role === 'dimension') {
    // Pie chart for low cardinality
    if (column.cardinality_bucket === 'low') {
      charts.push({
        type: 'pie',
        title: `Distribution of ${column.name}`,
        xAxis: column.name,
      });
    }
    
    // Bar chart with a measure
    const measures = allColumns.filter(c => mapRoleToDisplay(c.effective_role) === 'measure');
    if (measures.length > 0) {
      charts.push({
        type: 'bar',
        title: `${measures[0].name} by ${column.name}`,
        xAxis: column.name,
        yAxis: measures[0].name,
      });
    }
  }
  
  if (role === 'measure') {
    // Histogram
    charts.push({
      type: 'histogram',
      title: `Distribution of ${column.name}`,
      xAxis: column.name,
    });
    
    // Line chart over time
    const temporals = allColumns.filter(c => mapRoleToDisplay(c.effective_role) === 'temporal');
    if (temporals.length > 0) {
      charts.push({
        type: 'line',
        title: `${column.name} over Time`,
        xAxis: temporals[0].name,
        yAxis: column.name,
      });
    }
  }
  
  if (role === 'temporal') {
    // Time series
    const measures = allColumns.filter(c => mapRoleToDisplay(c.effective_role) === 'measure');
    if (measures.length > 0) {
      charts.push({
        type: 'line',
        title: `${measures[0].name} over ${column.name}`,
        xAxis: column.name,
        yAxis: measures[0].name,
      });
    }
  }
  
  return charts.slice(0, 3);
}

/**
 * Format datetime string for display
 */
export function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'N/A';
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString();
  } catch {
    return dateStr;
  }
}

/**
 * Format number for display
 */
export function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return 'N/A';
  return value.toLocaleString(undefined, { maximumFractionDigits: decimals });
}

/**
 * Get display-friendly data type
 */
export function getDisplayDataType(column: ColumnProfileAPI): string {
  const physical = column.physical_type;
  const logical = column.logical_type;
  
  if (physical === 'datetime' || physical === 'date') {
    return physical;
  }
  if (physical === 'float' || physical === 'int') {
    return logical === 'numeric' ? 'number' : physical;
  }
  return physical;
}

/**
 * Frontend-friendly column profile type
 */
export interface TransformedColumnProfile {
  name: string;
  role: ColumnRole;
  dataType: string;
  nullPercentage: number;
  uniqueCount: number;
  totalCount: number;
  cardinality: 'low' | 'medium' | 'high' | null;
  
  // For dimension columns
  topValues: Array<{ value: string; count: number; percent: number }>;
  
  // For measure columns
  min: number | null;
  max: number | null;
  mean: number | null;
  median: number | null;
  stddev: number | null;
  
  // For temporal columns
  minDate: string | null;
  maxDate: string | null;
  distinctDays: number | null;
  
  // Metadata
  isUnique: boolean;
  sampleValues: string[];
}

/**
 * Transform API column profile to frontend format
 */
export function transformColumnProfile(column: ColumnProfileAPI): TransformedColumnProfile {
  const role = mapRoleToDisplay(column.effective_role);
  const stats = column.stats;
  
  // Extract stats based on kind
  let topValues: Array<{ value: string; count: number; percent: number }> = [];
  let min: number | null = null;
  let max: number | null = null;
  let mean: number | null = null;
  let median: number | null = null;
  let stddev: number | null = null;
  let minDate: string | null = null;
  let maxDate: string | null = null;
  let distinctDays: number | null = null;
  
  if (stats) {
    if (stats.kind === 'categorical') {
      topValues = stats.top_k.map(item => ({
        value: item.value,
        count: item.count,
        percent: item.percent,
      }));
    } else if (stats.kind === 'text') {
      topValues = stats.top_k.map(item => ({
        value: item.value,
        count: item.count,
        percent: item.percent,
      }));
    } else if (stats.kind === 'numeric') {
      min = stats.min;
      max = stats.max;
      mean = stats.mean;
      median = stats.p50;
      stddev = stats.stddev;
    } else if (stats.kind === 'datetime') {
      minDate = stats.min;
      maxDate = stats.max;
      distinctDays = stats.distinct_days;
    }
  }
  
  return {
    name: column.name,
    role,
    dataType: getDisplayDataType(column),
    nullPercentage: column.null_fraction * 100,
    uniqueCount: column.distinct_count,
    totalCount: column.row_count,
    cardinality: column.cardinality_bucket,
    topValues,
    min,
    max,
    mean,
    median,
    stddev,
    minDate,
    maxDate,
    distinctDays,
    isUnique: column.is_unique,
    sampleValues: column.sample_values,
  };
}

/**
 * Transform all columns in a profile
 */
export function transformAllColumns(profile: DatasetProfileAPI): TransformedColumnProfile[] {
  return profile.columns.map(transformColumnProfile);
}
