// API client for backend communication

import type {
  AggregateRequest,
  AggregateResponse,
  AggregationsResponse,
  ChartDataRequest,
  ChartDataResponse,
  ColumnProfileAPI,
  DatasetProfileAPI,
  DecisionStateResponse,
  StrategyBundleEditorResponse,
  StrategyAgentExtractRequest,
  StrategyAgentExtractResponse,
  StrategyAgentReconcileRequest,
  StrategyAgentReconcileResponse,
  StrategyOverviewResponse,
  StrategyOverviewUpdateRequest,
  StrategyKpiDeleteRequest,
  StrategyKpiLibraryResponse,
  StrategyKpiUpsertRequest,
  StrategyBundleUpdateRequest,
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
  detail: string | { code?: string; message?: string; hint?: string };
}

export class ApiRequestError extends Error {
  status: number;
  code?: string;
  hint?: string;

  constructor(status: number, message: string, options?: { code?: string; hint?: string }) {
    super(message);
    this.status = status;
    this.code = options?.code;
    this.hint = options?.hint;
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
      let errorCode: string | undefined = undefined;
      let errorHint: string | undefined = undefined;
      try {
        const error = (await response.json()) as ApiError;
        if (typeof error.detail === "string") {
          detail = error.detail || detail;
        } else if (error.detail && typeof error.detail === "object") {
          detail = error.detail.message || detail;
          errorCode = error.detail.code;
          errorHint = error.detail.hint;
        }
      } catch {
        detail = response.statusText || detail;
      }
      throw new ApiRequestError(response.status, detail, { code: errorCode, hint: errorHint });
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
  // Task-2 Strategy/Decision Endpoints
  // ============================================

  async getDecisionState(datasetId: string): Promise<DecisionStateResponse> {
    return this.request<DecisionStateResponse>(`/decision/state?dataset_id=${encodeURIComponent(datasetId)}`);
  }

  async getStrategyBundle(): Promise<StrategyBundleEditorResponse> {
    return this.request<StrategyBundleEditorResponse>("/strategy/bundle");
  }

  async putStrategyBundle(payload: StrategyBundleUpdateRequest): Promise<StrategyBundleEditorResponse> {
    return this.request<StrategyBundleEditorResponse>("/strategy/bundle", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }

  async getStrategyOverview(): Promise<StrategyOverviewResponse> {
    return this.request<StrategyOverviewResponse>("/strategy/overview");
  }

  async putStrategyOverview(payload: StrategyOverviewUpdateRequest): Promise<StrategyOverviewResponse> {
    return this.request<StrategyOverviewResponse>("/strategy/overview", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }

  async getKpiRegistryBundle(): Promise<StrategyBundleEditorResponse> {
    return this.request<StrategyBundleEditorResponse>("/kpi-registry/bundle");
  }

  async putKpiRegistryBundle(payload: StrategyBundleUpdateRequest): Promise<StrategyBundleEditorResponse> {
    return this.request<StrategyBundleEditorResponse>("/kpi-registry/bundle", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }

  async getStrategyKpis(datasetId: string): Promise<StrategyKpiLibraryResponse> {
    return this.request<StrategyKpiLibraryResponse>(`/strategy/kpis?dataset_id=${encodeURIComponent(datasetId)}`);
  }

  async createStrategyKpi(payload: StrategyKpiUpsertRequest): Promise<StrategyKpiLibraryResponse> {
    return this.request<StrategyKpiLibraryResponse>("/strategy/kpis", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async updateStrategyKpi(kpiId: string, payload: StrategyKpiUpsertRequest): Promise<StrategyKpiLibraryResponse> {
    return this.request<StrategyKpiLibraryResponse>(`/strategy/kpis/${encodeURIComponent(kpiId)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }

  async deleteStrategyKpi(kpiId: string, payload: StrategyKpiDeleteRequest): Promise<StrategyKpiLibraryResponse> {
    return this.request<StrategyKpiLibraryResponse>(`/strategy/kpis/${encodeURIComponent(kpiId)}`, {
      method: "DELETE",
      body: JSON.stringify(payload),
    });
  }

  async extractStrategyKpis(payload: StrategyAgentExtractRequest): Promise<StrategyAgentExtractResponse> {
    return this.request<StrategyAgentExtractResponse>("/strategy/agent/extract-kpis", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async reconcileStrategyKpis(payload: StrategyAgentReconcileRequest): Promise<StrategyAgentReconcileResponse> {
    return this.request<StrategyAgentReconcileResponse>("/strategy/agent/reconcile", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }
}

export const apiClient = new ApiClient(API_URL);
