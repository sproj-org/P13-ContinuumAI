'use client';

import { useState } from 'react';
import { Sidebar } from '@/components/chat/Sidebar';
import { ChatInterface } from '@/components/chat/ChatInterface';

export default function ChatPage() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      <Sidebar isOpen={isSidebarOpen} onToggle={() => setIsSidebarOpen(!isSidebarOpen)} />
      <ChatInterface isSidebarOpen={isSidebarOpen} onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)} />
    </div>
  );
}
