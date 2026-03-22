import { create } from 'zustand';
import { createJSONStorage, persist, type StateStorage } from 'zustand/middleware';
import type { ChartSpecV1 } from './types/chartspec';
import type { ChatResponse, QuerySpec, QuerySpecFilter } from './types/chat';

export type DatasetId = string;
export type WorkspaceTab = 'marts' | 'chart-builder' | 'dashboard' | 'strategy';

export interface SavedChart {
  id: string;
  backendId?: number;  // DB primary key for persistence
  title: string;
  dashboardName: string;
  chartSpec: ChartSpecV1;
  rows: Array<Record<string, unknown>>;
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
  hydrateSavedCharts: (charts: SavedChart[]) => void;

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

  /** Bulk-load chat threads from the backend, replacing local state. */
  hydrateChatThreads: (threads: {
    thread_key: string;
    turns: ChatTurn[];
    chat_state: ChatThreadState | null;
    last_chart_spec: ChartSpecV1 | null;
    saved_prompts: string[];
    chat_mode: ChatMode;
  }[]) => void;

  /** Wipe all persisted state (call on logout) */
  resetStore: () => void;
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

// ── Per-user storage adapter ─────────────────────────────
// Reads the logged-in user ID from localStorage and namespaces
// the Zustand persistence key so each user gets isolated state.
function getUserId(): number | null {
  if (typeof globalThis.window === 'undefined') return null;
  try {
    const raw = localStorage.getItem('user');
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return typeof parsed?.id === 'number' ? parsed.id : null;
  } catch {
    return null;
  }
}

const userScopedStorage: StateStorage = {
  getItem: (name: string) => {
    if (typeof globalThis.window === 'undefined') return null;
    const uid = getUserId();
    const key = uid !== null ? `${name}-user-${uid}` : name;
    return localStorage.getItem(key);
  },
  setItem: (name: string, value: string) => {
    if (typeof globalThis.window === 'undefined') return;
    const uid = getUserId();
    const key = uid !== null ? `${name}-user-${uid}` : name;
    localStorage.setItem(key, value);
  },
  removeItem: (name: string) => {
    if (typeof globalThis.window === 'undefined') return;
    const uid = getUserId();
    const key = uid !== null ? `${name}-user-${uid}` : name;
    localStorage.removeItem(key);
  },
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

function sanitizeQuerySpecFilter(raw: unknown): QuerySpecFilter | null {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const record = raw as Record<string, unknown>;
  if (typeof record.field !== 'string' || typeof record.op !== 'string') {
    return null;
  }
  const out: QuerySpecFilter = {
    field: record.field,
    op: record.op,
  };
  if (record.value !== undefined) {
    out.value = record.value;
  }
  return out;
}

function sanitizeQuerySpec(raw: unknown): QuerySpec | null {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const record = raw as Record<string, unknown>;
  const filters = Array.isArray(record.filters)
    ? record.filters
        .map((item) => sanitizeQuerySpecFilter(item))
        .filter((item): item is QuerySpecFilter => item !== null)
    : [];
  const chartType =
    record.chart_type === 'bar' ||
    record.chart_type === 'line' ||
    record.chart_type === 'pie' ||
    record.chart_type === 'histogram' ||
    record.chart_type === 'kpi'
      ? record.chart_type
      : null;
  const timeGrain =
    record.time_grain === 'day' ||
    record.time_grain === 'week' ||
    record.time_grain === 'month' ||
    record.time_grain === 'quarter' ||
    record.time_grain === 'year'
      ? record.time_grain
      : null;
  const aggregation =
    record.aggregation === 'sum' ||
    record.aggregation === 'avg' ||
    record.aggregation === 'count' ||
    record.aggregation === 'min' ||
    record.aggregation === 'max'
      ? record.aggregation
      : null;
  return {
    dataset_id: asNullableString(record.dataset_id),
    table: asNullableString(record.table),
    chart_type: chartType,
    measures: asStringArray(record.measures),
    dimensions: asStringArray(record.dimensions),
    time_field: asNullableString(record.time_field),
    aggregation,
    time_grain: timeGrain,
    filters,
    limit: asNullableNumber(record.limit),
  };
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
  const openaiErrorType = typeof record.openai_error_type === 'string' ? record.openai_error_type : undefined;
  const openaiStatusCode = typeof record.openai_status_code === 'number' ? record.openai_status_code : null;
  const openaiErrorHint = typeof record.openai_error_hint === 'string' ? record.openai_error_hint : null;
  const debugMetadata = {
    used_fallback: usedFallback,
    openai_configured: openaiConfigured,
    fallback_reason: fallbackReason,
    openai_error_type: openaiErrorType,
    openai_status_code: openaiStatusCode,
    openai_error_hint: openaiErrorHint,
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
      query_spec: sanitizeQuerySpec(record.query_spec),
      ...debugMetadata,
    };
  }

  if (responseType === 'refuse' && typeof record.message === 'string') {
    return {
      response_type: 'refuse',
      message: record.message,
      meta,
      query_spec: sanitizeQuerySpec(record.query_spec),
      ...debugMetadata,
    };
  }

  if (responseType === 'explain' && typeof record.message === 'string') {
    return {
      response_type: 'explain',
      message: record.message,
      citations: asStringArray(record.citations),
      meta,
      query_spec: sanitizeQuerySpec(record.query_spec),
      ...debugMetadata,
    };
  }

  if (responseType === 'chart_patch' && typeof record.patch === 'object' && record.patch !== null) {
    return {
      response_type: 'chart_patch',
      patch: record.patch as Record<string, unknown>,
      narrative: typeof record.narrative === 'string' ? record.narrative : undefined,
      meta,
      query_spec: sanitizeQuerySpec(record.query_spec),
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
      query_spec: sanitizeQuerySpec(record.query_spec),
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
      hydrateSavedCharts: (charts) => set({ savedCharts: charts }),

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
          const nextPrompts = { ...state.savedPromptsByKey };
          delete nextTurns[key];
          delete nextSpecs[key];
          delete nextChatState[key];
          delete nextPrompts[key];
          return {
            chatTurnsByKey: nextTurns,
            lastChartSpecByKey: nextSpecs,
            chatStateByKey: nextChatState,
            savedPromptsByKey: nextPrompts,
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

      hydrateChatThreads: (threads) =>
        set(() => {
          const nextTurns: Record<string, ChatTurn[]> = {};
          const nextSpecs: Record<string, ChartSpecV1 | null> = {};
          const nextChatState: Record<string, ChatThreadState> = {};
          const nextPrompts: SavedPromptsState = {};
          let mode: ChatMode = 'auto';
          for (const t of threads) {
            nextTurns[t.thread_key] = t.turns;
            nextSpecs[t.thread_key] = t.last_chart_spec;
            if (t.chat_state) {
              nextChatState[t.thread_key] = t.chat_state;
            }
            if (t.saved_prompts.length > 0) {
              nextPrompts[t.thread_key] = t.saved_prompts;
            }
            // Use the mode from the most recent thread
            if (t.chat_mode === 'chart' || t.chat_mode === 'explain' || t.chat_mode === 'auto') {
              mode = t.chat_mode;
            }
          }
          return {
            chatTurnsByKey: nextTurns,
            lastChartSpecByKey: nextSpecs,
            chatStateByKey: nextChatState,
            savedPromptsByKey: nextPrompts,
            chatMode: mode,
          };
        }),

      resetStore: () =>
        set({
          activeTab: 'marts',
          selectedAggregation: null,
          savedCharts: [],
          chatTurnsByKey: {},
          lastChartSpecByKey: {},
          chatStateByKey: {},
          chatMode: 'auto' as ChatMode,
          savedPromptsByKey: {},
        }),
    }),
    {
      name: 'continuumai-app-store',
      version: 5,
      storage: createJSONStorage(() => userScopedStorage),
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
        activeTab: state.activeTab,
        selectedAggregation: state.selectedAggregation,
        savedCharts: state.savedCharts,
        chatTurnsByKey: state.chatTurnsByKey,
        lastChartSpecByKey: state.lastChartSpecByKey,
        chatStateByKey: state.chatStateByKey,
        chatMode: state.chatMode,
        savedPromptsByKey: state.savedPromptsByKey,
      }),
    }
  )
);

/**
 * Call after login/logout so the store rehydrates from the
 * correct per-user localStorage bucket.
 */
export function rehydrateStore() {
  // Reset in-memory state to defaults first
  useAppStore.getState().resetStore();
  // Then rehydrate from the (now user-scoped) storage
  useAppStore.persist.rehydrate();
}
