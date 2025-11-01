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
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-800">ContinuumAI Dashboard</h1>
          <button
            onClick={logout}
            className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
          >
            Logout
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome Card */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-2xl font-semibold text-gray-800 mb-2">
            Welcome back, {user.username}! 👋
          </h2>
          <p className="text-gray-600">You are successfully logged in to ContinuumAI.</p>
        </div>

        {/* User Info Card */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Your Profile</h3>
          <div className="space-y-3">
            <div className="flex items-center">
              <span className="font-medium text-gray-700 w-32">User ID:</span>
              <span className="text-gray-600">{user.user_id}</span>
            </div>
            <div className="flex items-center">
              <span className="font-medium text-gray-700 w-32">Username:</span>
              <span className="text-gray-600">{user.username}</span>
            </div>
            <div className="flex items-center">
              <span className="font-medium text-gray-700 w-32">Email:</span>
              <span className="text-gray-600">{user.email}</span>
            </div>
            <div className="flex items-center">
              <span className="font-medium text-gray-700 w-32">Role:</span>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                {user.role}
              </span>
            </div>
            <div className="flex items-center">
              <span className="font-medium text-gray-700 w-32">Status:</span>
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
              }`}>
                {user.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
            <div className="flex items-center">
              <span className="font-medium text-gray-700 w-32">Member since:</span>
              <span className="text-gray-600">
                {new Date(user.created_at).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric'
                })}
              </span>
            </div>
          </div>
        </div>

        {/* Placeholder for future features */}
        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-4xl mb-2">📊</div>
            <h3 className="font-semibold text-gray-800">Analytics</h3>
            <p className="text-sm text-gray-600 mt-1">Coming soon</p>
          </div>
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-4xl mb-2">📈</div>
            <h3 className="font-semibold text-gray-800">Reports</h3>
            <p className="text-sm text-gray-600 mt-1">Coming soon</p>
          </div>
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-4xl mb-2">⚙️</div>
            <h3 className="font-semibold text-gray-800">Settings</h3>
            <p className="text-sm text-gray-600 mt-1">Coming soon</p>
          </div>
        </div>
      </main>
    </div>
  );
}
