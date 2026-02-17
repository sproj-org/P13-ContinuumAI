import { create } from 'zustand';

export type DatasetId = string;
export type WorkspaceTab = 'table-profiling' | 'column-profiling' | 'chart-builder';

interface AppState {
  selectedDatasetId: DatasetId;
  setSelectedDatasetId: (datasetId: DatasetId) => void;

  // Dataset selection
  activeDataset: DatasetId | null;
  setActiveDataset: (dataset: DatasetId | null) => void;

  // Workspace state
  selectedAggregation: string | null;
  setSelectedAggregation: (table: string | null) => void;

  selectedColumn: string | null;
  setSelectedColumn: (column: string | null) => void;

  activeTab: WorkspaceTab;
  setActiveTab: (tab: WorkspaceTab) => void;

  // Chart builder state
  chartConfig: ChartConfig;
  setChartConfig: (config: Partial<ChartConfig>) => void;
  resetChartConfig: () => void;
}

export interface ChartConfig {
  chartType: 'bar' | 'line' | 'pie' | 'histogram' | 'kpi';
  xAxis: string | null;
  yAxis: string | null;
  colorBy: string | null;
  aggregationFn: 'sum' | 'avg' | 'count' | 'min' | 'max';
}

const defaultChartConfig: ChartConfig = {
  chartType: 'bar',
  xAxis: null,
  yAxis: null,
  colorBy: null,
  aggregationFn: 'sum',
};

export const useAppStore = create<AppState>((set) => ({
  selectedDatasetId: 'silkroute',
  setSelectedDatasetId: (datasetId) =>
    set({
      selectedDatasetId: datasetId,
      activeDataset: datasetId,
    }),

  // Dataset
  activeDataset: 'silkroute',
  setActiveDataset: (dataset) =>
    set((state) => ({
      activeDataset: dataset,
      selectedDatasetId: dataset ?? state.selectedDatasetId,
    })),

  // Workspace
  selectedAggregation: null,
  setSelectedAggregation: (table) => set({ selectedAggregation: table, selectedColumn: null }),

  selectedColumn: null,
  setSelectedColumn: (column) => set({ selectedColumn: column }),

  activeTab: 'table-profiling',
  setActiveTab: (tab) => set({ activeTab: tab }),

  // Chart builder
  chartConfig: defaultChartConfig,
  setChartConfig: (config) => set((state) => ({ 
    chartConfig: { ...state.chartConfig, ...config } 
  })),
  resetChartConfig: () => set({ chartConfig: defaultChartConfig }),
}));
