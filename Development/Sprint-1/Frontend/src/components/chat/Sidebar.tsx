'use client';

import { useState } from 'react';
import { 
  MessageSquare, 
  Plus, 
  Settings, 
  Menu,
  X,
  Trash2,
  Edit3,
  Sparkles
} from 'lucide-react';
import { ContinuumIcon } from '@/components/ui/ContinuumIcon';
import { useChat } from '@/contexts/ChatContext';
import { clsx } from 'clsx';

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
}

export function Sidebar({ isOpen, onToggle }: SidebarProps) {
  const { chats, activeChat, createNewChat, selectChat, deleteChat } = useChat();
  const [editingChatId, setEditingChatId] = useState<string | null>(null);

  const handleNewChat = () => {
    createNewChat();
  };

  const handleDeleteChat = (chatId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    deleteChat(chatId);
  };

  const getLastMessage = (chat: any) => {
    const lastUserMessage = chat.messages.filter((m: any) => m.sender === 'user').pop();
    return lastUserMessage?.content || 'New conversation';
  };

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={onToggle}
        />
      )}
      
      {/* Premium Black Sidebar */}
      <div className={clsx(
        'fixed lg:relative inset-y-0 left-0 z-50 w-80 bg-black/95 backdrop-blur-xl border-r border-white/10 transform transition-all duration-300 ease-out flex flex-col shadow-xl',
        isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
      )}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-white/10">
          <div className="flex items-center space-x-4">
            <div className="w-11 h-11 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-2xl flex items-center justify-center shadow-2xl shadow-cyan-500/25 ring-1 ring-white/10">
              <ContinuumIcon size={22} className="text-black" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight">
                Continuum AI
              </h1>
              <p className="text-xs text-white/60 font-medium">Sales Intelligence</p>
            </div>
          </div>
          <button
            onClick={onToggle}
            className="lg:hidden p-2.5 rounded-xl hover:bg-white/10 transition-all duration-200 ease-out active:scale-95"
          >
            <X className="w-5 h-5 text-white/70" />
          </button>
        </div>

        {/* New Chat Button */}
        <div className="px-6 py-4">
          <button 
            onClick={handleNewChat}
            className="w-full flex items-center justify-center space-x-3 px-4 py-3 bg-gradient-to-r from-cyan-400 to-blue-500 text-black rounded-2xl hover:from-cyan-300 hover:to-blue-400 transition-all duration-300 ease-out shadow-2xl shadow-cyan-500/25 hover:shadow-cyan-500/40 transform hover:scale-105 active:scale-95 font-semibold ring-1 ring-white/20"
          >
            <Plus className="w-5 h-5" />
            <span>New Chat</span>
          </button>
        </div>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto px-6 pb-6">
          <h2 className="text-sm font-semibold text-white/60 mb-4 uppercase tracking-wider">
            Recent Chats
          </h2>
          <div className="space-y-2">
            {chats.map((chat) => (
              <div
                key={chat.id}
                onClick={() => selectChat(chat.id)}
                className={clsx(
                  'group relative p-4 rounded-2xl cursor-pointer transition-all duration-300 ease-out',
                  activeChat?.id === chat.id
                    ? 'bg-cyan-400/20 border border-cyan-400/30 shadow-sm'
                    : 'hover:bg-white/10 border border-transparent'
                )}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-white truncate mb-1">
                      {chat.title}
                    </h3>
                    <p className="text-xs text-white/60 truncate mb-2">
                      {getLastMessage(chat)}
                    </p>
                    <p className="text-xs text-white/50 font-medium">
                      {chat.updatedAt.toLocaleDateString()}
                    </p>
                  </div>
                  <div className="opacity-0 group-hover:opacity-100 transition-all duration-300 ease-out flex space-x-1 ml-3">
                    <button 
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingChatId(chat.id);
                      }}
                      className="p-2 rounded-xl hover:bg-white/10 transition-all duration-200 ease-out active:scale-95"
                    >
                      <Edit3 className="w-4 h-4 text-white/70" />
                    </button>
                    <button 
                      onClick={(e) => handleDeleteChat(chat.id, e)}
                      className="p-2 rounded-xl hover:bg-red-500/20 transition-all duration-200 ease-out active:scale-95"
                    >
                      <Trash2 className="w-4 h-4 text-red-400" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Settings */}
        <div className="px-6 py-4 border-t border-white/10">
          <button className="w-full flex items-center space-x-3 px-4 py-3 text-white/80 hover:bg-white/10 rounded-2xl transition-all duration-300 ease-out active:scale-95">
            <Settings className="w-5 h-5" />
            <span className="text-sm font-semibold">Settings</span>
          </button>
        </div>
      </div>
    </>
  );
}
