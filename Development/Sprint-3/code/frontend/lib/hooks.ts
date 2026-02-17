/**
 * React Query hooks for profiling data
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient } from './api';
import type { 
  DatasetProfileAPI, 
  ColumnProfileAPI, 
  AggregationsResponse,
  ChartDataRequest,
  ChartDataResponse,
  AggregationFn,
} from './api-types';

/**
 * Fetch list of available aggregation tables
 */
export function useAggregations() {
  return useQuery<AggregationsResponse, Error>({
    queryKey: ['aggregations'],
    queryFn: () => apiClient.getAggregations(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Fetch full profile for a specific table
 */
export function useTableProfile(tableName: string | null) {
  return useQuery<DatasetProfileAPI, Error>({
    queryKey: ['tableProfile', tableName],
    queryFn: () => apiClient.getTableProfile(tableName!),
    enabled: !!tableName,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Fetch detailed profile for a specific column
 */
export function useColumnProfile(tableName: string | null, columnName: string | null) {
  return useQuery<ColumnProfileAPI, Error>({
    queryKey: ['columnProfile', tableName, columnName],
    queryFn: () => apiClient.getColumnProfile(tableName!, columnName!),
    enabled: !!tableName && !!columnName,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Fetch real chart data from the database.
 * Only executes when all required parameters are provided.
 */
export function useChartData(
  tableName: string | null,
  xAxis: string | null,
  yAxis: string | null,
  aggregationFn: AggregationFn,
  limit: number = 20
) {
  return useQuery<ChartDataResponse, Error>({
    queryKey: ['chartData', tableName, xAxis, yAxis, aggregationFn, limit],
    queryFn: () => apiClient.getChartData({
      table_name: tableName!,
      x_axis: xAxis!,
      y_axis: yAxis!,
      aggregation_fn: aggregationFn,
      limit,
    }),
    enabled: !!tableName && !!xAxis && !!yAxis,
    staleTime: 1 * 60 * 1000, // 1 minute (shorter for chart data)
  });
}
