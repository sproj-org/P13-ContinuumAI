// API client for backend communication

import type { 
  DatasetProfileAPI, 
  ColumnProfileAPI, 
  AggregationsResponse,
  ChartDataRequest,
  ChartDataResponse,
} from './api-types';

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

class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private getToken(): string | null {
    if (typeof globalThis.window === "undefined") return null;
    return localStorage.getItem("access_token");
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    const headers: HeadersInit = {
      "Content-Type": "application/json",
      ...options.headers,
    };

    if (token) {
      (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error: ApiError = await response.json();
      throw new Error(error.detail || "An error occurred");
    }

    return response.json();
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

  /**
   * Get list of available aggregation tables (mart_sales, mart_customers, mart_stores)
   */
  async getAggregations(): Promise<AggregationsResponse> {
    return this.request<AggregationsResponse>("/profiling/aggregations");
  }

  /**
   * Get full profile for a specific aggregation table
   */
  async getTableProfile(tableName: string): Promise<DatasetProfileAPI> {
    return this.request<DatasetProfileAPI>(`/profiling/aggregations/${tableName}/profile`);
  }

  /**
   * Get detailed profile for a specific column
   */
  async getColumnProfile(tableName: string, columnName: string): Promise<ColumnProfileAPI> {
    return this.request<ColumnProfileAPI>(`/profiling/aggregations/${tableName}/columns/${columnName}`);
  }

  // ============================================
  // Chart Data Endpoints
  // ============================================

  /**
   * Get aggregated chart data from the database
   */
  async getChartData(request: ChartDataRequest): Promise<ChartDataResponse> {
    return this.request<ChartDataResponse>("/profiling/chart-data", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }
}

export const apiClient = new ApiClient(API_URL);
