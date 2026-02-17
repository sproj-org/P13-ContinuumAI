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

  // ============================================
  // Aggregate Endpoint
  // ============================================

  async executeAggregate(datasetId: string, request: AggregateRequest): Promise<AggregateResponse> {
    return this.request<AggregateResponse>(`/datasets/${datasetId}/query/aggregate`, {
      method: "POST",
      body: JSON.stringify(request),
    });
  }
}

export const apiClient = new ApiClient(API_URL);
