# 🤖 Continuum AI - Sales Intelligence Platform

A modern, AI-powered sales intelligence platform built with Next.js 16, featuring a beautiful chat interface, comprehensive dashboard, and seamless user experience.

![Continuum AI](https://img.shields.io/badge/Next.js-16.0.1-black?style=for-the-badge&logo=next.js)
![React](https://img.shields.io/badge/React-19.2.0-blue?style=for-the-badge&logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue?style=for-the-badge&logo=typescript)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4.0-38B2AC?style=for-the-badge&logo=tailwind-css)

## ✨ Features

### 🎨 **Modern Design System**
- **Consistent Theme**: Unified slate-based color palette across all components
- **Inter Font**: Premium typography for enhanced readability
- **Dark/Light Mode**: Seamless theme switching with system preference detection
- **Responsive Design**: Mobile-first approach with perfect desktop experience
- **Smooth Animations**: Buttery smooth transitions and micro-interactions

### 💬 **AI Chat Interface**
- **Real-time Messaging**: Instant AI responses with typing indicators
- **File Upload**: Support for documents, images, and spreadsheets
- **Message Actions**: Copy, like/dislike functionality
- **Chat History**: Persistent conversation management
- **Auto-expanding Input**: Smart textarea that grows with content

### 📊 **Dashboard**
- **User Profile**: Comprehensive user information display
- **Statistics Grid**: Key metrics and insights visualization
- **Quick Actions**: Direct access to AI chat and features
- **Modern Cards**: Clean, interactive component design

### 🔐 **Authentication**
- **Secure Login/Register**: Complete authentication system
- **Form Validation**: Real-time input validation
- **Error Handling**: User-friendly error messages
- **Session Management**: Persistent login state

## 🚀 Quick Start

### Prerequisites

- **Node.js** 18.0 or later
- **npm** or **yarn** package manager

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/continuum-ai.git
   cd continuum-ai/Prototype/Code/Frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   # or
   yarn install
   ```

3. **Run the development server**
   ```bash
   npm run dev
   # or
   yarn dev
   ```

4. **Open your browser**
   Navigate to [http://localhost:3000](http://localhost:3000)

## 📦 Dependencies

### Core Dependencies
- **Next.js 16.0.1** - React framework with App Router
- **React 19.2.0** - UI library with latest features
- **TypeScript 5.0** - Type-safe JavaScript
- **Tailwind CSS 4.0** - Utility-first CSS framework

### UI & Icons
- **Lucide React 0.552.0** - Beautiful, customizable icons
- **clsx 2.1.1** - Conditional className utility
- **class-variance-authority 0.7.1** - Component variant management

### Development Tools
- **ESLint 9.0** - Code linting and formatting
- **PostCSS** - CSS processing
- **Babel React Compiler** - React optimization

## 📁 Project Structure

```
src/
├── app/                    # Next.js App Router
│   ├── auth/              # Authentication pages
│   │   └── page.tsx       # Login/Register page
│   ├── chat/              # Chat interface
│   │   └── page.tsx       # Main chat page
│   ├── dashboard/         # User dashboard
│   │   └── page.tsx       # Dashboard page
│   ├── globals.css        # Global styles & design system
│   ├── layout.tsx         # Root layout component
│   └── page.tsx           # Landing page
├── components/            # Reusable UI components
│   ├── chat/             # Chat-specific components
│   │   ├── ChatInterface.tsx  # Main chat interface
│   │   └── Sidebar.tsx        # Chat history sidebar
│   ├── ui/               # Generic UI components
│   │   └── ThemeToggle.tsx    # Dark/light mode toggle
│   ├── LoginForm.tsx     # Login form component
│   └── RegisterForm.tsx  # Registration form component
├── contexts/             # React Context providers
│   ├── AuthContext.tsx   # Authentication state management
│   └── ChatContext.tsx   # Chat state management
└── lib/                  # Utility functions
    └── api.ts            # API helper functions
```

## 🎨 Design System

### Color Palette
- **Primary**: Blue (blue-600, blue-700)
- **Neutral**: Slate (slate-50 to slate-950)
- **Success**: Green (green-600)
- **Warning**: Yellow (yellow-500)
- **Error**: Red (red-500)

### Typography
- **Font Family**: Inter (Google Fonts)
- **Weights**: 400 (Regular), 500 (Medium), 600 (Semibold), 700 (Bold)
- **Features**: Optimized for readability and modern aesthetics

### Components
- **Border Radius**: Consistent rounded-2xl (16px) for modern look
- **Shadows**: Subtle shadows with proper elevation
- **Spacing**: 4px grid system for consistent spacing
- **Animations**: 300ms duration with ease-out timing

## 🛠️ Available Scripts

```bash
# Development
npm run dev          # Start development server
npm run build        # Build for production
npm run start        # Start production server
npm run lint         # Run ESLint

# Type Checking
npx tsc --noEmit     # Check TypeScript types
```

## 🌐 Environment Setup

Create a `.env.local` file in the root directory:

```env
# Add your environment variables here
NEXT_PUBLIC_API_URL=your_api_url
```

## 📱 Responsive Breakpoints

- **Mobile**: < 768px
- **Tablet**: 768px - 1024px
- **Desktop**: > 1024px

## 🎯 Key Features Implementation

### Chat Interface
- **Real-time messaging** with smooth animations
- **File upload** with drag-and-drop support
- **Message persistence** using React Context
- **Typing indicators** for better UX

### Authentication
- **Form validation** with real-time feedback
- **Secure state management** with Context API
- **Responsive design** for all devices

### Dashboard
- **Statistics visualization** with modern cards
- **User profile management**
- **Quick navigation** to key features

## 🚀 Deployment

### Vercel (Recommended)
1. Push your code to GitHub
2. Connect your repository to Vercel
3. Deploy automatically with each push

### Manual Deployment
```bash
npm run build
npm run start
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Design Inspiration**: Linear, Notion, and modern SaaS applications
- **Icons**: Lucide React icon library
- **Fonts**: Inter by Google Fonts
- **Framework**: Next.js team for the amazing framework

---
