"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import Aurora from "@/components/ui/Aurora";
import CountUp from "@/components/ui/CountUp";
import LogoLoop, { LogoItem } from "@/components/ui/LogoLoop";
import { MagicBento, MagicBentoItem } from "@/components/ui/MagicBento";
import Noise from "@/components/ui/Noise";
import TextType from "@/components/ui/TextType";
import { 
  SiPython, 
  SiPostgresql, 
  SiOpenai, 
  SiFastapi, 
  SiReact, 
  SiTypescript,
  SiTailwindcss,
  SiDocker,
  SiNextdotjs,
  SiRedis,
  SiPandas,
  SiSupabase,
  SiLangchain
} from "react-icons/si";
import { 
  HiOutlineChartBar, 
  HiOutlineChatBubbleLeftRight, 
  HiOutlineCpuChip,
  HiOutlineShieldCheck,
  HiOutlineSparkles
} from "react-icons/hi2";

export default function Home() {
  const { isAuthenticated, isLoading } = useAuth();

  const techLogos: LogoItem[] = [
    { node: <SiPython className="text-yellow-400" />, title: "Python" },
    { node: <SiPostgresql className="text-blue-400" />, title: "PostgreSQL" },
    { node: <SiOpenai className="text-white" />, title: "OpenAI" },
    { node: <SiFastapi className="text-teal-400" />, title: "FastAPI" },
    { node: <SiReact className="text-cyan-400" />, title: "React" },
    { node: <SiTypescript className="text-blue-400" />, title: "TypeScript" },
    { node: <SiTailwindcss className="text-cyan-400" />, title: "TailwindCSS" },
    { node: <SiDocker className="text-blue-400" />, title: "Docker" },
    { node: <SiNextdotjs className="text-white" />, title: "Next.js" },
    { node: <SiRedis className="text-red-400" />, title: "Redis" },
    { node: <SiPandas className="text-purple-400" />, title: "Pandas" },
    { node: <SiSupabase className="text-emerald-400" />, title: "Supabase" },
    { node: <SiLangchain className="text-green-400" />, title: "LangChain" },
  ];

  return (
    <div className="min-h-screen w-full bg-white text-slate-900 overflow-x-hidden">
      {/* Pill-shaped Floating Navbar */}
      <nav className="fixed top-4 left-1/2 -translate-x-1/2 z-50 w-[65%]">
        <div className="flex items-center justify-between px-8 py-3 rounded-full backdrop-blur-xl bg-white/60 border border-white/40 shadow-lg shadow-slate-200/50">
          <Link href="/" className="text-lg font-bold tracking-tight font-[family-name:var(--font-special-gothic)] text-slate-900">
            ContinuumAI
          </Link>

          <div className="flex items-center gap-2">
            {isLoading ? (
              <div className="w-14 h-8 bg-slate-100 rounded-full animate-pulse" />
            ) : isAuthenticated ? (
              <Link
                href="/dashboard"
                className="px-4 py-1.5 bg-[#4F46E5] text-white text-sm font-medium rounded-full hover:bg-[#6366F1] transition-all"
              >
                Dashboard
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="px-4 py-1.5 bg-[#4F46E5] text-white text-sm font-medium rounded-full hover:bg-[#6366F1] transition-all"
                >
                  Login
                </Link>
                <Link
                  href="/get-access"
                  className="px-4 py-1.5 border border-slate-300 text-slate-700 text-sm font-medium rounded-full hover:bg-slate-100 transition-all"
                >
                  Get Access
                </Link>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* Hero Section with Aurora Background */}
      <section className="relative h-[80vh] flex items-center justify-center overflow-hidden">
        {/* Aurora Background - Absolute positioned */}
        <div className="absolute inset-0 z-0">
          <Aurora colorStops={["#4F46E5", "#06B6D4", "#10B981"]} blend={0.3} amplitude={1.0} />
        </div>
        
        {/* Noise overlay for texture */}
        <div className="absolute inset-0 z-[1] opacity-30">
          <Noise
            patternSize={250}
            patternScaleX={1}
            patternScaleY={1}
            patternRefreshInterval={2}
            patternAlpha={15}
          />
        </div>
        
        {/* Content - Foreground */}
        <div className="relative z-10 text-center max-w-4xl mx-auto px-6 pt-16">
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight mb-8 font-[family-name:var(--font-special-gothic)]">
            <span className="text-slate-900">
              The Future of
            </span>
            <br />
            <span className="bg-gradient-to-r from-[#4F46E5] via-cyan-500 to-emerald-500 bg-clip-text text-transparent">
              Business Intelligence
            </span>
          </h1>

          {/* CTA Buttons */}
          {!isLoading && !isAuthenticated && (
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link
                href="/login"
                className="px-6 py-3 bg-[#4F46E5] text-white font-semibold rounded-xl hover:bg-[#6366F1] transition-all shadow-xl hover:shadow-2xl hover:scale-105"
              >
                Login
              </Link>
              <Link
                href="/get-access"
                className="px-6 py-3 bg-white/80 border-2 border-[#4F46E5] text-[#4F46E5] font-semibold rounded-xl hover:bg-[#4F46E5]/10 transition-all backdrop-blur-sm hover:scale-105"
              >
                Get Access
              </Link>
            </div>
          )}
        </div>
      </section>

      {/* Stats Section */}
      <section id="stats" className="py-16 px-6 bg-gradient-to-b from-slate-50 to-white">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className="text-center p-5 rounded-2xl bg-white shadow-lg border border-slate-100">
              <div className="text-3xl md:text-4xl font-bold text-[#4F46E5] mb-2">
                <CountUp from={0} to={99} duration={2} /><span>%</span>
              </div>
              <p className="text-slate-600 font-medium text-sm">Query Accuracy</p>
            </div>
            <div className="text-center p-5 rounded-2xl bg-white shadow-lg border border-slate-100">
              <div className="text-3xl md:text-4xl font-bold text-cyan-500 mb-2">
                <CountUp from={0} to={10} duration={2} /><span>x</span>
              </div>
              <p className="text-slate-600 font-medium text-sm">Faster Insights</p>
            </div>
            <div className="text-center p-5 rounded-2xl bg-white shadow-lg border border-slate-100">
              <div className="text-3xl md:text-4xl font-bold text-emerald-500 mb-2">
                <CountUp from={0} to={75} duration={2} /><span>%</span>
              </div>
              <p className="text-slate-600 font-medium text-sm">Faster Onboarding</p>
            </div>
            <div className="text-center p-5 rounded-2xl bg-white shadow-lg border border-slate-100">
              <div className="text-3xl md:text-4xl font-bold text-purple-500 mb-2">
                <CountUp from={0} to={100} duration={2} /><span>%</span>
              </div>
              <p className="text-slate-600 font-medium text-sm">Secure &amp; Private</p>
            </div>
          </div>
        </div>
      </section>

      {/* Tech Stack Section - Dark */}
      <section id="tech" className="py-16 px-6 bg-slate-900">
        <div className="max-w-6xl mx-auto">
          <p className="text-center text-sm text-slate-400 uppercase tracking-wider mb-8 font-medium">
            Powered by Industry-Leading Technologies
          </p>
          <LogoLoop 
            logos={techLogos} 
            speed={80} 
            logoHeight={40} 
            gap={60}
            pauseOnHover
            fadeOut
            fadeOutColor="#0f172a"
          />
        </div>
      </section>

      {/* Demo Section - Chat + Graph */}
      <section className="py-20 px-6 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-2xl md:text-4xl font-bold mb-4">
              <span className="text-slate-900">See It </span>
              <span className="bg-gradient-to-r from-[#4F46E5] to-cyan-500 bg-clip-text text-transparent">
                In Action
              </span>
            </h2>
            <p className="text-slate-600 text-base max-w-2xl mx-auto">
              Ask questions in natural language and get instant visualizations
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8 items-center">
            {/* Chat Box */}
            <div className="bg-slate-50 rounded-2xl p-6 border border-slate-200 shadow-lg">
              <div className="flex items-center gap-2 mb-4 pb-4 border-b border-slate-200">
                <div className="w-3 h-3 rounded-full bg-red-400" />
                <div className="w-3 h-3 rounded-full bg-yellow-400" />
                <div className="w-3 h-3 rounded-full bg-green-400" />
                <span className="ml-2 text-sm text-slate-500 font-medium">AI Assistant</span>
              </div>
              
              <div className="space-y-4">
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#4F46E5] to-cyan-500 flex items-center justify-center shrink-0">
                    <span className="text-white text-xs font-bold">U</span>
                  </div>
                  <div className="bg-white rounded-xl px-4 py-3 shadow-sm border border-slate-100 max-w-[85%]">
                    <TextType
                      text={["Show me sales trends for Q4 2024 by region"]}
                      typingSpeed={40}
                      pauseDuration={4000}
                      deletingSpeed={25}
                      showCursor
                      cursorCharacter="|"
                      cursorBlinkDuration={0.5}
                      loop={true}
                      className="text-sm text-slate-700"
                      cursorClassName="text-[#4F46E5]"
                    />
                  </div>
                </div>
                
                <div className="flex gap-3 justify-end">
                  <div className="bg-[#4F46E5] rounded-xl px-4 py-3 shadow-sm max-w-[85%]">
                    <p className="text-sm text-white">
                      Here&apos;s the Q4 2024 sales breakdown by region. The West region shows 23% growth while East maintains steady performance...
                    </p>
                  </div>
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-emerald-500 flex items-center justify-center shrink-0">
                    <HiOutlineCpuChip className="w-4 h-4 text-white" />
                  </div>
                </div>
              </div>
            </div>

            {/* Graph Visualization */}
            <div className="bg-slate-50 rounded-2xl p-6 border border-slate-200 shadow-lg">
              <div className="flex items-center justify-between mb-4 pb-4 border-b border-slate-200">
                <span className="text-sm text-slate-700 font-semibold">Q4 2024 Sales by Region</span>
                <HiOutlineChartBar className="w-5 h-5 text-[#4F46E5]" />
              </div>
              
              {/* Mock Bar Chart */}
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <span className="text-xs text-slate-500 w-12">West</span>
                  <div className="flex-1 h-8 bg-slate-200 rounded-lg overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-[#4F46E5] to-indigo-400 rounded-lg" style={{ width: '85%' }} />
                  </div>
                  <span className="text-xs font-semibold text-slate-700 w-12">$2.4M</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-xs text-slate-500 w-12">East</span>
                  <div className="flex-1 h-8 bg-slate-200 rounded-lg overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-cyan-500 to-cyan-400 rounded-lg" style={{ width: '70%' }} />
                  </div>
                  <span className="text-xs font-semibold text-slate-700 w-12">$1.9M</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-xs text-slate-500 w-12">North</span>
                  <div className="flex-1 h-8 bg-slate-200 rounded-lg overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-lg" style={{ width: '55%' }} />
                  </div>
                  <span className="text-xs font-semibold text-slate-700 w-12">$1.5M</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-xs text-slate-500 w-12">South</span>
                  <div className="flex-1 h-8 bg-slate-200 rounded-lg overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-purple-500 to-purple-400 rounded-lg" style={{ width: '45%' }} />
                  </div>
                  <span className="text-xs font-semibold text-slate-700 w-12">$1.2M</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section with MagicBento */}
      <section id="features" className="py-20 px-6 bg-slate-100">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-2xl md:text-4xl font-bold mb-4">
              <span className="text-slate-900">Powerful </span>
              <span className="bg-gradient-to-r from-[#4F46E5] to-cyan-500 bg-clip-text text-transparent">
                Features
              </span>
            </h2>
            <p className="text-slate-600 text-base max-w-2xl mx-auto">
              Everything you need to transform raw data into strategic decisions
            </p>
          </div>

          <MagicBento className="gap-4" glowColor="rgba(79, 70, 229, 0.3)">
            <MagicBentoItem colSpan={2} rowSpan={2} className="bg-gradient-to-br from-white to-indigo-50/50">
              <div className="h-full flex flex-col justify-between">
                <div>
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-cyan-500 flex items-center justify-center mb-4 shadow-lg">
                    <HiOutlineChatBubbleLeftRight className="w-6 h-6 text-white" />
                  </div>
                  <h3 className="text-xl font-bold text-slate-900 mb-2">Natural Language Queries</h3>
                  <p className="text-slate-600 text-sm">
                    Ask questions in plain English and get instant, accurate answers. 
                    No SQL knowledge required - just type what you want to know.
                  </p>
                </div>
                <div className="mt-4 p-3 rounded-lg bg-slate-100/80 border border-slate-200">
                  <p className="text-xs text-slate-500 mb-1">Example query:</p>
                  <p className="text-indigo-600 font-mono text-xs">
                    &quot;Show me top 10 products by revenue this quarter&quot;
                  </p>
                </div>
              </div>
            </MagicBentoItem>

            <MagicBentoItem className="bg-gradient-to-br from-white to-cyan-50/50">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-teal-500 flex items-center justify-center mb-3 shadow-md">
                <HiOutlineChartBar className="w-5 h-5 text-white" />
              </div>
              <h3 className="text-base font-bold text-slate-900 mb-1">Smart Visualizations</h3>
              <p className="text-slate-600 text-xs">
                Auto-generated charts and graphs that tell your data&apos;s story
              </p>
            </MagicBentoItem>

            <MagicBentoItem className="bg-gradient-to-br from-white to-purple-50/50">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-indigo-500 flex items-center justify-center mb-3 shadow-md">
                <HiOutlineCpuChip className="w-5 h-5 text-white" />
              </div>
              <h3 className="text-base font-bold text-slate-900 mb-1">AI-Powered Analysis</h3>
              <p className="text-slate-600 text-xs">
                Bundle your data with the power of LLMs to discover hidden patterns and trends
              </p>
            </MagicBentoItem>

            <MagicBentoItem className="bg-gradient-to-br from-white to-emerald-50/50">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center mb-3 shadow-md">
                <HiOutlineShieldCheck className="w-5 h-5 text-white" />
              </div>
              <h3 className="text-base font-bold text-slate-900 mb-1">Enterprise Security</h3>
              <p className="text-slate-600 text-xs">
                Role-based access, encryption, and compliance built-in
              </p>
            </MagicBentoItem>

            <MagicBentoItem colSpan={2} className="bg-gradient-to-br from-white to-pink-50/50">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-pink-500 to-purple-500 flex items-center justify-center shrink-0 shadow-md">
                  <HiOutlineSparkles className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900 mb-1">Real-Time Insights</h3>
                  <p className="text-slate-600 text-xs">
                    Connect your data source and let AI find correlations across your entire data ecosystem. No more siloed dashboards - get a holistic view of your business in real time. 
                  </p>
                </div>
              </div>
            </MagicBentoItem>
          </MagicBento>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-20 px-6 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-2xl md:text-4xl font-bold mb-4">
              <span className="text-slate-900">How It </span>
              <span className="bg-gradient-to-r from-[#4F46E5] to-cyan-500 bg-clip-text text-transparent">
                Works
              </span>
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <div className="text-center p-8 rounded-2xl bg-white border-2 border-slate-200 shadow-lg hover:shadow-xl hover:border-[#4F46E5]/30 transition-all">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#4F46E5] to-indigo-400 flex items-center justify-center mx-auto mb-4 shadow-lg">
                <span className="text-2xl font-bold text-white">1</span>
              </div>
              <h3 className="text-lg font-bold text-slate-900 mb-2">Ask Your Question</h3>
              <p className="text-slate-600 text-sm">
                Type your business question in natural language - no technical knowledge needed.
              </p>
            </div>

            <div className="text-center p-8 rounded-2xl bg-white border-2 border-slate-200 shadow-lg hover:shadow-xl hover:border-cyan-500/30 transition-all">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500 to-teal-400 flex items-center justify-center mx-auto mb-4 shadow-lg">
                <span className="text-2xl font-bold text-white">2</span>
              </div>
              <h3 className="text-lg font-bold text-slate-900 mb-2">AI Processes Data</h3>
              <p className="text-slate-600 text-sm">
                Our AI understands context, queries your data, and generates accurate results.
              </p>
            </div>

            <div className="text-center p-8 rounded-2xl bg-white border-2 border-slate-200 shadow-lg hover:shadow-xl hover:border-emerald-500/30 transition-all">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500 to-green-400 flex items-center justify-center mx-auto mb-4 shadow-lg">
                <span className="text-2xl font-bold text-white">3</span>
              </div>
              <h3 className="text-lg font-bold text-slate-900 mb-2">Get Visual Insights</h3>
              <p className="text-slate-600 text-sm">
                Receive beautiful charts, tables, and actionable insights instantly.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-6 relative overflow-hidden bg-slate-100">
        {/* Noise overlay */}
        <div className="absolute inset-0 z-0 opacity-20">
          <Noise
            patternSize={200}
            patternScaleX={1}
            patternScaleY={1}
            patternRefreshInterval={3}
            patternAlpha={20}
          />
        </div>
        <div className="relative z-10 max-w-4xl mx-auto text-center">
          <h2 className="text-2xl md:text-4xl font-bold mb-4 text-slate-900">
            Ready to Transform Your Analytics?
          </h2>
          <p className="text-slate-600 text-base mb-8 max-w-2xl mx-auto">
            Join leading organizations using ContinuumAI to make smarter data-driven decisions.
          </p>
          {!isAuthenticated && (
            <Link
              href="/get-access"
              className="inline-flex items-center gap-2 px-8 py-4 bg-white text-[#4F46E5] font-semibold rounded-xl hover:bg-slate-50 transition-all shadow-2xl hover:scale-105"
            >
              Get Access Today
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </Link>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="py-4 px-6 bg-slate-900 border-t border-slate-800">
        <div className="max-w-6xl mx-auto flex items-center justify-center gap-2">
          <span className="text-lg font-bold tracking-tight font-[family-name:var(--font-special-gothic)] text-white">ContinuumAI</span>
          <span className="text-slate-500">|</span>
          <span className="text-slate-400 text-sm">© 2026 All rights reserved.</span>
        </div>
      </footer>
    </div>
  );
}
