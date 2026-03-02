"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import Noise from "@/components/Noise";
import TargetCursor from "@/components/TargetCursor";
import ElectricBorder from "@/components/ElectricBorder";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login, error, clearError, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  // Clear errors on mount and unmount
  useEffect(() => {
    clearError();
    return () => clearError();
  }, [clearError]);

  // Redirect if already authenticated
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.push("/dashboard");
    }
  }, [isAuthenticated, isLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError("");
    clearError();

    if (!username || !password) {
      setLocalError("Please fill in all fields");
      return;
    }

    setIsSubmitting(true);

    try {
      await login(username, password);
    } catch {
      // Error is handled by the auth context
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="h-screen w-screen overflow-hidden flex items-center justify-center bg-white">
        <div className="text-lg text-slate-900">Loading...</div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen overflow-hidden flex items-center justify-center bg-white">
      {/* Custom Cursor */}
      <TargetCursor
        spinDuration={2}
        hideDefaultCursor
        parallaxOn
        hoverDuration={0.2}
      />

      {/* Noise Background */}
      <div className="absolute inset-0 z-0 overflow-hidden">
        <Noise
          patternSize={250}
          patternScaleX={1}
          patternScaleY={1}
          patternRefreshInterval={2}
          patternAlpha={8}
        />
      </div>

      <div className="relative z-10 w-full max-w-md px-4">
        <ElectricBorder
          color="#06B6D4"
          speed={1}
          chaos={0.08}
          borderRadius={16}
        >
          <div className="bg-white/95 backdrop-blur-sm p-8 rounded-2xl shadow-2xl">
            <div className="mb-6">
              <h2 className="text-center text-3xl font-bold text-slate-900">
                Login
              </h2>
              <p className="mt-2 text-center text-sm text-slate-600">
                Don't have an account?{" "}
                <Link
                  href="/signup"
                  className="cursor-target font-medium text-cyan-600 hover:text-cyan-700 transition-colors"
                >
                  Sign Up
                </Link>
              </p>
            </div>

            <form className="space-y-5" onSubmit={handleSubmit}>
              {(error || localError) && (
                <div className="bg-red-50 border border-red-300 text-red-700 px-4 py-3 rounded-lg text-sm">
                  {error || localError}
                </div>
              )}

              <div className="space-y-4">
                <div>
                  <label
                    htmlFor="username"
                    className="block text-sm font-medium text-slate-700"
                  >
                    Username
                  </label>
                  <input
                    id="username"
                    name="username"
                    type="text"
                    autoComplete="username"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="mt-1 block w-full px-4 py-3 bg-slate-50 border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
                    placeholder="johndoe"
                  />
                </div>

                <div>
                  <label
                    htmlFor="password"
                    className="block text-sm font-medium text-slate-700"
                  >
                    Password
                  </label>
                  <input
                    id="password"
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="mt-1 block w-full px-4 py-3 bg-slate-50 border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
                    placeholder="••••••••"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="cursor-target w-full py-3 px-4 rounded-lg text-sm font-medium text-white bg-gradient-to-r from-cyan-500 to-emerald-500 hover:from-cyan-600 hover:to-emerald-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-white focus:ring-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg"
              >
                {isSubmitting ? "Signing in..." : "Login"}
              </button>
            </form>

            <div className="mt-6 text-center">
              <Link
                href="/"
                className="cursor-target text-sm text-slate-600 hover:text-slate-900 transition-colors"
              >
                ← Back to Home
              </Link>
            </div>
          </div>
        </ElectricBorder>
      </div>
    </div>
  );
}
