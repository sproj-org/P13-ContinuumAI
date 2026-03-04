"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Organization {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  users?: { id: number; username: string; is_active: boolean }[];
  datasets?: { id: number; dataset_name: string }[];
}

export default function OrganizationsPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchOrganizations();
  }, []);

  const fetchOrganizations = async () => {
    try {
      const token = localStorage.getItem("admin_token");
      const response = await fetch(`${API_BASE_URL}/admin/organizations`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        throw new Error("Failed to fetch organizations");
      }

      const data = await response.json();
      setOrganizations(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load organizations");
    } finally {
      setIsLoading(false);
    }
  };

  const toggleOrgStatus = async (org: Organization) => {
    try {
      const token = localStorage.getItem("admin_token");
      const response = await fetch(
        `${API_BASE_URL}/admin/organizations/${org.id}`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ is_active: !org.is_active }),
        }
      );

      if (!response.ok) {
        throw new Error("Failed to update organization");
      }

      // Refresh list
      fetchOrganizations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update organization");
    }
  };

  const deleteOrganization = async (org: Organization) => {
    if (!confirm(`Are you sure you want to delete "${org.name}"? This will also delete all associated users.`)) {
      return;
    }

    try {
      const token = localStorage.getItem("admin_token");
      const response = await fetch(
        `${API_BASE_URL}/admin/organizations/${org.id}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!response.ok) {
        throw new Error("Failed to delete organization");
      }

      fetchOrganizations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete organization");
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Organizations</h1>
          <p className="text-slate-500 mt-1">Manage organization accounts</p>
        </div>
        <Link
          href="/admin/organizations/new"
          className="px-4 py-2 bg-[#4f46e5] hover:bg-indigo-700 text-white font-medium rounded-lg transition-colors"
        >
          + Add Organization
        </Link>
      </div>

      {/* Error message */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
          {error}
        </div>
      )}

      {/* Organizations table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-slate-500">Loading...</div>
        ) : organizations.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            No organizations yet.{" "}
            <Link href="/admin/organizations/new" className="text-[#4f46e5] hover:underline">
              Create one
            </Link>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-600">
                  Organization
                </th>
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-600">
                  Users
                </th>
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-600">
                  Datasets
                </th>
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-600">
                  Status
                </th>
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-600">
                  Created
                </th>
                <th className="text-right px-6 py-4 text-sm font-medium text-slate-600">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {organizations.map((org) => (
                <tr key={org.id} className="hover:bg-slate-50">
                  <td className="px-6 py-4">
                    <div>
                      <p className="font-medium text-slate-900">{org.name}</p>
                      <p className="text-sm text-slate-500">{org.slug}</p>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-slate-600">
                      {org.users?.length || 0} users
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-slate-600">
                      {org.datasets?.length || 0} datasets
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        org.is_active
                          ? "bg-green-100 text-green-800"
                          : "bg-red-100 text-red-800"
                      }`}
                    >
                      {org.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-500">
                    {new Date(org.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        href={`/admin/organizations/${org.id}`}
                        className="px-3 py-1 text-sm text-[#4f46e5] hover:bg-indigo-50 rounded transition-colors"
                      >
                        Edit
                      </Link>
                      <button
                        onClick={() => toggleOrgStatus(org)}
                        className={`px-3 py-1 text-sm rounded transition-colors ${
                          org.is_active
                            ? "text-orange-600 hover:bg-orange-50"
                            : "text-green-600 hover:bg-green-50"
                        }`}
                      >
                        {org.is_active ? "Disable" : "Enable"}
                      </button>
                      <button
                        onClick={() => deleteOrganization(org)}
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
    </div>
  );
}
