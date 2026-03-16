/**
 * React Query hooks for profiling data
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './api';
import type {
  SavedChartAPI,
  SavedChartCreateAPI,
  ChatThreadAPI,
  ChatThreadUpsertAPI,
  UserDashboardAPI,
  UserDashboardCreateAPI,
  UserDashboardUpdateAPI,
} from './api';
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

// ============================================
// Saved Charts (Dashboard Persistence)
// ============================================

/**
 * Fetch all saved charts for the current user, optionally filtered by dataset.
 */
export function useSavedCharts(datasetId?: string, dashboardName?: string) {
  return useQuery<SavedChartAPI[], Error>({
    queryKey: ['savedCharts', datasetId ?? 'all', dashboardName ?? 'all-dashboards'],
    queryFn: () => apiClient.listSavedCharts(datasetId, dashboardName),
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Mutation: create a saved chart on the backend.
 */
export function useCreateSavedChart() {
  const queryClient = useQueryClient();
  return useMutation<SavedChartAPI, Error, SavedChartCreateAPI>({
    mutationFn: (data) => apiClient.createSavedChart(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['savedCharts'] });
    },
  });
}

/**
 * Mutation: update a saved chart (title or position).
 */
export function useUpdateSavedChart() {
  const queryClient = useQueryClient();
  return useMutation<SavedChartAPI, Error, { chartId: number; data: { title?: string; dashboard_name?: string; position?: number } }>({
    mutationFn: ({ chartId, data }) => apiClient.updateSavedChart(chartId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['savedCharts'] });
    },
  });
}

/**
 * Mutation: delete a single saved chart.
 */
export function useDeleteSavedChart() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, number>({
    mutationFn: (chartId) => apiClient.deleteSavedChart(chartId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['savedCharts'] });
    },
  });
}

/**
 * Mutation: clear all saved charts for a dataset.
 */
export function useClearSavedCharts() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string | undefined>({
    mutationFn: (datasetId) => apiClient.clearAllSavedCharts(datasetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['savedCharts'] });
    },
  });
}

// ============================================
// Dashboards (Named Dashboard Management)
// ============================================

export function useDashboards(datasetId?: string) {
  return useQuery<UserDashboardAPI[], Error>({
    queryKey: ['dashboards', datasetId ?? 'all'],
    queryFn: () => apiClient.listDashboards(datasetId),
    staleTime: 30 * 1000,
  });
}

export function useCreateDashboard() {
  const queryClient = useQueryClient();
  return useMutation<UserDashboardAPI, Error, UserDashboardCreateAPI>({
    mutationFn: (data) => apiClient.createDashboard(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboards'] });
      queryClient.invalidateQueries({ queryKey: ['savedCharts'] });
    },
  });
}

export function useRenameDashboard() {
  const queryClient = useQueryClient();
  return useMutation<UserDashboardAPI, Error, { dashboardId: number; data: UserDashboardUpdateAPI }>({
    mutationFn: ({ dashboardId, data }) => apiClient.renameDashboard(dashboardId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboards'] });
      queryClient.invalidateQueries({ queryKey: ['savedCharts'] });
    },
  });
}

export function useDeleteDashboard() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, number>({
    mutationFn: (dashboardId) => apiClient.deleteDashboard(dashboardId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboards'] });
      queryClient.invalidateQueries({ queryKey: ['savedCharts'] });
    },
  });
}

// ============================================
// Chat Threads (Chat Persistence)
// ============================================

/**
 * Fetch all chat threads for the current user.
 */
export function useChatThreads() {
  return useQuery<ChatThreadAPI[], Error>({
    queryKey: ['chatThreads'],
    queryFn: () => apiClient.listChatThreads(),
    staleTime: 30 * 1000,
  });
}

/**
 * Mutation: upsert (create/update) a chat thread.
 */
export function useUpsertChatThread() {
  const queryClient = useQueryClient();
  return useMutation<ChatThreadAPI, Error, ChatThreadUpsertAPI>({
    mutationFn: (data) => apiClient.upsertChatThread(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatThreads'] });
    },
  });
}

/**
 * Mutation: delete a single chat thread by key.
 */
export function useDeleteChatThread() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (threadKey) => apiClient.deleteChatThread(threadKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatThreads'] });
    },
  });
}

/**
 * Mutation: clear all chat threads.
 */
export function useClearChatThreads() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, void>({
    mutationFn: () => apiClient.clearAllChatThreads(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatThreads'] });
    },
  });
}
