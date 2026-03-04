"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import TextType from "@/components/TextType";
import TargetCursor from "@/components/TargetCursor";
import Noise from "@/components/Noise";

export default function Home() {
  const { isAuthenticated, isLoading } = useAuth();

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col items-center justify-center bg-white">
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

      <main className="relative z-10 text-center flex flex-col items-center justify-center gap-6">
        {/* App Name */}
        <h1 className="text-5xl md:text-6xl lg:text-7xl font-normal text-slate-900 tracking-wide font-[family-name:var(--font-special-gothic)]">
          ContinuumAi
        </h1>

        {/* Tagline with typing animation */}
        <div className="h-8 flex items-center justify-center">
          <TextType
            text={["The Future of Business Intelligence."]}
            typingSpeed={75}
            pauseDuration={7000}
            deletingSpeed={50}
            showCursor
            cursorCharacter="_"
            cursorBlinkDuration={0.5}
            loop={true}
            className="text-xl md:text-2xl text-slate-600 font-light"
            cursorClassName="text-[#4F46E5]"
          />
        </div>

        {/* Buttons */}
        {isLoading ? (
          <div className="text-slate-500 mt-8">Loading...</div>
        ) : isAuthenticated ? (
          <Link
            href="/dashboard"
            className="cursor-target mt-8 px-8 py-3 bg-[#4F46E5] text-white font-medium rounded-lg hover:bg-[#6366F1] transition-colors shadow-lg"
          >
            Go to Dashboard
          </Link>
        ) : (
          <div className="flex gap-6 mt-8">
            <Link
              href="/login"
              className="cursor-target px-8 py-3 bg-[#4F46E5] text-white font-medium rounded-lg hover:bg-[#6366F1] transition-colors shadow-lg"
            >
              Login
            </Link>
            <Link
              href="/signup"
              className="cursor-target px-8 py-3 border-2 border-[#4F46E5] text-[#4F46E5] font-medium rounded-lg hover:bg-[#4F46E5]/10 transition-colors"
            >
              Sign Up
            </Link>
          </div>
        )}
      </main>
    </div>
  );
}
