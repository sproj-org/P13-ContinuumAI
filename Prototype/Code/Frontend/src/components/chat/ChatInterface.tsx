'use client';

import { useState, useRef, useEffect } from 'react';
import { 
  Send, 
  Menu,
  Bot,
  User,
  Copy,
  ThumbsUp,
  ThumbsDown,
  MoreHorizontal,
  Sparkles,
  Plus,
  ArrowUp,
  Paperclip
} from 'lucide-react';
import { ContinuumIcon } from '@/components/ui/ContinuumIcon';
import { useChat } from '@/contexts/ChatContext';
import { clsx } from 'clsx';
import PlotlyCard from '@/components/plotly/PlotlyCard';
import { runQuery } from '@/lib/query';

interface ChatInterfaceProps {
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
}

export function ChatInterface({ isSidebarOpen, onToggleSidebar }: ChatInterfaceProps) {
  const { activeChat, addMessage, isTyping, setIsTyping } = useChat();
  const [inputValue, setInputValue] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [activeChat?.messages]);

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      const newFiles = Array.from(files);
      setUploadedFiles(prev => [...prev, ...newFiles]);
    }
  };

  const removeFile = (index: number) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleFileButtonClick = () => {
    fileInputRef.current?.click();
  };

  const handleSend = async () => {
    if ((!inputValue.trim() && uploadedFiles.length === 0) || !activeChat) return;

    // Create message content with file information
    let messageContent = inputValue;
    if (uploadedFiles.length > 0) {
      const fileNames = uploadedFiles.map(file => file.name).join(', ');
      messageContent = inputValue 
        ? `${inputValue}\n\n📎 Files: ${fileNames}` 
        : `📎 Files: ${fileNames}`;
    }

    // Add user message
    addMessage(activeChat.id, {
      content: messageContent,
      sender: 'user'
    });
    
    setInputValue('');
    setUploadedFiles([]);
    setIsTyping(true);

    try {
  const res = await runQuery({ message: inputValue.trim() || ' ' });
  if (res.status === 'success' && res.results?.length) {
    for (const fig of res.results) {
      addMessage(activeChat.id, {
        content: '[plotly]',
        sender: 'ai',
        metadata: fig, // Message type needs: metadata?: any
      } as any);
    }
  } else {
    addMessage(activeChat.id, {
      content: res.message || "I'm sorry, I couldn't find that data.",
      sender: 'ai',
    });
  }
} catch {
  addMessage(activeChat.id, { content: 'Error contacting orchestrator.', sender: 'ai' });
} finally {
  setIsTyping(false);
}


    
    // Simulate AI response
    // setTimeout(() => {
    //   const responses = [
    //     'Thank you for your message! I\'m here to help you with sales insights, market analysis, and strategic recommendations. What specific area would you like to explore?',
    //     'Great question! Based on current market trends, I can provide you with detailed analytics and actionable insights. Would you like me to dive deeper into any particular aspect?',
    //     'I\'d be happy to help you with that! Let me analyze the data and provide you with comprehensive insights that can drive your sales strategy forward.',
    //     'Excellent! I can assist you with advanced sales intelligence, customer behavior analysis, and market forecasting. What would you like to focus on first?'
    //   ];
      
    //   const randomResponse = responses[Math.floor(Math.random() * responses.length)];
      
    //   addMessage(activeChat.id, {
    //     content: randomResponse,
    //     sender: 'ai'
    //   });
    //   setIsTyping(false);
    // }, 1500);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const adjustTextareaHeight = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }
  };

  useEffect(() => {
    adjustTextareaHeight();
  }, [inputValue]);

  if (!activeChat) {
    return (
      <div className="flex flex-col flex-1 h-screen bg-black">
        {/* Premium header */}
        <div className="flex items-center justify-between px-6 py-4 bg-black/95 backdrop-blur-xl border-b border-white/10">
          <button
            onClick={onToggleSidebar}
            className="lg:hidden p-2.5 rounded-xl hover:bg-white/10 transition-all duration-200 ease-out"
          >
            <Menu className="w-5 h-5 text-white/70" />
          </button>
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-2xl flex items-center justify-center shadow-2xl shadow-cyan-500/25 ring-1 ring-white/10">
              <ContinuumIcon size={20} className="text-black" />
            </div>
            <h1 className="text-lg font-semibold text-white tracking-tight">Continuum AI</h1>
          </div>
          <button className="p-2.5 rounded-xl hover:bg-white/10 transition-all duration-200 ease-out active:scale-95">
            <MoreHorizontal className="w-5 h-5 text-white/70" />
          </button>
        </div>

        {/* Premium welcome content */}
        <div className="flex items-center justify-center flex-1 px-6">
          <div className="text-center max-w-2xl">
            <div className="relative mb-12">
              <div className="w-32 h-32 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-3xl flex items-center justify-center mx-auto shadow-2xl shadow-cyan-500/25 transform rotate-2 hover:rotate-0 transition-all duration-700 ring-1 ring-white/10">
                <ContinuumIcon size={64} className="text-black" />
              </div>
              <div className="absolute -top-2 -right-2 w-8 h-8 bg-green-400 rounded-full flex items-center justify-center animate-pulse">
                <div className="w-3 h-3 bg-white rounded-full"></div>
              </div>
            </div>
            
            <h2 className="text-5xl font-bold text-white mb-6 tracking-tight">
              Welcome to Continuum AI
            </h2>
            <p className="text-xl text-white/70 mb-12 leading-relaxed max-w-xl mx-auto font-medium">
              Your intelligent sales assistant is ready to transform your business with AI-powered insights, market analysis, and strategic recommendations.
            </p>
            
            <div className="bg-white/5 backdrop-blur-xl rounded-2xl p-8 border border-white/10 max-w-md mx-auto">
              <div className="flex items-center justify-center space-x-2 mb-4">
                <div className="w-2 h-2 bg-cyan-400 rounded-full animate-pulse"></div>
                <p className="text-sm font-medium text-white/60 uppercase tracking-wider">Get Started</p>
              </div>
              <p className="text-white/80 font-medium">
                Start a new conversation or upload files to begin your AI-powered sales journey
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1 h-screen bg-black">
      {/* Premium Header */}
      <div className="flex items-center justify-between px-6 py-4 bg-black/95 backdrop-blur-xl border-b border-white/10 sticky top-0 z-10">
        <div className="flex items-center space-x-4">
          <button
            onClick={onToggleSidebar}
            className="lg:hidden p-2.5 rounded-xl hover:bg-white/10 transition-all duration-200 ease-out active:scale-95"
          >
            <Menu className="w-5 h-5 text-white/70" />
          </button>
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-2xl flex items-center justify-center shadow-2xl shadow-cyan-500/25 ring-1 ring-white/10">
              <ContinuumIcon size={24} className="text-black" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight">New Chat</h1>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                <p className="text-sm text-white/60 font-medium">
                  AI Assistant • Online
                </p>
              </div>
            </div>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <button className="p-2.5 rounded-xl hover:bg-white/10 transition-all duration-200 ease-out active:scale-95">
            <MoreHorizontal className="w-5 h-5 text-white/70" />
          </button>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-6 py-8 space-y-6">
        {activeChat.messages.map((message, index) => (
          <div
            key={message.id}
            className={clsx(
              'flex animate-in slide-in-from-bottom-4 duration-500 ease-out',
              message.sender === 'user' ? 'justify-end' : 'justify-start'
            )}
            style={{ animationDelay: `${index * 100}ms` }}
          >
            {/* AI Message Layout */}
            {message.sender === 'ai' && (
              <>
                {/* AI Avatar */}
                <div className="flex-shrink-0 w-11 h-11 rounded-2xl flex items-center justify-center shadow-2xl bg-gradient-to-br from-cyan-400 to-blue-500 shadow-cyan-500/25 mr-4 ring-1 ring-white/10">
                  <Sparkles className="w-5 h-5 text-black" />
                </div>
                
                {/* AI Message Content */}
                <div className="group relative max-w-2xl">
                  <div className="px-6 py-4 rounded-2xl shadow-lg transition-all duration-300 ease-out hover:shadow-xl bg-white/10 backdrop-blur-xl text-white border border-white/20 hover:border-white/30 hover:bg-white/15">
{message.content === '[plotly]' && message.metadata ? (
  <PlotlyCard figure={message.metadata} />
) : (
  <p className="text-[15px] leading-relaxed whitespace-pre-wrap font-medium">
    {message.content}
  </p>
)}

                  </div>
                  
                  {/* AI Message Actions */}
                  <div className="flex items-center mt-3 space-x-3 opacity-0 group-hover:opacity-100 transition-all duration-300 ease-out justify-start">
                    <span className="text-xs text-white/60 font-medium">
                      {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                    <div className="flex space-x-1">
                      <button className="p-2 rounded-xl hover:bg-white/10 transition-all duration-200 ease-out active:scale-95">
                        <Copy className="w-4 h-4 text-white/70" />
                      </button>
                      <button className="p-2 rounded-xl hover:bg-white/10 transition-all duration-200 ease-out active:scale-95">
                        <ThumbsUp className="w-4 h-4 text-white/70" />
                      </button>
                      <button className="p-2 rounded-xl hover:bg-white/10 transition-all duration-200 ease-out active:scale-95">
                        <ThumbsDown className="w-4 h-4 text-white/70" />
                      </button>
                    </div>
                  </div>
                </div>
              </>
            )}

            {/* User Message Layout */}
            {message.sender === 'user' && (
              <>
                {/* User Message Content */}
                <div className="group relative max-w-2xl">
                  <div className="px-6 py-4 rounded-2xl shadow-2xl transition-all duration-300 ease-out hover:shadow-cyan-500/40 bg-gradient-to-br from-cyan-400 to-blue-500 text-black shadow-cyan-500/25 hover:from-cyan-300 hover:to-blue-400 ring-1 ring-white/20">
                    <p className="text-[15px] leading-relaxed whitespace-pre-wrap font-semibold">
                      {message.content}
                    </p>
                  </div>
                  
                  {/* User Message Actions */}
                  <div className="flex items-center mt-3 space-x-3 opacity-0 group-hover:opacity-100 transition-all duration-300 ease-out justify-end">
                    <span className="text-xs text-white/60 font-medium">
                      {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                </div>
                
                {/* User Avatar */}
                <div className="flex-shrink-0 w-11 h-11 rounded-2xl flex items-center justify-center shadow-lg bg-white/10 backdrop-blur-xl ml-4 border border-white/20">
                  <User className="w-5 h-5 text-white" />
                </div>
              </>
            )}
          </div>
        ))}

        {/* Modern Typing indicator */}
        {isTyping && (
          <div className="flex space-x-4 animate-in slide-in-from-bottom-4 duration-300 ease-out">
            <div className="flex-shrink-0 w-10 h-10 bg-gradient-to-br from-blue-600 to-blue-500 rounded-2xl flex items-center justify-center shadow-sm shadow-blue-500/20">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div className="bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700/80 rounded-2xl px-5 py-4 shadow-sm">
              <div className="flex space-x-2">
                <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Premium Input Area */}
      <div className="px-6 py-4 bg-black/95 backdrop-blur-xl border-t border-white/10 shadow-sm">
        <div className="max-w-4xl mx-auto">
          {/* Uploaded Files Display */}
          {uploadedFiles.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {uploadedFiles.map((file, index) => (
                <div key={index} className="flex items-center space-x-2 bg-cyan-400/20 px-3 py-2 rounded-xl border border-cyan-400/30">
                  <Paperclip className="w-4 h-4 text-cyan-400" />
                  <span className="text-sm font-medium text-cyan-300 truncate max-w-32">
                    {file.name}
                  </span>
                  <button
                    onClick={() => removeFile(index)}
                    className="text-cyan-400 hover:text-cyan-300 transition-colors"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
          
          <div className="relative flex items-end space-x-3 bg-white/10 rounded-2xl border border-white/20 focus-within:border-cyan-400 transition-all duration-300 ease-out shadow-sm hover:shadow-md">
            {/* File Upload Button */}
            <button
              onClick={handleFileButtonClick}
              className="flex-shrink-0 p-3 rounded-xl hover:bg-white/10 transition-all duration-200 ease-out active:scale-95 m-2"
              title="Upload files"
            >
              <Paperclip className="w-5 h-5 text-white/70" />
            </button>
            
            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Message Continuum AI..."
              className="flex-1 resize-none bg-transparent py-4 text-white placeholder-white/60 focus:outline-none min-h-[52px] max-h-[120px] text-[15px] font-medium"
              rows={1}
            />
            
            <button
              onClick={handleSend}
              disabled={!inputValue.trim() && uploadedFiles.length === 0}
              className={clsx(
                'flex-shrink-0 w-11 h-11 rounded-xl transition-all duration-300 ease-out my-2 mr-3 ml-2 flex items-center justify-center',
                (inputValue.trim() || uploadedFiles.length > 0)
                  ? 'bg-gradient-to-r from-cyan-400 to-blue-500 text-black hover:from-cyan-300 hover:to-blue-400 shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 transform hover:scale-105 active:scale-95'
                  : 'bg-white/10 text-white/40 cursor-not-allowed'
              )}
            >
              <ArrowUp className="w-4 h-4 ml-0.5" />
            </button>
          </div>
          
          {/* Hidden File Input */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileUpload}
            className="hidden"
            accept=".pdf,.doc,.docx,.txt,.csv,.xlsx,.xls,.png,.jpg,.jpeg,.gif"
          />
          
          <p className="text-xs text-white/60 mt-3 text-center font-medium">
            Continuum AI can make mistakes. Consider checking important information.
          </p>
        </div>
      </div>
    </div>
  );
}
