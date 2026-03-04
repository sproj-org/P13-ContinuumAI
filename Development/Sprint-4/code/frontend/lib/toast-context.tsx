"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, XCircle, AlertCircle, Info, X } from "lucide-react";

type ToastType = "success" | "error" | "warning" | "info";

interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
}

interface ToastContextType {
  showToast: (message: string, type?: ToastType, duration?: number) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return context;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback(
    (message: string, type: ToastType = "success", duration: number = 3000) => {
      const id = Math.random().toString(36).substring(2, 9);
      const newToast: Toast = { id, message, type, duration };

      setToasts((prev) => [...prev, newToast]);

      if (duration > 0) {
        setTimeout(() => {
          setToasts((prev) => prev.filter((t) => t.id !== id));
        }, duration);
      }
    },
    []
  );

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const getToastStyles = (type: ToastType) => {
    switch (type) {
      case "success":
        return {
          bg: "bg-white/95",
          border: "border-emerald-200",
          icon: CheckCircle2,
          iconColor: "text-emerald-600",
          iconBg: "bg-emerald-100",
          shadow: "shadow-emerald-500/20",
        };
      case "error":
        return {
          bg: "bg-white/95",
          border: "border-red-200",
          icon: XCircle,
          iconColor: "text-red-600",
          iconBg: "bg-red-100",
          shadow: "shadow-red-500/20",
        };
      case "warning":
        return {
          bg: "bg-white/95",
          border: "border-amber-200",
          icon: AlertCircle,
          iconColor: "text-amber-600",
          iconBg: "bg-amber-100",
          shadow: "shadow-amber-500/20",
        };
      case "info":
        return {
          bg: "bg-white/95",
          border: "border-cyan-200",
          icon: Info,
          iconColor: "text-cyan-600",
          iconBg: "bg-cyan-100",
          shadow: "shadow-cyan-500/20",
        };
    }
  };

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed top-4 right-4 z-50 pointer-events-none flex flex-col gap-2">
        <AnimatePresence mode="popLayout">
          {toasts.map((toast) => {
            const styles = getToastStyles(toast.type);
            const Icon = styles.icon;

            return (
              <motion.div
                key={toast.id}
                layout
                initial={{ opacity: 0, y: -20, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, x: 100, scale: 0.95 }}
                transition={{ type: "spring", stiffness: 500, damping: 40 }}
                className={`${styles.bg} ${styles.border} border backdrop-blur-xl rounded-xl shadow-xl ${styles.shadow} pointer-events-auto min-w-[320px] max-w-md overflow-hidden`}
              >
                <div className="flex items-center gap-3 p-4">
                  <div className={`w-10 h-10 rounded-lg ${styles.iconBg} flex items-center justify-center flex-shrink-0`}>
                    <Icon className={`w-5 h-5 ${styles.iconColor}`} />
                  </div>
                  <p className="flex-1 text-sm font-medium text-slate-900">
                    {toast.message}
                  </p>
                  <button
                    onClick={() => removeToast(toast.id)}
                    className="flex-shrink-0 w-6 h-6 rounded-md hover:bg-slate-100 flex items-center justify-center transition-colors"
                  >
                    <X className="w-4 h-4 text-slate-400" />
                  </button>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}
