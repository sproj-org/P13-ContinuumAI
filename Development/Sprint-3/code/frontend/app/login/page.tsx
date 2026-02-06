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
      <div className="h-screen w-screen overflow-hidden flex items-center justify-center bg-[#060010]">
        <div className="text-lg text-white">Loading...</div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen overflow-hidden flex items-center justify-center bg-[#060010]">
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
          patternAlpha={15}
        />
      </div>

      <div className="relative z-10 w-full max-w-md px-4">
        <ElectricBorder
          color="#5237ff"
          speed={1}
          chaos={0.08}
          borderRadius={16}
        >
          <div className="bg-[#060010]/90 backdrop-blur-sm p-8 rounded-2xl">
            <div className="mb-6">
              <h2 className="text-center text-3xl font-bold text-white">
                Login
              </h2>
              <p className="mt-2 text-center text-sm text-gray-400">
                Don't have an account?{" "}
                <Link
                  href="/signup"
                  className="cursor-target font-medium text-[#5237ff] hover:text-[#6347ff] transition-colors"
                >
                  Sign Up
                </Link>
              </p>
            </div>

            <form className="space-y-5" onSubmit={handleSubmit}>
              {(error || localError) && (
                <div className="bg-red-500/10 border border-red-500/50 text-red-400 px-4 py-3 rounded-lg text-sm">
                  {error || localError}
                </div>
              )}

              <div className="space-y-4">
                <div>
                  <label
                    htmlFor="username"
                    className="block text-sm font-medium text-gray-300"
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
                    className="mt-1 block w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-[#5237ff] focus:border-transparent transition-all"
                    placeholder="johndoe"
                  />
                </div>

                <div>
                  <label
                    htmlFor="password"
                    className="block text-sm font-medium text-gray-300"
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
                    className="mt-1 block w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-[#5237ff] focus:border-transparent transition-all"
                    placeholder="••••••••"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="cursor-target w-full py-3 px-4 rounded-lg text-sm font-medium text-white bg-[#5237ff] hover:bg-[#6347ff] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#060010] focus:ring-[#5237ff] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isSubmitting ? "Signing in..." : "Login"}
              </button>
            </form>

            <div className="mt-6 text-center">
              <Link
                href="/"
                className="cursor-target text-sm text-gray-400 hover:text-white transition-colors"
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
