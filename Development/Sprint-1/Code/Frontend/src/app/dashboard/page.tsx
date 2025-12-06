'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

export default function DashboardPage() {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();

  // Redirect if not logged in
  useEffect(() => {
    if (!isLoading && !user) {
      router.push('/auth');
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-black">
        <div className="text-center">
          <div className="relative">
            <div className="w-16 h-16 border-4 border-white/10 rounded-full animate-spin">
              <div className="absolute top-0 left-0 w-16 h-16 border-4 border-transparent border-t-cyan-400 rounded-full animate-spin"></div>
            </div>
          </div>
          <p className="mt-6 text-white/70 font-medium text-lg">Loading your dashboard...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-black">
      {/* Premium Header */}
      <header className="bg-black/95 backdrop-blur-xl border-b border-white/10 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-5 flex justify-between items-center">
          <div className="flex items-center space-x-4">
            <div className="w-11 h-11 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-2xl flex items-center justify-center shadow-2xl shadow-cyan-500/25 ring-1 ring-white/10">
              <div className="w-6 h-6 bg-black rounded-xl flex items-center justify-center">
                <div className="w-2.5 h-2.5 bg-cyan-400 rounded-full animate-pulse"></div>
              </div>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">Continuum AI</h1>
              <p className="text-xs text-white/60 font-medium">Sales Intelligence Platform</p>
            </div>
          </div>
          <button
            onClick={logout}
            className="px-5 py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-white rounded-xl transition-all duration-300 ease-out backdrop-blur-sm hover:shadow-lg hover:shadow-white/5 transform hover:scale-105 active:scale-95 font-medium"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-10">
        {/* Premium Welcome Section */}
        <div className="mb-12">
          <div className="flex items-center space-x-3 mb-4">
            <div className="w-2 h-2 bg-cyan-400 rounded-full animate-pulse"></div>
            <span className="text-sm font-medium text-white/60 uppercase tracking-wider">Dashboard</span>
          </div>
          <h2 className="text-4xl font-bold text-white mb-3 tracking-tight">
            Welcome back, {user.username}
          </h2>
          <p className="text-xl text-white/70 font-medium max-w-2xl leading-relaxed">
            Your AI-powered sales intelligence platform is ready to unlock insights and drive growth.
          </p>
        </div>

        {/* Premium Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          <div className="bg-white/5 backdrop-blur-xl rounded-2xl p-7 border border-white/10 hover:border-white/20 hover:bg-white/10 transition-all duration-500 ease-out group">
            <div className="flex items-center justify-between mb-6">
              <div className="w-14 h-14 bg-gradient-to-br from-cyan-400/20 to-blue-500/20 rounded-2xl flex items-center justify-center ring-1 ring-cyan-400/30 group-hover:ring-cyan-400/50 transition-all duration-300">
                <div className="w-7 h-7 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-xl shadow-lg"></div>
              </div>
              <div className="text-right">
                <span className="text-3xl font-bold text-white">24</span>
                <div className="flex items-center space-x-1 mt-1">
                  <div className="w-1 h-1 bg-green-400 rounded-full"></div>
                  <span className="text-xs text-green-400 font-medium">+12%</span>
                </div>
              </div>
            </div>
            <h3 className="font-semibold text-white mb-2 text-lg">Active Conversations</h3>
            <p className="text-sm text-white/60 font-medium">This month</p>
          </div>
          
          <div className="bg-white/5 backdrop-blur-xl rounded-2xl p-7 border border-white/10 hover:border-white/20 hover:bg-white/10 transition-all duration-500 ease-out group">
            <div className="flex items-center justify-between mb-6">
              <div className="w-14 h-14 bg-gradient-to-br from-green-400/20 to-emerald-500/20 rounded-2xl flex items-center justify-center ring-1 ring-green-400/30 group-hover:ring-green-400/50 transition-all duration-300">
                <div className="w-7 h-7 bg-gradient-to-br from-green-400 to-emerald-500 rounded-xl shadow-lg"></div>
              </div>
              <div className="text-right">
                <span className="text-3xl font-bold text-white">94%</span>
                <div className="flex items-center space-x-1 mt-1">
                  <div className="w-1 h-1 bg-green-400 rounded-full"></div>
                  <span className="text-xs text-green-400 font-medium">+5%</span>
                </div>
              </div>
            </div>
            <h3 className="font-semibold text-white mb-2 text-lg">AI Accuracy</h3>
            <p className="text-sm text-white/60 font-medium">Response quality</p>
          </div>
          
          <div className="bg-white/5 backdrop-blur-xl rounded-2xl p-7 border border-white/10 hover:border-white/20 hover:bg-white/10 transition-all duration-500 ease-out group">
            <div className="flex items-center justify-between mb-6">
              <div className="w-14 h-14 bg-gradient-to-br from-purple-400/20 to-pink-500/20 rounded-2xl flex items-center justify-center ring-1 ring-purple-400/30 group-hover:ring-purple-400/50 transition-all duration-300">
                <div className="w-7 h-7 bg-gradient-to-br from-purple-400 to-pink-500 rounded-xl shadow-lg"></div>
              </div>
              <div className="text-right">
                <span className="text-3xl font-bold text-white">2.1K</span>
                <div className="flex items-center space-x-1 mt-1">
                  <div className="w-1 h-1 bg-green-400 rounded-full"></div>
                  <span className="text-xs text-green-400 font-medium">+28%</span>
                </div>
              </div>
            </div>
            <h3 className="font-semibold text-white mb-2 text-lg">Insights Generated</h3>
            <p className="text-sm text-white/60 font-medium">Total insights</p>
          </div>
        </div>

        {/* Premium Profile Section */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-12">
          {/* Profile Card */}
          <div className="lg:col-span-2 bg-white/5 backdrop-blur-xl rounded-2xl p-8 border border-white/10">
            <div className="flex items-center space-x-4 mb-8">
              <div className="w-16 h-16 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-2xl flex items-center justify-center shadow-2xl shadow-cyan-500/25">
                <span className="text-2xl font-bold text-black">{user.username.charAt(0).toUpperCase()}</span>
              </div>
              <div>
                <h3 className="text-2xl font-bold text-white mb-1">{user.username}</h3>
                <p className="text-white/60 font-medium">{user.email}</p>
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-5">
                <div className="flex items-center justify-between py-4 border-b border-white/10">
                  <span className="font-medium text-white/70">User ID</span>
                  <span className="text-white font-medium font-mono text-sm">{user.user_id}</span>
                </div>
                <div className="flex items-center justify-between py-4 border-b border-white/10">
                  <span className="font-medium text-white/70">Username</span>
                  <span className="text-white font-medium">{user.username}</span>
                </div>
                <div className="flex items-center justify-between py-4 border-b border-white/10">
                  <span className="font-medium text-white/70">Email</span>
                  <span className="text-white font-medium">{user.email}</span>
                </div>
              </div>
              <div className="space-y-5">
                <div className="flex items-center justify-between py-4 border-b border-white/10">
                  <span className="font-medium text-white/70">Role</span>
                  <span className="inline-flex items-center px-3 py-1.5 rounded-xl text-xs font-semibold bg-cyan-400/20 text-cyan-400 border border-cyan-400/30">
                    {user.role}
                  </span>
                </div>
                <div className="flex items-center justify-between py-4 border-b border-white/10">
                  <span className="font-medium text-white/70">Status</span>
                  <span className={`inline-flex items-center px-3 py-1.5 rounded-xl text-xs font-semibold border ${
                    user.is_active 
                      ? 'bg-green-400/20 text-green-400 border-green-400/30' 
                      : 'bg-red-400/20 text-red-400 border-red-400/30'
                  }`}>
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <div className="flex items-center justify-between py-4 border-b border-white/10">
                  <span className="font-medium text-white/70">Member since</span>
                  <span className="text-white font-medium">
                    {new Date(user.created_at).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric'
                    })}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="space-y-6">
            <div className="bg-white/5 backdrop-blur-xl rounded-2xl p-6 border border-white/10">
              <h4 className="font-semibold text-white mb-4">Quick Actions</h4>
              <div className="space-y-3">
                <button className="w-full flex items-center space-x-3 p-3 bg-white/5 hover:bg-white/10 rounded-xl transition-all duration-300 group">
                  <div className="w-8 h-8 bg-cyan-400/20 rounded-lg flex items-center justify-center group-hover:bg-cyan-400/30 transition-colors">
                    <div className="w-3 h-3 bg-cyan-400 rounded-sm"></div>
                  </div>
                  <span className="text-white font-medium">Settings</span>
                </button>
                <button className="w-full flex items-center space-x-3 p-3 bg-white/5 hover:bg-white/10 rounded-xl transition-all duration-300 group">
                  <div className="w-8 h-8 bg-purple-400/20 rounded-lg flex items-center justify-center group-hover:bg-purple-400/30 transition-colors">
                    <div className="w-3 h-3 bg-purple-400 rounded-sm"></div>
                  </div>
                  <span className="text-white font-medium">Analytics</span>
                </button>
                <button className="w-full flex items-center space-x-3 p-3 bg-white/5 hover:bg-white/10 rounded-xl transition-all duration-300 group">
                  <div className="w-8 h-8 bg-green-400/20 rounded-lg flex items-center justify-center group-hover:bg-green-400/30 transition-colors">
                    <div className="w-3 h-3 bg-green-400 rounded-sm"></div>
                  </div>
                  <span className="text-white font-medium">Reports</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Premium AI Chat CTA */}
        <div className="bg-gradient-to-br from-cyan-500/10 via-blue-500/10 to-purple-500/10 backdrop-blur-xl rounded-3xl p-10 border border-white/10 relative overflow-hidden">
          {/* Background Pattern */}
          <div className="absolute inset-0 bg-gradient-to-br from-cyan-400/5 to-blue-500/5 opacity-50"></div>
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-cyan-400/10 to-blue-500/10 rounded-full blur-3xl"></div>
          <div className="absolute bottom-0 left-0 w-24 h-24 bg-gradient-to-br from-purple-400/10 to-pink-500/10 rounded-full blur-2xl"></div>
          
          <div className="relative flex items-center justify-between">
            <div className="flex-1 max-w-2xl">
              <div className="flex items-center space-x-3 mb-6">
                <div className="w-14 h-14 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-2xl flex items-center justify-center shadow-2xl shadow-cyan-500/25 ring-1 ring-white/20">
                  <div className="w-7 h-7 bg-black rounded-xl flex items-center justify-center">
                    <div className="w-3 h-3 bg-cyan-400 rounded-sm animate-pulse"></div>
                  </div>
                </div>
                <div>
                  <h3 className="text-3xl font-bold text-white tracking-tight mb-1">
                    AI Sales Assistant
                  </h3>
                  <p className="text-white/60 font-medium">Powered by advanced machine learning</p>
                </div>
              </div>
              
              <p className="text-white/80 mb-8 text-lg leading-relaxed">
                Transform your sales process with AI-powered insights, market analysis, and strategic recommendations. 
                Start intelligent conversations that drive real results.
              </p>
              
              <button
                onClick={() => router.push('/chat')}
                className="bg-gradient-to-r from-cyan-400 to-blue-500 text-black px-8 py-4 rounded-2xl font-bold hover:from-cyan-300 hover:to-blue-400 transition-all duration-300 ease-out shadow-2xl shadow-cyan-500/25 hover:shadow-cyan-500/40 transform hover:scale-105 active:scale-95 ring-1 ring-white/20"
              >
                Launch AI Assistant →
              </button>
            </div>
            
            <div className="hidden xl:block ml-12">
              <div className="w-32 h-32 bg-gradient-to-br from-white/5 to-white/10 rounded-3xl flex items-center justify-center backdrop-blur-sm border border-white/10 relative">
                <div className="w-16 h-16 bg-gradient-to-br from-cyan-400/20 to-blue-500/20 rounded-2xl flex items-center justify-center">
                  <div className="w-8 h-8 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-xl shadow-lg animate-pulse"></div>
                </div>
                <div className="absolute -top-2 -right-2 w-6 h-6 bg-green-400 rounded-full flex items-center justify-center">
                  <div className="w-2 h-2 bg-black rounded-full"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
