'use client';

import React, { createContext, useContext, useState, ReactNode } from 'react';
import type { PlotlyChart } from '@/lib/mockApiResponses';

export interface Message {
  id: string;
  content: string;
  sender: 'user' | 'ai';
  timestamp: Date;
  chartData?: PlotlyChart[]; // Optional chart data for AI responses
}

export interface Chat {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

interface ChatContextType {
  chats: Chat[];
  activeChat: Chat | null;
  createNewChat: () => string;
  selectChat: (chatId: string) => void;
  deleteChat: (chatId: string) => void;
  updateChatTitle: (chatId: string, title: string) => void;
  addMessage: (chatId: string, message: Omit<Message, 'id' | 'timestamp'>) => void;
  isTyping: boolean;
  setIsTyping: (typing: boolean) => void;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [chats, setChats] = useState<Chat[]>([]);
  
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [isTyping, setIsTyping] = useState(false);

  const activeChat = chats.find(chat => chat.id === activeChatId) || null;

  const createNewChat = (): string => {
    const newChatId = Date.now().toString();
    const newChat: Chat = {
      id: newChatId,
      title: 'New Chat',
      messages: [
        {
          id: `${newChatId}_1`,
          content: 'Hello! I\'m Continuum AI, your sales intelligence assistant. How can I help you today?',
          sender: 'ai',
          timestamp: new Date()
        }
      ],
      createdAt: new Date(),
      updatedAt: new Date()
    };

    setChats(prev => [newChat, ...prev]);
    setActiveChatId(newChatId);
    return newChatId;
  };

  const selectChat = (chatId: string) => {
    setActiveChatId(chatId);
  };

  const deleteChat = (chatId: string) => {
    setChats(prev => {
      const filtered = prev.filter(chat => chat.id !== chatId);
      // If we deleted the active chat, select the first remaining chat or null
      if (chatId === activeChatId) {
        setActiveChatId(filtered.length > 0 ? filtered[0].id : null);
      }
      return filtered;
    });
  };

  const updateChatTitle = (chatId: string, title: string) => {
    setChats(prev => prev.map(chat => 
      chat.id === chatId 
        ? { ...chat, title, updatedAt: new Date() }
        : chat
    ));
  };

  const addMessage = (chatId: string, messageData: Omit<Message, 'id' | 'timestamp'>) => {
    const message: Message = {
      ...messageData,
      id: `${chatId}_${Date.now()}`,
      timestamp: new Date()
    };

    setChats(prev => prev.map(chat => 
      chat.id === chatId 
        ? { 
            ...chat, 
            messages: [...chat.messages, message],
            updatedAt: new Date(),
            // Auto-update title based on first user message
            title: chat.title === 'New Chat' && messageData.sender === 'user' 
              ? messageData.content.slice(0, 30) + (messageData.content.length > 30 ? '...' : '')
              : chat.title
          }
        : chat
    ));
  };

  return (
    <ChatContext.Provider value={{
      chats,
      activeChat,
      createNewChat,
      selectChat,
      deleteChat,
      updateChatTitle,
      addMessage,
      isTyping,
      setIsTyping
    }}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
}
