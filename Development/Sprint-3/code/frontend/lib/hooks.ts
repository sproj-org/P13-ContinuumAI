/**
 * React Query hooks for profiling data
 */

import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from './api';
import type {
  DatasetProfileAPI,
  ColumnProfileAPI,
  AggregationsResponse,
  ChartSpec,
  AggregateResponse,
} from './api-types';

/**
 * Fetch list of available aggregation tables
 */
export function useAggregations(datasetId: string) {
  return useQuery<AggregationsResponse, Error>({
    queryKey: ['aggregations', datasetId],
    queryFn: () => apiClient.getAggregations(datasetId),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Fetch full profile for a specific table
 */
export function useTableProfile(datasetId: string, tableName: string | null) {
  return useQuery<DatasetProfileAPI, Error>({
    queryKey: ['tableProfile', datasetId, tableName],
    queryFn: () => apiClient.getTableProfile(datasetId, tableName!),
    enabled: !!tableName,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Fetch detailed profile for a specific column
 */
export function useColumnProfile(
  datasetId: string,
  tableName: string | null,
  columnName: string | null
) {
  return useQuery<ColumnProfileAPI, Error>({
    queryKey: ['columnProfile', datasetId, tableName, columnName],
    queryFn: () => apiClient.getColumnProfile(datasetId, tableName!, columnName!),
    enabled: !!tableName && !!columnName,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Execute a ChartSpec via the new aggregate pipeline.
 * Uses a mutation because it's an imperative POST action.
 */
export function useExecuteChartSpec(datasetId: string) {
  return useMutation<AggregateResponse, Error, ChartSpec>({
    mutationFn: (spec: ChartSpec) =>
      apiClient.executeChartSpec(datasetId, spec),
  });
}
