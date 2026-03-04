"use client";

import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface User {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

interface Dataset {
  id: number;
  dataset_name: string;
  created_at: string;
}

interface Organization {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  users?: User[];
  datasets?: Dataset[];
}

// Available datasets (hardcoded for now, could come from API)
const AVAILABLE_DATASETS = [
  "silkroute",
  "gold_customer_360",
  "gold_employee_360",
  "gold_inventory_health_daily",
  "gold_product_360",
  "gold_sales_daily",
  "gold_store_360",
  "gold_store_sku_daily",
];

export default function OrganizationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();

  const [org, setOrg] = useState<Organization | null>(null);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // New user form
  const [showAddUser, setShowAddUser] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newIsAdmin, setNewIsAdmin] = useState(false);
  const [userError, setUserError] = useState("");

  // Dataset management
  const [showAddDataset, setShowAddDataset] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState("");

  useEffect(() => {
    fetchOrganization();
  }, [id]);

  const fetchOrganization = async () => {
    try {
      const token = localStorage.getItem("admin_token");
      const response = await fetch(
        `${API_BASE_URL}/admin/organizations/${id}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!response.ok) {
        throw new Error("Failed to fetch organization");
      }

      const data = await response.json();
      setOrg(data);
      setName(data.name);
      setSlug(data.slug);
      setIsActive(data.is_active);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load organization");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      const token = localStorage.getItem("admin_token");
      const response = await fetch(
        `${API_BASE_URL}/admin/organizations/${id}`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ name, slug, is_active: isActive }),
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to update organization");
      }

      router.push("/admin/organizations");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update organization");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAddUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setUserError("");

    try {
      const token = localStorage.getItem("admin_token");
      const response = await fetch(`${API_BASE_URL}/admin/users`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: newUsername,
          email: newEmail,
          password: newPassword,
          organization_id: parseInt(id),
          is_admin: newIsAdmin,
          is_active: true,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to create user");
      }

      // Reset form and refresh
      setNewUsername("");
      setNewEmail("");
      setNewPassword("");
      setNewIsAdmin(false);
      setShowAddUser(false);
      fetchOrganization();
    } catch (err) {
      setUserError(err instanceof Error ? err.message : "Failed to create user");
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

      fetchOrganization();
    } catch (err) {
      console.error("Failed to toggle user status:", err);
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

      fetchOrganization();
    } catch (err) {
      console.error("Failed to delete user:", err);
    }
  };

  const handleAddDataset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDataset) return;

    try {
      const token = localStorage.getItem("admin_token");
      const response = await fetch(
        `${API_BASE_URL}/admin/organizations/${id}/datasets`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ dataset_name: selectedDataset }),
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to add dataset");
      }

      setSelectedDataset("");
      setShowAddDataset(false);
      fetchOrganization();
    } catch (err) {
      console.error("Failed to add dataset:", err);
    }
  };

  const removeDataset = async (datasetId: number) => {
    try {
      const token = localStorage.getItem("admin_token");
      const response = await fetch(
        `${API_BASE_URL}/admin/organizations/${id}/datasets/${datasetId}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!response.ok) {
        throw new Error("Failed to remove dataset");
      }

      fetchOrganization();
    } catch (err) {
      console.error("Failed to remove dataset:", err);
    }
  };

  if (isLoading) {
    return (
      <div className="p-8 text-center text-slate-500">Loading...</div>
    );
  }

  if (!org) {
    return (
      <div className="p-8 text-center text-slate-500">
        Organization not found.{" "}
        <Link href="/admin/organizations" className="text-[#4f46e5] hover:underline">
          Go back
        </Link>
      </div>
    );
  }

  // Get datasets not yet assigned
  const availableDatasets = AVAILABLE_DATASETS.filter(
    (d) => !org.datasets?.some((od) => od.dataset_name === d)
  );

  return (
    <div className="max-w-4xl">
      {/* Header */}
      <div className="mb-8">
        <Link
          href="/admin/organizations"
          className="text-sm text-slate-500 hover:text-slate-700 mb-2 inline-block"
        >
          ← Back to Organizations
        </Link>
        <h1 className="text-3xl font-bold text-slate-900">Edit Organization</h1>
        <p className="text-slate-500 mt-1">Manage organization details, users, and datasets</p>
      </div>

      {/* Organization details form */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">
          Organization Details
        </h2>

        <form onSubmit={handleSave} className="space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4f46e5] text-slate-900"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Slug
              </label>
              <input
                type="text"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                required
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4f46e5] text-slate-900"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="isActive"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="w-4 h-4 text-[#4f46e5] border-slate-300 rounded focus:ring-[#4f46e5]"
            />
            <label htmlFor="isActive" className="text-sm text-slate-700">
              Active
            </label>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="px-4 py-2 bg-[#4f46e5] hover:bg-indigo-700 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
          >
            {isSubmitting ? "Saving..." : "Save Changes"}
          </button>
        </form>
      </div>

      {/* Users section */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-900">Users</h2>
          <button
            onClick={() => setShowAddUser(!showAddUser)}
            className="px-3 py-1 text-sm bg-[#4f46e5] hover:bg-indigo-700 text-white rounded-lg transition-colors"
          >
            + Add User
          </button>
        </div>

        {/* Add user form */}
        {showAddUser && (
          <form
            onSubmit={handleAddUser}
            className="bg-slate-50 rounded-lg p-4 mb-4 space-y-4"
          >
            {userError && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
                {userError}
              </div>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Username
                </label>
                <input
                  type="text"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4f46e5] text-slate-900"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Email
                </label>
                <input
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4f46e5] text-slate-900"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Password
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4f46e5] text-slate-900"
                />
              </div>
              <div className="flex items-end pb-2">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={newIsAdmin}
                    onChange={(e) => setNewIsAdmin(e.target.checked)}
                    className="w-4 h-4 text-[#4f46e5] border-slate-300 rounded"
                  />
                  <span className="text-sm text-slate-700">Admin privileges</span>
                </label>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                className="px-4 py-2 bg-[#4f46e5] hover:bg-indigo-700 text-white text-sm font-medium rounded-lg transition-colors"
              >
                Add User
              </button>
              <button
                type="button"
                onClick={() => setShowAddUser(false)}
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-sm font-medium rounded-lg transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {/* Users list */}
        {org.users && org.users.length > 0 ? (
          <div className="divide-y divide-slate-200">
            {org.users.map((user) => (
              <div
                key={user.id}
                className="py-3 flex items-center justify-between"
              >
                <div>
                  <p className="font-medium text-slate-900">
                    {user.username}
                    {user.is_admin && (
                      <span className="ml-2 px-2 py-0.5 text-xs bg-purple-100 text-purple-700 rounded">
                        Admin
                      </span>
                    )}
                  </p>
                  <p className="text-sm text-slate-500">{user.email}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 text-xs rounded ${
                      user.is_active
                        ? "bg-green-100 text-green-700"
                        : "bg-red-100 text-red-700"
                    }`}
                  >
                    {user.is_active ? "Active" : "Inactive"}
                  </span>
                  <button
                    onClick={() => toggleUserStatus(user)}
                    className={`px-2 py-1 text-xs rounded transition-colors ${
                      user.is_active
                        ? "text-orange-600 hover:bg-orange-50"
                        : "text-green-600 hover:bg-green-50"
                    }`}
                  >
                    {user.is_active ? "Disable" : "Enable"}
                  </button>
                  <button
                    onClick={() => deleteUser(user)}
                    className="px-2 py-1 text-xs text-red-600 hover:bg-red-50 rounded transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-slate-500 text-sm">No users in this organization.</p>
        )}
      </div>

      {/* Datasets section */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-900">
            Dataset Access
          </h2>
          {availableDatasets.length > 0 && (
            <button
              onClick={() => setShowAddDataset(!showAddDataset)}
              className="px-3 py-1 text-sm bg-[#4f46e5] hover:bg-indigo-700 text-white rounded-lg transition-colors"
            >
              + Add Dataset
            </button>
          )}
        </div>

        {/* Add dataset form */}
        {showAddDataset && (
          <form
            onSubmit={handleAddDataset}
            className="bg-slate-50 rounded-lg p-4 mb-4 flex items-end gap-4"
          >
            <div className="flex-1">
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Select Dataset
              </label>
              <select
                value={selectedDataset}
                onChange={(e) => setSelectedDataset(e.target.value)}
                required
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4f46e5] text-slate-900"
              >
                <option value="">Choose a dataset...</option>
                {availableDatasets.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-[#4f46e5] hover:bg-indigo-700 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Add
            </button>
            <button
              type="button"
              onClick={() => setShowAddDataset(false)}
              className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-sm font-medium rounded-lg transition-colors"
            >
              Cancel
            </button>
          </form>
        )}

        {/* Datasets list */}
        {org.datasets && org.datasets.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {org.datasets.map((dataset) => (
              <div
                key={dataset.id}
                className="flex items-center gap-2 px-3 py-2 bg-slate-100 rounded-lg"
              >
                <span className="text-sm text-slate-700">
                  {dataset.dataset_name}
                </span>
                <button
                  onClick={() => removeDataset(dataset.id)}
                  className="text-slate-400 hover:text-red-600 transition-colors"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-slate-500 text-sm">
            No datasets assigned. Add datasets to allow users to query them.
          </p>
        )}
      </div>
    </div>
  );
}
