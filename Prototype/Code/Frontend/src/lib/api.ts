// API Service for Backend Communication

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export interface RegisterData {
  username: string;
  email: string;
  password: string;
}

export interface LoginData {
  username_or_email: string;
  password: string;
}

export interface UserResponse {
  user_id: number;
  username: string;
  email: string;
  role: string;
  created_at: string;
  is_active: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

// Register new user
export async function registerUser(data: RegisterData): Promise<UserResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new ApiError(response.status, error.detail || 'Registration failed');
  }

  return response.json();
}

// Login user
export async function loginUser(data: LoginData): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new ApiError(response.status, error.detail || 'Login failed');
  }

  return response.json();
}

// Get current user
export async function getCurrentUser(token: string): Promise<UserResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new ApiError(response.status, error.detail || 'Failed to get user');
  }

  return response.json();
}
