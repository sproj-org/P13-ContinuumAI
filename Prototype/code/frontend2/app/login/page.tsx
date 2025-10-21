'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000';

export default function LoginPage() {
  const router = useRouter();
  const sp = useSearchParams();
  const next = sp.get('next') || '/';

  const [email, setEmail] = useState('demo@continuum.ai');
  const [password, setPassword] = useState('demo123');
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function login(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      const emailNorm = email.trim().toLowerCase();
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email: emailNorm, password }),
      });
      if (!res.ok) throw new Error('Invalid credentials');
      const data = await res.json();
      document.cookie = `access=${encodeURIComponent(data.access_token)}; Path=/; SameSite=Lax`;
      router.replace(next);
    } catch (e: any) {
      setErr('Invalid email or password');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen grid place-items-center bg-neutral-100 text-neutral-900 dark:bg-neutral-900 dark:text-neutral-100">
      <form
        onSubmit={login}
        className="w-full max-w-sm rounded-2xl bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 shadow-lg p-6 space-y-5"
      >
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-50">
          Sign in
        </h1>

        {err && (
          <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg px-3 py-2">
            {err}
          </div>
        )}

        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-neutral-800 dark:text-neutral-200">
            Email
          </label>
          <input
            className="w-full rounded-lg border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-800
                       text-neutral-900 dark:text-neutral-100 placeholder-neutral-400 dark:placeholder-neutral-500
                       px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            autoComplete="username"
            inputMode="email"
          />
        </div>

        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-neutral-800 dark:text-neutral-200">
            Password
          </label>
          <input
            type="password"
            className="w-full rounded-lg border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-800
                       text-neutral-900 dark:text-neutral-100 placeholder-neutral-400 dark:placeholder-neutral-500
                       px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
          />
        </div>

        <button
          disabled={loading}
          className="w-full rounded-lg py-2.5 font-medium text-white bg-blue-600 hover:bg-blue-700
                     disabled:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-600
                     dark:focus:ring-offset-neutral-900"
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
        
        <p className="text-sm text-neutral-600 dark:text-neutral-400">
        Don’t have an account?{' '}
        <a className="text-blue-600 hover:underline" href="/signup">
            Create one
        </a>
        </p>

      </form>
    </div>
  );
}
