"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Organization {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  users?: User[];
}

interface User {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  organization_id: number;
  created_at: string;
}

export default function UsersPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [allUsers, setAllUsers] = useState<(User & { org_name: string })[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"all" | "active" | "inactive" | "admin">("all");
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const token = localStorage.getItem("admin_token");
      const response = await fetch(`${API_BASE_URL}/admin/organizations`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        throw new Error("Failed to fetch data");
      }

      const orgs: Organization[] = await response.json();
      setOrganizations(orgs);

      // Flatten users with org name
      const users: (User & { org_name: string })[] = [];
      orgs.forEach((org) => {
        if (org.users) {
          org.users.forEach((user) => {
            users.push({ ...user, org_name: org.name, organization_id: org.id });
          });
        }
      });
      setAllUsers(users);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users");
    } finally {
      setIsLoading(false);
    }
  };

  const toggleUserStatus = async (user: User) => {
    try {
      const token = localStorage.getItem("admin_token");
      const response = await fetch(`${API_BASE_URL}/admin/users/${user.id}`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ is_active: !user.is_active }),
      });

      if (!response.ok) {
        throw new Error("Failed to update user");
      }

      fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update user");
    }
  };

  const deleteUser = async (user: User) => {
    if (!confirm(`Are you sure you want to delete user "${user.username}"?`)) {
      return;
    }

    try {
      const token = localStorage.getItem("admin_token");
      const response = await fetch(`${API_BASE_URL}/admin/users/${user.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        throw new Error("Failed to delete user");
      }

      fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete user");
    }
  };

  // Filter and search users
  const filteredUsers = allUsers.filter((user) => {
    // Apply filter
    if (filter === "active" && !user.is_active) return false;
    if (filter === "inactive" && user.is_active) return false;
    if (filter === "admin" && !user.is_admin) return false;

    // Apply search
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        user.username.toLowerCase().includes(query) ||
        user.email.toLowerCase().includes(query) ||
        user.org_name.toLowerCase().includes(query)
      );
    }

    return true;
  });

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Users</h1>
          <p className="text-slate-500 mt-1">Manage all users across organizations</p>
        </div>
        <Link
          href="/admin/users/new"
          className="px-4 py-2 bg-[#4f46e5] hover:bg-indigo-700 text-white font-medium rounded-lg transition-colors"
        >
          + Add User
        </Link>
      </div>

      {/* Error message */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
          {error}
        </div>
      )}

      {/* Filters and search */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          {/* Search */}
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              placeholder="Search users..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4f46e5] text-slate-900"
            />
          </div>

          {/* Filter buttons */}
          <div className="flex items-center gap-2">
            {(["all", "active", "inactive", "admin"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                  filter === f
                    ? "bg-[#4f46e5] text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Users table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-slate-500">Loading...</div>
        ) : filteredUsers.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            {allUsers.length === 0
              ? "No users yet. Create an organization first, then add users."
              : "No users match your filters."}
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-600">
                  User
                </th>
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-600">
                  Organization
                </th>
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-600">
                  Role
                </th>
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-600">
                  Status
                </th>
                <th className="text-right px-6 py-4 text-sm font-medium text-slate-600">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {filteredUsers.map((user) => (
                <tr key={user.id} className="hover:bg-slate-50">
                  <td className="px-6 py-4">
                    <div>
                      <p className="font-medium text-slate-900">{user.username}</p>
                      <p className="text-sm text-slate-500">{user.email}</p>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <Link
                      href={`/admin/organizations/${user.organization_id}`}
                      className="text-[#4f46e5] hover:underline"
                    >
                      {user.org_name}
                    </Link>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        user.is_admin
                          ? "bg-purple-100 text-purple-800"
                          : "bg-slate-100 text-slate-800"
                      }`}
                    >
                      {user.is_admin ? "Admin" : "User"}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        user.is_active
                          ? "bg-green-100 text-green-800"
                          : "bg-red-100 text-red-800"
                      }`}
                    >
                      {user.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => toggleUserStatus(user)}
                        className={`px-3 py-1 text-sm rounded transition-colors ${
                          user.is_active
                            ? "text-orange-600 hover:bg-orange-50"
                            : "text-green-600 hover:bg-green-50"
                        }`}
                      >
                        {user.is_active ? "Disable" : "Enable"}
                      </button>
                      <button
                        onClick={() => deleteUser(user)}
                        className="px-3 py-1 text-sm text-red-600 hover:bg-red-50 rounded transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Summary */}
      <div className="mt-4 text-sm text-slate-500">
        Showing {filteredUsers.length} of {allUsers.length} users
      </div>
    </div>
  );
}
