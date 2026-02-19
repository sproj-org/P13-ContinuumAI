import { create } from 'zustand';
import { createJSONStorage, persist, type StateStorage } from 'zustand/middleware';
import type { ChartSpecV1 } from './types/chartspec';
import type { ChatResponse } from './types/chat';

export type DatasetId = string;
export type WorkspaceTab = 'table-profiling' | 'column-profiling' | 'chart-builder' | 'chat';

export interface AvailableMart {
  id: string;
  label?: string;
  description?: string;
}

export interface ChatTurn {
  role: 'user' | 'assistant';
  message: string;
  response?: ChatResponse | null;
  createdAt: string;
}

interface AppState {
  selectedDatasetId: DatasetId;
  setSelectedDatasetId: (datasetId: DatasetId) => void;

  // Dataset selection
  activeDataset: DatasetId | null;
  setActiveDataset: (dataset: DatasetId | null) => void;

  // Workspace state
  selectedAggregation: string | null;
  setSelectedAggregation: (table: string | null) => void;
  availableMarts: AvailableMart[];
  setAvailableMarts: (marts: AvailableMart[]) => void;

  selectedColumn: string | null;
  setSelectedColumn: (column: string | null) => void;

  activeTab: WorkspaceTab;
  setActiveTab: (tab: WorkspaceTab) => void;

  // Chart builder state
  chartConfig: ChartConfig;
  setChartConfig: (config: Partial<ChartConfig>) => void;
  resetChartConfig: () => void;

  // Chat state (persisted by dataset+mart key)
  chatTurnsByKey: Record<string, ChatTurn[]>;
  lastChartSpecByKey: Record<string, ChartSpecV1 | null>;
  appendChatTurn: (key: string, turn: ChatTurn) => void;
  setChatTurns: (key: string, turns: ChatTurn[]) => void;
  clearChat: (key: string) => void;
  setLastChartSpec: (key: string, spec: ChartSpecV1 | null) => void;
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

const noopStorage: StateStorage = {
  getItem: () => null,
  setItem: () => undefined,
  removeItem: () => undefined,
};

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
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
      availableMarts: [],
      setAvailableMarts: (marts) => set({ availableMarts: marts }),

      selectedColumn: null,
      setSelectedColumn: (column) => set({ selectedColumn: column }),

      activeTab: 'table-profiling',
      setActiveTab: (tab) => set({ activeTab: tab }),

      // Chart builder
      chartConfig: defaultChartConfig,
      setChartConfig: (config) =>
        set((state) => ({
          chartConfig: { ...state.chartConfig, ...config },
        })),
      resetChartConfig: () => set({ chartConfig: defaultChartConfig }),

      // Chat persistence
      chatTurnsByKey: {},
      lastChartSpecByKey: {},
      appendChatTurn: (key, turn) =>
        set((state) => ({
          chatTurnsByKey: {
            ...state.chatTurnsByKey,
            [key]: [...(state.chatTurnsByKey[key] ?? []), turn],
          },
        })),
      setChatTurns: (key, turns) =>
        set((state) => ({
          chatTurnsByKey: {
            ...state.chatTurnsByKey,
            [key]: turns,
          },
        })),
      clearChat: (key) =>
        set((state) => {
          const nextTurns = { ...state.chatTurnsByKey };
          const nextSpecs = { ...state.lastChartSpecByKey };
          delete nextTurns[key];
          delete nextSpecs[key];
          return {
            chatTurnsByKey: nextTurns,
            lastChartSpecByKey: nextSpecs,
          };
        }),
      setLastChartSpec: (key, spec) =>
        set((state) => ({
          lastChartSpecByKey: {
            ...state.lastChartSpecByKey,
            [key]: spec,
          },
        })),
    }),
    {
      name: 'continuumai-app-store',
      storage: createJSONStorage(() => (typeof window !== 'undefined' ? localStorage : noopStorage)),
      partialize: (state) => ({
        selectedAggregation: state.selectedAggregation,
        chatTurnsByKey: state.chatTurnsByKey,
        lastChartSpecByKey: state.lastChartSpecByKey,
      }),
    }
  )
);
