'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { MessageSquare, Bot, Sparkles } from 'lucide-react';
import { ContinuumIcon } from '@/components/ui/ContinuumIcon';
import LoginForm from '@/components/LoginForm';
import RegisterForm from '@/components/RegisterForm';

export default function AuthPage() {
  const [activeTab, setActiveTab] = useState<'login' | 'register'>('login');
  const [successMessage, setSuccessMessage] = useState('');
  const { user, isLoading } = useAuth();
  const router = useRouter();

  // Redirect if already logged in
  useEffect(() => {
    if (!isLoading && user) {
      router.push('/dashboard');
    }
  }, [user, isLoading, router]);

  const handleRegisterSuccess = () => {
    setSuccessMessage('Registration successful! Please login with your credentials.');
    setActiveTab('login');
    // Clear success message after 5 seconds
    setTimeout(() => setSuccessMessage(''), 5000);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-black">
        <div className="text-center">
          <div className="relative">
            <div className="w-16 h-16 border-4 border-white/10 rounded-full animate-spin">
              <div className="absolute top-0 left-0 w-16 h-16 border-4 border-transparent border-t-cyan-400 rounded-full animate-spin"></div>
            </div>
          </div>
          <p className="mt-6 text-white/70 font-medium text-lg">Loading your experience...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black flex">
      {/* Left Panel - Minimal Premium Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-black relative overflow-hidden min-h-screen">
        <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 via-transparent to-blue-500/5"></div>
        <div className="relative z-10 flex flex-col justify-center items-center p-16 text-white w-full">
          <div className="text-center max-w-md">
            {/* Simplified Logo */}
            <div className="mb-16">
              <div className="w-24 h-24 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-3xl flex items-center justify-center mx-auto mb-8 shadow-2xl shadow-cyan-500/20">
                <ContinuumIcon size={48} className="text-black" />
              </div>
              <h1 className="text-4xl font-bold tracking-tight mb-2">Continuum AI</h1>
              <p className="text-white/50 text-sm font-medium uppercase tracking-wider">Sales Intelligence Platform</p>
            </div>
            
            {/* Minimal tagline */}
            <div className="space-y-6">
              <h2 className="text-2xl font-light text-white/90 leading-relaxed">
                Transform your sales process with AI-powered insights
              </h2>
              
              {/* Simple feature list */}
              <div className="space-y-3 text-left">
                <div className="flex items-center text-white/70">
                  <div className="w-1.5 h-1.5 bg-cyan-400 rounded-full mr-4"></div>
                  <span className="text-sm font-medium">Advanced Analytics</span>
                </div>
                <div className="flex items-center text-white/70">
                  <div className="w-1.5 h-1.5 bg-cyan-400 rounded-full mr-4"></div>
                  <span className="text-sm font-medium">Intelligent Assistant</span>
                </div>
                <div className="flex items-center text-white/70">
                  <div className="w-1.5 h-1.5 bg-cyan-400 rounded-full mr-4"></div>
                  <span className="text-sm font-medium">Real-time Insights</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        {/* Subtle background element */}
        <div className="absolute bottom-0 right-0 w-96 h-96 bg-gradient-to-tl from-cyan-500/5 to-transparent rounded-full blur-3xl"></div>
      </div>

      {/* Right Panel - Premium Auth Form - FIXED HEIGHT */}
      <div className="flex-1 flex items-center justify-center p-8 lg:p-12 bg-black min-h-screen">
        <div className="w-full max-w-md">
          {/* Mobile Logo */}
          <div className="lg:hidden text-center mb-8">
            <div className="w-16 h-16 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-2xl shadow-cyan-500/25">
              <ContinuumIcon size={32} className="text-black" />
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight mb-1">Continuum AI</h1>
            <p className="text-white/50 text-xs font-medium uppercase tracking-wider">Sales Intelligence Platform</p>
          </div>


          {/* Premium Auth Card - CONSISTENT HEIGHT */}
          <div className="bg-white/5 backdrop-blur-xl rounded-3xl shadow-2xl border border-white/10 p-8 hover:bg-white/10 transition-all duration-500 min-h-[600px] flex flex-col justify-center">
            {/* Welcome Text */}
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold text-white mb-3 tracking-tight">
                {activeTab === 'login' ? 'Welcome Back' : 'Get Started'}
              </h2>
              <p className="text-white/70 text-lg font-medium">
                {activeTab === 'login' 
                  ? 'Sign in to access your AI assistant' 
                  : 'Create your account to begin'
                }
              </p>
            </div>

            {/* Premium Tabs */}
            <div className="relative mb-8">
              <div className="flex bg-white/10 rounded-2xl p-1 backdrop-blur-sm border border-white/20">
                <button
                  onClick={() => setActiveTab('login')}
                  className={`flex-1 py-4 text-center font-semibold rounded-xl transition-all duration-300 ${
                    activeTab === 'login'
                      ? 'bg-gradient-to-r from-cyan-400 to-blue-500 text-black shadow-lg'
                      : 'text-white/70 hover:text-white hover:bg-white/10'
                  }`}
                >
                  Sign In
                </button>
                <button
                  onClick={() => setActiveTab('register')}
                  className={`flex-1 py-4 text-center font-semibold rounded-xl transition-all duration-300 ${
                    activeTab === 'register'
                      ? 'bg-gradient-to-r from-cyan-400 to-blue-500 text-black shadow-lg'
                      : 'text-white/70 hover:text-white hover:bg-white/10'
                  }`}
                >
                  Sign Up
                </button>
              </div>
            </div>

            {/* Form Content */}
            <div className="space-y-6">
              {successMessage && (
                <div className="bg-green-400/20 border border-green-400/30 text-green-300 px-4 py-3 rounded-2xl text-sm font-medium">
                  {successMessage}
                </div>
              )}
              
              <div className="transition-all duration-300 ease-in-out">
                {activeTab === 'login' ? (
                  <LoginForm />
                ) : (
                  <RegisterForm onSuccess={handleRegisterSuccess} />
                )}
              </div>
            </div>
          </div>

          {/* Footer */}
          <p className="text-center text-white/50 text-sm mt-8 font-medium">
            © 2025 Continuum AI. All rights reserved.
          </p>

          {/* Demo Credentials */}
          <div className="mt-6 text-center">
            <p className="text-white/60 text-sm font-medium mb-2">Demo credentials:</p>
            <p className="text-cyan-400 text-sm font-mono">demo / password123</p>
          </div>
        </div>
      </div>
    </div>
  );
}
