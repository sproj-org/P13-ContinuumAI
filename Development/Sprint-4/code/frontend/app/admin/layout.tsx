"use client";

import { useEffect, useSyncExternalStore } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";

const ADMIN_AUTH_EVENT = "continuum-admin-auth-change";

type AdminUser = { username: string };

function subscribeToAdminAuth(callback: () => void) {
  if (typeof window === "undefined") {
    return () => undefined;
  }

  const handleChange = () => callback();
  window.addEventListener("storage", handleChange);
  window.addEventListener(ADMIN_AUTH_EVENT, handleChange);
  return () => {
    window.removeEventListener("storage", handleChange);
    window.removeEventListener(ADMIN_AUTH_EVENT, handleChange);
  };
}

function getAdminAuthSnapshot(): {
  isAuthenticated: boolean;
  adminUser: AdminUser | null;
  isReady: boolean;
} {
  if (typeof window === "undefined") {
    return {
      isAuthenticated: false,
      adminUser: null,
      isReady: false,
    };
  }

  const token = localStorage.getItem("admin_token");
  const rawUser = localStorage.getItem("admin_user");
  const adminUser = rawUser ? (JSON.parse(rawUser) as AdminUser) : null;
  return {
    isAuthenticated: Boolean(token && adminUser),
    adminUser,
    isReady: true,
  };
}

// Admin layout with sidebar navigation
export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, adminUser, isReady } = useSyncExternalStore(
    subscribeToAdminAuth,
    getAdminAuthSnapshot,
    () => ({
      isAuthenticated: false,
      adminUser: null,
      isReady: false,
    }),
  );

  useEffect(() => {
    if (isReady && !isAuthenticated && pathname !== "/admin/login") {
      router.push("/admin/login");
    }
  }, [isAuthenticated, isReady, pathname, router]);

  const handleLogout = () => {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_user");
    window.dispatchEvent(new Event(ADMIN_AUTH_EVENT));
    router.push("/admin/login");
  };

  // Show loading state
  if (!isReady) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-slate-100">
        <div className="text-lg text-slate-600">Loading...</div>
      </div>
    );
  }

  // Show login page without layout
  if (pathname === "/admin/login") {
    return <>{children}</>;
  }

  // Show protected content with layout
  if (!isAuthenticated) {
    return null;
  }

  const navItems = [
    { href: "/admin", label: "Dashboard", icon: "📊" },
    { href: "/admin/organizations", label: "Organizations", icon: "🏢" },
    { href: "/admin/users", label: "Users", icon: "👥" },
    { href: "/admin/datasets", label: "Datasets", icon: "📁" },
  ];

  return (
    <div className="min-h-screen bg-slate-100 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 text-white flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-slate-700">
          <h1 className="text-xl font-bold">ContinuumAI</h1>
          <p className="text-sm text-slate-400">Admin Panel</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4">
          <ul className="space-y-2">
            {navItems.map((item) => {
              const isActive = pathname === item.href || 
                (item.href !== "/admin" && pathname.startsWith(item.href));
              
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                      isActive
                        ? "bg-[#4f46e5] text-white"
                        : "text-slate-300 hover:bg-slate-800"
                    }`}
                  >
                    <span>{item.icon}</span>
                    <span>{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* User info & logout */}
        <div className="p-4 border-t border-slate-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">{adminUser?.username}</p>
              <p className="text-xs text-slate-400">Administrator</p>
            </div>
            <button
              onClick={handleLogout}
              className="px-3 py-1 text-sm bg-slate-700 hover:bg-slate-600 rounded transition-colors"
            >
              Logout
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 p-8 overflow-auto">
        {children}
      </main>
    </div>
  );
}
