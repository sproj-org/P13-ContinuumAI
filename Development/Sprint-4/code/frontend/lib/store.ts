import { create } from 'zustand';
import { createJSONStorage, persist, type StateStorage } from 'zustand/middleware';
import type { ChartSpecV1 } from './types/chartspec';
import type { ChatResponse } from './types/chat';

export type DatasetId = string;
export type WorkspaceTab = 'marts' | 'chart-builder' | 'dashboard';

export interface SavedChart {
  id: string;
  title: string;
  chartSpec: ChartSpecV1;
  rows: any[];
  datasetId: string;
  martId: string;
  createdAt: string;
}

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

export type ChatMode = 'auto' | 'chart' | 'explain';
export type TimeGrain = 'day' | 'week' | 'month' | 'quarter' | 'year';
export type MetricAggregation = 'sum' | 'avg' | 'count' | 'min' | 'max';

export interface ChatSelectionsState {
  metric: string | null;
  dimension: string | null;
  temporal: string | null;
  time_grain: TimeGrain | null;
  aggregation: MetricAggregation | null;
  limit: number | null;
}

export interface ChatThreadState {
  clarify_id: string | null;
  selections: ChatSelectionsState;
  original_user_intent: string | null;
}

export interface SavedPromptsState {
  [key: string]: string[];
}

interface AppState {
  selectedDatasetId: DatasetId;
  setSelectedDatasetId: (datasetId: DatasetId) => void;

  // Saved charts for dashboard
  savedCharts: SavedChart[];
  saveChart: (chart: Omit<SavedChart, 'id' | 'createdAt'>) => void;
  updateChartTitle: (chartId: string, newTitle: string) => void;
  removeSavedChart: (chartId: string) => void;
  clearSavedCharts: () => void;

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
  chatStateByKey: Record<string, ChatThreadState>;
  savedPromptsByKey: SavedPromptsState;
  appendChatTurn: (key: string, turn: ChatTurn) => void;
  setChatTurns: (key: string, turns: ChatTurn[]) => void;
  clearChat: (key: string) => void;
  setLastChartSpec: (key: string, spec: ChartSpecV1 | null) => void;
  setChatState: (key: string, state: ChatThreadState) => void;
  patchChatState: (
    key: string,
    patch: Partial<Omit<ChatThreadState, 'selections'>> & {
      selections?: Partial<ChatSelectionsState>;
    }
  ) => void;
  chatMode: ChatMode;
  setChatMode: (mode: ChatMode) => void;
  addSavedPrompt: (key: string, prompt: string) => void;
  removeSavedPrompt: (key: string, prompt: string) => void;
  clearSavedPrompts: (key: string) => void;
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

type PersistedAppState = {
  selectedAggregation?: string | null;
  chatTurnsByKey?: Record<string, unknown>;
  lastChartSpecByKey?: Record<string, unknown>;
  chatStateByKey?: Record<string, unknown>;
  chatMode?: ChatMode;
  savedPromptsByKey?: Record<string, unknown>;
};

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === 'string');
}

function normalizeMissingValues(value: unknown): Array<'metric' | 'x_axis' | 'time_grain' | 'table'> {
  if (!Array.isArray(value)) {
    return [];
  }
  const normalized: Array<'metric' | 'x_axis' | 'time_grain' | 'table'> = [];
  for (const item of value) {
    if (typeof item !== 'string') {
      continue;
    }
    const lower = item.trim().toLowerCase();
    const mapped = lower === 'dimension' || lower === 'temporal' ? 'x_axis' : lower;
    if (
      (mapped === 'metric' || mapped === 'x_axis' || mapped === 'time_grain' || mapped === 'table') &&
      !normalized.includes(mapped)
    ) {
      normalized.push(mapped);
    }
  }
  return normalized;
}

function asTimeGrainArray(value: unknown): TimeGrain[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const output: TimeGrain[] = [];
  for (const item of value) {
    if (item === 'day' || item === 'week' || item === 'month' || item === 'quarter' || item === 'year') {
      output.push(item);
    }
  }
  return output;
}

function sanitizeChatResponse(raw: unknown): ChatResponse | null {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const record = raw as Record<string, unknown>;
  const responseType = record.response_type;
  if (typeof responseType !== 'string') {
    return null;
  }
  const meta = typeof record.meta === 'object' && record.meta !== null ? (record.meta as Record<string, unknown>) : {};
  const usedFallback = typeof record.used_fallback === 'boolean' ? record.used_fallback : undefined;
  const openaiConfigured = typeof record.openai_configured === 'boolean' ? record.openai_configured : undefined;
  const fallbackReason: 'missing_key' | 'openai_error' | undefined =
    record.fallback_reason === 'missing_key' || record.fallback_reason === 'openai_error'
      ? record.fallback_reason
      : undefined;
  const debugMetadata = {
    used_fallback: usedFallback,
    openai_configured: openaiConfigured,
    fallback_reason: fallbackReason,
  };

  if (responseType === 'clarify') {
    const optionsRaw = record.options;
    const optionsRecord = typeof optionsRaw === 'object' && optionsRaw !== null ? (optionsRaw as Record<string, unknown>) : {};
    const clarifyId =
      typeof record.clarify_id === 'string' && record.clarify_id.trim().length > 0
        ? record.clarify_id
        : 'legacy';
    const question =
      typeof record.question === 'string'
        ? record.question
        : typeof record.message === 'string'
        ? record.message
        : 'Could you clarify your request?';
    return {
      response_type: 'clarify',
      clarify_id: clarifyId,
      question,
      missing: normalizeMissingValues(record.missing),
      options: {
        metrics: asStringArray(optionsRecord.metrics),
        dimensions: asStringArray(optionsRecord.dimensions),
        temporals: asStringArray(optionsRecord.temporals),
        time_grains: asTimeGrainArray(optionsRecord.time_grains),
      },
      meta,
      ...debugMetadata,
    };
  }

  if (responseType === 'refuse' && typeof record.message === 'string') {
    return {
      response_type: 'refuse',
      message: record.message,
      meta,
      ...debugMetadata,
    };
  }

  if (responseType === 'explain' && typeof record.message === 'string') {
    return {
      response_type: 'explain',
      message: record.message,
      citations: asStringArray(record.citations),
      meta,
      ...debugMetadata,
    };
  }

  if (responseType === 'chart_patch' && typeof record.patch === 'object' && record.patch !== null) {
    return {
      response_type: 'chart_patch',
      patch: record.patch as Record<string, unknown>,
      narrative: typeof record.narrative === 'string' ? record.narrative : undefined,
      meta,
      ...debugMetadata,
    };
  }

  if (
    responseType === 'chart' &&
    typeof record.chart_spec === 'object' &&
    record.chart_spec !== null &&
    Array.isArray(record.columns) &&
    Array.isArray(record.rows) &&
    typeof record.narrative === 'string'
  ) {
    return {
      response_type: 'chart',
      chart_spec: record.chart_spec as unknown as ChartSpecV1,
      columns: record.columns.filter((item): item is string => typeof item === 'string'),
      rows: record.rows.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null),
      narrative: record.narrative,
      meta,
      ...debugMetadata,
    };
  }

  return null;
}

function sanitizePersistedTurns(raw: unknown): Record<string, ChatTurn[]> {
  if (!raw || typeof raw !== 'object') {
    return {};
  }
  const byKey = raw as Record<string, unknown>;
  const sanitized: Record<string, ChatTurn[]> = {};

  for (const [key, turnsRaw] of Object.entries(byKey)) {
    if (!Array.isArray(turnsRaw)) {
      continue;
    }
    const turns: ChatTurn[] = [];
    for (const turnRaw of turnsRaw) {
      if (!turnRaw || typeof turnRaw !== 'object') {
        continue;
      }
      const turn = turnRaw as Record<string, unknown>;
      const role = turn.role;
      const message = turn.message;
      if ((role !== 'user' && role !== 'assistant') || typeof message !== 'string' || !message.trim()) {
        continue;
      }
      const createdAt =
        typeof turn.createdAt === 'string' && turn.createdAt.trim()
          ? turn.createdAt
          : new Date(0).toISOString();

      let response: ChatResponse | null | undefined = undefined;
      if (role === 'assistant' && turn.response !== undefined && turn.response !== null) {
        response = sanitizeChatResponse(turn.response);
        if (!response) {
          // Drop only this malformed assistant turn.
          continue;
        }
      }

      turns.push({
        role,
        message,
        response,
        createdAt,
      });
    }
    sanitized[key] = turns;
  }

  return sanitized;
}

function asNullableString(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value : null;
}

function asNullableNumber(value: unknown): number | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return null;
  }
  return Math.max(1, Math.min(5000, Math.round(value)));
}

function sanitizeChatSelections(raw: unknown): ChatSelectionsState {
  if (!raw || typeof raw !== 'object') {
    return {
      metric: null,
      dimension: null,
      temporal: null,
      time_grain: null,
      aggregation: null,
      limit: null,
    };
  }
  const record = raw as Record<string, unknown>;
  const timeGrain = record.time_grain;
  const aggregation = record.aggregation;
  return {
    metric: asNullableString(record.metric),
    dimension: asNullableString(record.dimension),
    temporal: asNullableString(record.temporal),
    time_grain:
      timeGrain === 'day' || timeGrain === 'week' || timeGrain === 'month' || timeGrain === 'quarter' || timeGrain === 'year'
        ? timeGrain
        : null,
    aggregation:
      aggregation === 'sum' ||
      aggregation === 'avg' ||
      aggregation === 'count' ||
      aggregation === 'min' ||
      aggregation === 'max'
        ? aggregation
        : null,
    limit: asNullableNumber(record.limit),
  };
}

function sanitizePersistedChatState(raw: unknown): Record<string, ChatThreadState> {
  if (!raw || typeof raw !== 'object') {
    return {};
  }
  const byKey = raw as Record<string, unknown>;
  const sanitized: Record<string, ChatThreadState> = {};
  for (const [key, item] of Object.entries(byKey)) {
    if (!item || typeof item !== 'object') {
      continue;
    }
    const record = item as Record<string, unknown>;
    sanitized[key] = {
      clarify_id: asNullableString(record.clarify_id),
      selections: sanitizeChatSelections(record.selections),
      original_user_intent: asNullableString(record.original_user_intent),
    };
  }
  return sanitized;
}

function sanitizePersistedSavedPrompts(raw: unknown): SavedPromptsState {
  if (!raw || typeof raw !== 'object') {
    return {};
  }
  const byKey = raw as Record<string, unknown>;
  const sanitized: SavedPromptsState = {};
  for (const [key, value] of Object.entries(byKey)) {
    if (!Array.isArray(value)) {
      continue;
    }
    const prompts = value
      .filter((item): item is string => typeof item === 'string')
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
    if (prompts.length) {
      sanitized[key] = Array.from(new Set(prompts.map((item) => item.toLowerCase()))).map(
        (lower) => prompts.find((item) => item.toLowerCase() === lower) as string
      );
    }
  }
  return sanitized;
}

const defaultChatThreadState: ChatThreadState = {
  clarify_id: null,
  selections: {
    metric: null,
    dimension: null,
    temporal: null,
    time_grain: null,
    aggregation: null,
    limit: null,
  },
  original_user_intent: null,
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

      // Saved charts for dashboard
      savedCharts: [],
      saveChart: (chart) =>
        set((state) => ({
          savedCharts: [
            ...state.savedCharts,
            {
              ...chart,
              id: `chart-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              createdAt: new Date().toISOString(),
            },
          ],
        })),
      updateChartTitle: (chartId, newTitle) =>
        set((state) => ({
          savedCharts: state.savedCharts.map((c) =>
            c.id === chartId ? { ...c, title: newTitle } : c
          ),
        })),
      removeSavedChart: (chartId) =>
        set((state) => ({
          savedCharts: state.savedCharts.filter((c) => c.id !== chartId),
        })),
      clearSavedCharts: () => set({ savedCharts: [] }),

      // Workspace
      selectedAggregation: null,
      setSelectedAggregation: (table) => set({ selectedAggregation: table, selectedColumn: null }),
      availableMarts: [],
      setAvailableMarts: (marts) => set({ availableMarts: marts }),

      selectedColumn: null,
      setSelectedColumn: (column) => set({ selectedColumn: column }),

      activeTab: 'marts',
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
      chatStateByKey: {},
      savedPromptsByKey: {},
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
          const nextChatState = { ...state.chatStateByKey };
          delete nextTurns[key];
          delete nextSpecs[key];
          delete nextChatState[key];
          return {
            chatTurnsByKey: nextTurns,
            lastChartSpecByKey: nextSpecs,
            chatStateByKey: nextChatState,
          };
        }),
      setLastChartSpec: (key, spec) =>
        set((state) => ({
          lastChartSpecByKey: {
            ...state.lastChartSpecByKey,
            [key]: spec,
          },
        })),
      setChatState: (key, threadState) =>
        set((state) => ({
          chatStateByKey: {
            ...state.chatStateByKey,
            [key]: {
              clarify_id: threadState.clarify_id,
              selections: {
                ...defaultChatThreadState.selections,
                ...threadState.selections,
              },
              original_user_intent: threadState.original_user_intent,
            },
          },
        })),
      patchChatState: (key, patch) =>
        set((state) => {
          const current = state.chatStateByKey[key] ?? defaultChatThreadState;
          return {
            chatStateByKey: {
              ...state.chatStateByKey,
              [key]: {
                clarify_id:
                  patch.clarify_id === undefined ? current.clarify_id : patch.clarify_id,
                original_user_intent:
                  patch.original_user_intent === undefined
                    ? current.original_user_intent
                    : patch.original_user_intent,
                selections: {
                  ...current.selections,
                  ...(patch.selections ?? {}),
                },
              },
            },
          };
        }),
      chatMode: 'auto',
      setChatMode: (mode) => set({ chatMode: mode }),
      addSavedPrompt: (key, prompt) =>
        set((state) => {
          const trimmed = prompt.trim();
          if (!trimmed) {
            return state;
          }
          const existing = state.savedPromptsByKey[key] ?? [];
          const normalized = trimmed.toLowerCase();
          if (existing.some((item) => item.toLowerCase() === normalized)) {
            return state;
          }
          return {
            savedPromptsByKey: {
              ...state.savedPromptsByKey,
              [key]: [trimmed, ...existing].slice(0, 20),
            },
          };
        }),
      removeSavedPrompt: (key, prompt) =>
        set((state) => {
          const existing = state.savedPromptsByKey[key] ?? [];
          const normalized = prompt.toLowerCase();
          const next = existing.filter((item) => item.toLowerCase() !== normalized);
          if (next.length === 0) {
            const clone = { ...state.savedPromptsByKey };
            delete clone[key];
            return { savedPromptsByKey: clone };
          }
          return {
            savedPromptsByKey: {
              ...state.savedPromptsByKey,
              [key]: next,
            },
          };
        }),
      clearSavedPrompts: (key) =>
        set((state) => {
          const clone = { ...state.savedPromptsByKey };
          delete clone[key];
          return { savedPromptsByKey: clone };
        }),
    }),
    {
      name: 'continuumai-app-store',
      version: 5,
      storage: createJSONStorage(() => (typeof window !== 'undefined' ? localStorage : noopStorage)),
      migrate: (persistedState: unknown, version: number) => {
        const state = (persistedState ?? {}) as PersistedAppState;
        if (version >= 5) {
          return {
            ...state,
            chatTurnsByKey: sanitizePersistedTurns(state.chatTurnsByKey),
            chatStateByKey: sanitizePersistedChatState(state.chatStateByKey),
            savedPromptsByKey: sanitizePersistedSavedPrompts(state.savedPromptsByKey),
          };
        }
        return {
          ...state,
          chatTurnsByKey: sanitizePersistedTurns(state.chatTurnsByKey),
          lastChartSpecByKey:
            state.lastChartSpecByKey && typeof state.lastChartSpecByKey === 'object'
              ? (state.lastChartSpecByKey as Record<string, ChartSpecV1 | null>)
              : {},
          chatStateByKey: sanitizePersistedChatState(state.chatStateByKey),
          chatMode: state.chatMode === 'chart' || state.chatMode === 'explain' ? state.chatMode : 'auto',
          savedPromptsByKey: sanitizePersistedSavedPrompts(state.savedPromptsByKey),
        };
      },
      partialize: (state) => ({
        selectedAggregation: state.selectedAggregation,
        chatTurnsByKey: state.chatTurnsByKey,
        lastChartSpecByKey: state.lastChartSpecByKey,
        chatStateByKey: state.chatStateByKey,
        chatMode: state.chatMode,
        savedPromptsByKey: state.savedPromptsByKey,
      }),
    }
  )
);
