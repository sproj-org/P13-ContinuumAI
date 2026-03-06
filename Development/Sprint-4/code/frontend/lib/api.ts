// API client for backend communication

import type {
  AggregateRequest,
  AggregateResponse,
  AggregationsResponse,
  ChartDataRequest,
  ChartDataResponse,
  ColumnProfileAPI,
  DatasetProfileAPI,
} from "./api-types";
import type {
  ChartSpecV1,
  ChartsPreviewResponse,
} from "./types/chartspec";
import type { ChatHintsResponse, ChatRequest, ChatResponse } from "./types/chat";

// const API_URL = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api`;
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export interface User {
  id: number;
  username: string;
  email: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ApiError {
  detail: string;
}

export class ApiRequestError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiRequestError";
  }
}

class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private getToken(): string | null {
    if (typeof globalThis.window === "undefined") return null;
    return localStorage.getItem("access_token");
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const token = this.getToken();
    const headers: HeadersInit = {
      "Content-Type": "application/json",
      ...options.headers,
    };

    if (token) {
      (headers as Record<string, string>).Authorization = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let detail = "An error occurred";
      try {
        const error = (await response.json()) as ApiError;
        detail = error.detail || detail;
      } catch {
        detail = response.statusText || detail;
      }
      throw new ApiRequestError(response.status, detail);
    }

    return response.json();
  }

  private async requestWithFallback<T>(
    datasetEndpoint: string,
    legacyEndpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    try {
      return await this.request<T>(datasetEndpoint, options);
    } catch (error) {
      if (!(error instanceof ApiRequestError) || error.status !== 404) {
        throw error;
      }
      return this.request<T>(legacyEndpoint, options);
    }
  }

  async signup(
    username: string,
    email: string,
    password: string,
    confirmPassword: string
  ): Promise<AuthResponse> {
    return this.request<AuthResponse>("/auth/signup", {
      method: "POST",
      body: JSON.stringify({
        username,
        email,
        password,
        confirm_password: confirmPassword,
      }),
    });
  }

  async login(username: string, password: string): Promise<AuthResponse> {
    return this.request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  }

  async getMe(): Promise<User> {
    return this.request<User>("/auth/me");
  }

  async verifyToken(): Promise<{ valid: boolean; user_id: number }> {
    return this.request<{ valid: boolean; user_id: number }>("/auth/verify", {
      method: "POST",
    });
  }

  // ============================================
  // Profiling Endpoints
  // ============================================

  async getAggregations(datasetId: string): Promise<AggregationsResponse> {
    return this.requestWithFallback<AggregationsResponse>(
      `/datasets/${datasetId}/profiling/aggregations`,
      "/profiling/aggregations"
    );
  }

  async getTableProfile(datasetId: string, tableName: string): Promise<DatasetProfileAPI> {
    return this.requestWithFallback<DatasetProfileAPI>(
      `/datasets/${datasetId}/profiling/aggregations/${tableName}/profile`,
      `/profiling/aggregations/${tableName}/profile`
    );
  }

  async getColumnProfile(
    datasetId: string,
    tableName: string,
    columnName: string
  ): Promise<ColumnProfileAPI> {
    return this.requestWithFallback<ColumnProfileAPI>(
      `/datasets/${datasetId}/profiling/aggregations/${tableName}/columns/${columnName}`,
      `/profiling/aggregations/${tableName}/columns/${columnName}`
    );
  }

  async getChartData(datasetId: string, request: ChartDataRequest): Promise<ChartDataResponse> {
    return this.requestWithFallback<ChartDataResponse>(
      `/datasets/${datasetId}/profiling/chart-data`,
      "/profiling/chart-data",
      {
        method: "POST",
        body: JSON.stringify(request),
      }
    );
  }

  async postChartsPreview(
    datasetId: string,
    chartSpec: ChartSpecV1,
    options?: { debug?: boolean }
  ): Promise<ChartsPreviewResponse> {
    const debug = options?.debug ?? false;
    const body = debug ? { chart_spec: chartSpec, debug: true } : chartSpec;
    return this.request<ChartsPreviewResponse>(`/datasets/${datasetId}/charts/preview`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  async postChat(datasetId: string, request: ChatRequest): Promise<ChatResponse> {
    return this.request<ChatResponse>(`/datasets/${datasetId}/chat`, {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async getChatHints(datasetId: string, table: string): Promise<ChatHintsResponse> {
    return this.request<ChatHintsResponse>(`/datasets/${datasetId}/marts/${table}/chat-hints`);
  }

  // ============================================
  // Aggregate Endpoint
  // ============================================

  async executeAggregate(datasetId: string, request: AggregateRequest): Promise<AggregateResponse> {
    return this.request<AggregateResponse>(`/datasets/${datasetId}/query/aggregate`, {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  // ============================================
  // Saved Charts (Dashboard Persistence)
  // ============================================

  async listSavedCharts(datasetId?: string): Promise<SavedChartAPI[]> {
    const qs = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : "";
    return this.request<SavedChartAPI[]>(`/saved-charts${qs}`);
  }

  async createSavedChart(data: SavedChartCreateAPI): Promise<SavedChartAPI> {
    return this.request<SavedChartAPI>("/saved-charts", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updateSavedChart(chartId: number, data: { title?: string; position?: number }): Promise<SavedChartAPI> {
    return this.request<SavedChartAPI>(`/saved-charts/${chartId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async deleteSavedChart(chartId: number): Promise<void> {
    await this.request<void>(`/saved-charts/${chartId}`, { method: "DELETE" });
  }

  async clearAllSavedCharts(datasetId?: string): Promise<void> {
    const qs = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : "";
    await this.request<void>(`/saved-charts${qs}`, { method: "DELETE" });
  }

  // ============================================
  // Chat Threads (Chat Persistence)
  // ============================================

  async listChatThreads(): Promise<ChatThreadAPI[]> {
    return this.request<ChatThreadAPI[]>("/chat-threads");
  }

  async upsertChatThread(data: ChatThreadUpsertAPI): Promise<ChatThreadAPI> {
    return this.request<ChatThreadAPI>("/chat-threads", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async deleteChatThread(threadKey: string): Promise<void> {
    await this.request<void>(`/chat-threads/${encodeURIComponent(threadKey)}`, {
      method: "DELETE",
    });
  }

  async clearAllChatThreads(): Promise<void> {
    await this.request<void>("/chat-threads", { method: "DELETE" });
  }
}

export interface SavedChartAPI {
  id: number;
  dataset_id: string;
  mart_id: string;
  title: string;
  chart_spec: Record<string, unknown>;
  rows: Record<string, unknown>[];
  position: number;
  created_at: string;
}

export interface SavedChartCreateAPI {
  dataset_id: string;
  mart_id: string;
  title: string;
  chart_spec: Record<string, unknown>;
  rows: Record<string, unknown>[];
  position?: number;
}

export interface ChatThreadAPI {
  id: number;
  thread_key: string;
  turns: Record<string, unknown>[];
  chat_state: Record<string, unknown> | null;
  last_chart_spec: Record<string, unknown> | null;
  saved_prompts: string[];
  chat_mode: string;
  updated_at: string;
}

export interface ChatThreadUpsertAPI {
  thread_key: string;
  turns: Record<string, unknown>[];
  chat_state: Record<string, unknown> | null;
  last_chart_spec: Record<string, unknown> | null;
  saved_prompts: string[];
  chat_mode: string;
}

export const apiClient = new ApiClient(API_URL);
