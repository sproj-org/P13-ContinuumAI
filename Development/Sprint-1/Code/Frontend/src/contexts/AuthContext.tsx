'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { loginUser, registerUser, getCurrentUser, LoginData, RegisterData, UserResponse } from '@/lib/api';

interface AuthContextType {
  user: UserResponse | null;
  token: string | null;
  isLoading: boolean;
  login: (data: LoginData) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load token from localStorage on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('access_token');
    if (storedToken) {
      setToken(storedToken);
      // Fetch user data with the token
      getCurrentUser(storedToken)
        .then(setUser)
        .catch(() => {
          // Token is invalid, clear it
          localStorage.removeItem('access_token');
          setToken(null);
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = async (data: LoginData) => {
    const response = await loginUser(data);
    const { access_token } = response;
    
    // Store token
    localStorage.setItem('access_token', access_token);
    setToken(access_token);
    
    // Fetch user data
    const userData = await getCurrentUser(access_token);
    setUser(userData);
  };

  const register = async (data: RegisterData) => {
    // Just register the user, don't auto-login
    await registerUser(data);
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
