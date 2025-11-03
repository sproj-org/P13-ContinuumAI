// Mock API Service for Development (replaces backend calls)

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

// Mock user storage (in real app, this would be in backend database)
const mockUsers: Array<UserResponse & { password: string }> = [
  {
    user_id: 1,
    username: 'demo',
    email: 'demo@continuumai.com',
    password: 'password123',
    role: 'user',
    created_at: new Date().toISOString(),
    is_active: true
  }
];

// Simulate network delay
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// Register new user
export async function registerUser(data: RegisterData): Promise<UserResponse> {
  await delay(800); // Simulate network delay
  
  // Check if user already exists
  const existingUser = mockUsers.find(
    user => user.username === data.username || user.email === data.email
  );
  
  if (existingUser) {
    throw new ApiError(400, 'User with this username or email already exists');
  }
  
  // Create new user
  const newUser = {
    user_id: mockUsers.length + 1,
    username: data.username,
    email: data.email,
    password: data.password,
    role: 'user',
    created_at: new Date().toISOString(),
    is_active: true
  };
  
  mockUsers.push(newUser);
  
  // Return user without password
  const { password, ...userResponse } = newUser;
  return userResponse;
}

// Login user
export async function loginUser(data: LoginData): Promise<AuthResponse> {
  await delay(600); // Simulate network delay
  
  // Find user by username or email
  const user = mockUsers.find(
    u => (u.username === data.username_or_email || u.email === data.username_or_email) 
         && u.password === data.password
  );
  
  if (!user) {
    throw new ApiError(401, 'Invalid credentials');
  }
  
  if (!user.is_active) {
    throw new ApiError(401, 'Account is deactivated');
  }
  
  // Generate mock token
  const token = `mock_token_${user.user_id}_${Date.now()}`;
  
  return {
    access_token: token,
    token_type: 'bearer'
  };
}

// Get current user
export async function getCurrentUser(token: string): Promise<UserResponse> {
  await delay(300); // Simulate network delay
  
  // Extract user ID from mock token
  const tokenParts = token.split('_');
  if (tokenParts.length < 3 || tokenParts[0] !== 'mock' || tokenParts[1] !== 'token') {
    throw new ApiError(401, 'Invalid token');
  }
  
  const userId = parseInt(tokenParts[2]);
  const user = mockUsers.find(u => u.user_id === userId);
  
  if (!user) {
    throw new ApiError(401, 'User not found');
  }
  
  // Return user without password
  const { password, ...userResponse } = user;
  return userResponse;
}
