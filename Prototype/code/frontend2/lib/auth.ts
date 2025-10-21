// Central place for token refresh + axios instance with interceptors.
// No React context; doesn’t touch your existing components.

import axios, { AxiosError } from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000';
let accessToken: string | null = null;

// Attempt to bootstrap from cookie (so hard refresh keeps you logged-in)
export function getAccessFromCookie(): string | null {
  if (typeof document === 'undefined') return null;
  const m = document.cookie.match(/(?:^|; )access=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}
accessToken = getAccessFromCookie();

export function setAccessToken(token: string | null) {
  accessToken = token;
  if (typeof document !== 'undefined') {
    if (token) {
      // short-lived cookie for SSR/middleware checks
      document.cookie = `access=${encodeURIComponent(token)}; Path=/; SameSite=Lax`;
    } else {
      document.cookie = 'access=; Max-Age=0; Path=/';
    }
  }
}

async function refreshAccess(): Promise<string> {
  const res = await fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    credentials: 'include', // send refresh cookie
  });
  if (!res.ok) throw new Error('refresh failed');
  const data = await res.json();
  setAccessToken(data.access_token);
  return data.access_token as string;
}

// Axios instance used by your existing API client
export const axiosAuth = axios.create({
  baseURL: API_BASE,
  withCredentials: true,  // so refresh cookie flows
});

// Attach Authorization automatically
axiosAuth.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers = config.headers ?? {};
    (config.headers as any)['Authorization'] = `Bearer ${accessToken}`;
  }
  return config;
});

// On 401, transparently refresh once and retry
let refreshing = false;
let waiters: Array<(t: string) => void> = [];

function waitForToken(): Promise<string> {
  return new Promise((resolve) => waiters.push(resolve));
}

axiosAuth.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config!;
    const status = error.response?.status;

    if (status === 401) {
      try {
        if (!refreshing) {
          refreshing = true;
          const newTok = await refreshAccess();
          waiters.forEach(w => w(newTok));
          waiters = [];
          refreshing = false;
        } else {
          await new Promise<void>((res) => {
            waiters.push(() => res());
          });
        }
        original.headers = original.headers ?? {};
        (original.headers as Record<string, string>)['Authorization'] = `Bearer ${accessToken}`;
        return axiosAuth(original);
      } catch {
        setAccessToken(null);
      }
    }
    return Promise.reject(error);
  }
);

export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
  } catch {}
  // clear access token & cookie so middleware will redirect on next nav
  setAccessToken(null);
}
