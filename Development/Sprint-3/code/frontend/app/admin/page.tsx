"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Stats {
  totalOrganizations: number;
  totalUsers: number;
  activeOrganizations: number;
  activeUsers: number;
}

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<Stats>({
    totalOrganizations: 0,
    totalUsers: 0,
    activeOrganizations: 0,
    activeUsers: 0,
  });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const token = localStorage.getItem("admin_token");
      
      // Fetch organizations
      const orgsResponse = await fetch(`${API_BASE_URL}/admin/organizations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (orgsResponse.ok) {
        const orgs = await orgsResponse.json();
        
        // Calculate stats
        const activeOrgs = orgs.filter((o: { is_active: boolean }) => o.is_active);
        let totalUsers = 0;
        let activeUsers = 0;
        
        orgs.forEach((org: { users?: { is_active: boolean }[] }) => {
          if (org.users) {
            totalUsers += org.users.length;
            activeUsers += org.users.filter((u: { is_active: boolean }) => u.is_active).length;
          }
        });
        
        setStats({
          totalOrganizations: orgs.length,
          activeOrganizations: activeOrgs.length,
          totalUsers,
          activeUsers,
        });
      }
    } catch (error) {
      console.error("Failed to fetch stats:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const statCards = [
    {
      label: "Total Organizations",
      value: stats.totalOrganizations,
      icon: "🏢",
      color: "bg-blue-500",
    },
    {
      label: "Active Organizations",
      value: stats.activeOrganizations,
      icon: "✅",
      color: "bg-green-500",
    },
    {
      label: "Total Users",
      value: stats.totalUsers,
      icon: "👥",
      color: "bg-purple-500",
    },
    {
      label: "Active Users",
      value: stats.activeUsers,
      icon: "🟢",
      color: "bg-[#4f46e5]",
    },
  ];

  const quickActions = [
    {
      label: "Add Organization",
      href: "/admin/organizations/new",
      icon: "➕",
      description: "Create a new organization",
    },
    {
      label: "Add User",
      href: "/admin/users/new",
      icon: "👤",
      description: "Add a new user to an organization",
    },
    {
      label: "Manage Datasets",
      href: "/admin/datasets",
      icon: "📁",
      description: "Assign datasets to organizations",
    },
  ];

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-slate-500 mt-1">Welcome to the admin panel</p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {statCards.map((card) => (
          <div
            key={card.label}
            className="bg-white rounded-xl shadow-sm p-6 border border-slate-200"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">{card.label}</p>
                <p className="text-3xl font-bold text-slate-900 mt-1">
                  {isLoading ? "..." : card.value}
                </p>
              </div>
              <div
                className={`w-12 h-12 ${card.color} rounded-lg flex items-center justify-center text-2xl`}
              >
                {card.icon}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick actions */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">
          Quick Actions
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {quickActions.map((action) => (
            <Link
              key={action.label}
              href={action.href}
              className="bg-white rounded-xl shadow-sm p-6 border border-slate-200 hover:border-indigo-300 hover:shadow-md transition-all group"
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-slate-100 group-hover:bg-indigo-100 rounded-lg flex items-center justify-center text-xl transition-colors">
                  {action.icon}
                </div>
                <div>
                  <p className="font-medium text-slate-900">{action.label}</p>
                  <p className="text-sm text-slate-500">{action.description}</p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Recent activity placeholder */}
      <div>
        <h2 className="text-xl font-semibold text-slate-900 mb-4">
          System Status
        </h2>
        <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-200">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-slate-600">All systems operational</span>
          </div>
        </div>
      </div>
    </div>
  );
}
