"use client";

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
} from "react";
import { useRouter } from "next/navigation";
import { apiClient, User, AuthResponse } from "@/lib/api";
import { rehydrateStore } from "@/lib/store";
import { getQueryClient } from "@/lib/query-provider";

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  signup: (
    username: string,
    email: string,
    password: string,
    confirmPassword: string
  ) => Promise<void>;
  logout: () => void;
  error: string | null;
  clearError: () => void;
}

interface AuthProviderProps {
  readonly children: React.ReactNode;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Check authentication status on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem("access_token");
      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        const userData = await apiClient.getMe();
        setUser(userData);
      } catch {
        // Token is invalid, clear it
        localStorage.removeItem("access_token");
        localStorage.removeItem("user");
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, []);

  const handleAuthSuccess = useCallback((response: AuthResponse) => {
    localStorage.setItem("access_token", response.access_token);
    localStorage.setItem("user", JSON.stringify(response.user));
    setUser(response.user);
    setError(null);
    // Clear React Query cache so no stale data from the previous user leaks
    getQueryClient()?.clear();
    // Rehydrate Zustand from the new user's localStorage bucket
    rehydrateStore();
    router.push("/dashboard");
  }, [router]);

  const login = useCallback(async (username: string, password: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.login(username, password);
      handleAuthSuccess(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [handleAuthSuccess]);

  const signup = useCallback(async (
    username: string,
    email: string,
    password: string,
    confirmPassword: string
  ) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.signup(
        username,
        email,
        password,
        confirmPassword
      );
      handleAuthSuccess(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [handleAuthSuccess]);

  const logout = useCallback(() => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    // Clear React Query cache so next user starts fresh
    getQueryClient()?.clear();
    // Rehydrate store — with no user, falls back to empty defaults
    rehydrateStore();
    setUser(null);
    router.push("/");
  }, [router]);

  const value = useMemo<AuthContextType>(() => ({
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    signup,
    logout,
    error,
    clearError,
  }), [user, isLoading, login, signup, logout, error, clearError]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
