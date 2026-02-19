/**
 * React Query hooks for profiling data
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient } from './api';
import type {
  DatasetProfileAPI,
  ColumnProfileAPI,
  AggregationsResponse,
  ChartDataResponse,
  AggregationFn,
} from './api-types';
import type { ChartSpecV1, ChartsPreviewResponse } from "./types/chartspec";

function stableSerialize(value: unknown): string {
  if (value === null || value === undefined) {
    return "null";
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableSerialize(item)).join(",")}]`;
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => `${JSON.stringify(key)}:${stableSerialize(item)}`);
    return `{${entries.join(",")}}`;
  }
  return JSON.stringify(value);
}

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
 * Fetch real chart data from the database.
 * Only executes when all required parameters are provided.
 */
export function useChartData(
  datasetId: string,
  tableName: string | null,
  xAxis: string | null,
  yAxis: string | null,
  aggregationFn: AggregationFn,
  limit: number = 20
) {
  return useQuery<ChartDataResponse, Error>({
    queryKey: ['chartData', datasetId, tableName, xAxis, yAxis, aggregationFn, limit],
    queryFn: () => apiClient.getChartData(datasetId, {
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

export function useChartsPreview(datasetId: string, chartSpec: ChartSpecV1 | null, debug: boolean = false) {
  const fingerprint = chartSpec ? stableSerialize(chartSpec) : "";
  return useQuery<ChartsPreviewResponse, Error>({
    queryKey: ["chartsPreview", datasetId, fingerprint, debug],
    queryFn: () => apiClient.postChartsPreview(datasetId, chartSpec!, { debug }),
    enabled: !!datasetId && !!chartSpec,
    staleTime: 1 * 60 * 1000,
  });
}
