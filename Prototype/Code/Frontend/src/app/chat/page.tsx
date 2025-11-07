'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Sidebar } from '@/components/chat/Sidebar';
import { ChatInterface } from '@/components/chat/ChatInterface';

export default function ChatPage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  // Redirect if not logged in
  useEffect(() => {
    if (!isLoading && !user) {
      router.push('/auth');
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <div className="relative">
            <div className="w-16 h-16 border-4 border-gray-200 dark:border-gray-700 rounded-full animate-spin">
              <div className="absolute top-0 left-0 w-16 h-16 border-4 border-transparent border-t-blue-500 rounded-full animate-spin"></div>
            </div>
          </div>
          <p className="mt-6 text-gray-600 dark:text-gray-300 font-medium text-lg">Loading chat...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      <Sidebar isOpen={isSidebarOpen} onToggle={() => setIsSidebarOpen(!isSidebarOpen)} />
      <ChatInterface isSidebarOpen={isSidebarOpen} onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)} />
    </div>
  );
}