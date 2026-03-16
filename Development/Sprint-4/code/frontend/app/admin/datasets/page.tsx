"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getApiBaseUrl } from "@/lib/api-base";

const API_BASE_URL = getApiBaseUrl();

// Available datasets in the system
const AVAILABLE_DATASETS = [
  {
    name: "silkroute",
    description: "Main retail analytics dataset",
    tables: ["customers", "products", "orders", "stores", "employees"],
  },
  {
    name: "gold_customer_360",
    description: "Customer 360 view with aggregated metrics",
    tables: ["customer profile, lifetime value, segments"],
  },
  {
    name: "gold_employee_360",
    description: "Employee performance metrics",
    tables: ["employee details, sales, rankings"],
  },
  {
    name: "gold_inventory_health_daily",
    description: "Daily inventory health tracking",
    tables: ["stock levels, turnover, alerts"],
  },
  {
    name: "gold_product_360",
    description: "Product analytics and performance",
    tables: ["product metrics, sales, inventory"],
  },
  {
    name: "gold_sales_daily",
    description: "Daily sales aggregations",
    tables: ["revenue, transactions, trends"],
  },
  {
    name: "gold_store_360",
    description: "Store-level analytics",
    tables: ["store performance, employees, inventory"],
  },
  {
    name: "gold_store_sku_daily",
    description: "Store-SKU level daily metrics",
    tables: ["product sales by store, daily"],
  },
];

interface Organization {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  datasets?: { id: number; dataset_name: string }[];
}

export default function DatasetsPage() {
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
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setIsLoading(false);
    }
  };

  const toggleDatasetAccess = async (org: Organization, datasetName: string) => {
    const hasAccess = org.datasets?.some((d) => d.dataset_name === datasetName);
    const token = localStorage.getItem("admin_token");

    try {
      if (hasAccess) {
        // Remove access
        const dataset = org.datasets?.find((d) => d.dataset_name === datasetName);
        if (dataset) {
          await fetch(
            `${API_BASE_URL}/admin/organizations/${org.id}/datasets/${dataset.id}`,
            {
              method: "DELETE",
              headers: { Authorization: `Bearer ${token}` },
            }
          );
        }
      } else {
        // Add access
        await fetch(`${API_BASE_URL}/admin/organizations/${org.id}/datasets`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ dataset_name: datasetName }),
        });
      }

      fetchOrganizations();
    } catch (err) {
      console.error("Failed to toggle dataset access:", err);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Dataset Management</h1>
        <p className="text-slate-500 mt-1">
          Manage which datasets each organization can access
        </p>
      </div>

      {/* Error message */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
          {error}
        </div>
      )}

      {/* Available Datasets Reference */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">
          Available Datasets
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {AVAILABLE_DATASETS.map((dataset) => (
            <div
              key={dataset.name}
              className="border border-slate-200 rounded-lg p-4"
            >
              <p className="font-medium text-slate-900">{dataset.name}</p>
              <p className="text-sm text-slate-500 mt-1">
                {dataset.description}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Access Matrix */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-6 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">
            Organization Access Matrix
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Click cells to toggle access for each organization
          </p>
        </div>

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
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="text-left px-6 py-4 text-sm font-medium text-slate-600 sticky left-0 bg-slate-50">
                    Organization
                  </th>
                  {AVAILABLE_DATASETS.map((dataset) => (
                    <th
                      key={dataset.name}
                      className="text-center px-4 py-4 text-sm font-medium text-slate-600 min-w-[120px]"
                    >
                      <div className="transform -rotate-45 origin-center whitespace-nowrap">
                        {dataset.name.replace("gold_", "").replace(/_/g, " ")}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {organizations.map((org) => (
                  <tr key={org.id} className="hover:bg-slate-50">
                    <td className="px-6 py-4 sticky left-0 bg-white">
                      <Link
                        href={`/admin/organizations/${org.id}`}
                        className="font-medium text-slate-900 hover:text-[#4f46e5]"
                      >
                        {org.name}
                      </Link>
                      {!org.is_active && (
                        <span className="ml-2 text-xs text-red-500">
                          (Inactive)
                        </span>
                      )}
                    </td>
                    {AVAILABLE_DATASETS.map((dataset) => {
                      const hasAccess = org.datasets?.some(
                        (d) => d.dataset_name === dataset.name
                      );
                      return (
                        <td key={dataset.name} className="px-4 py-4 text-center">
                          <button
                            onClick={() =>
                              toggleDatasetAccess(org, dataset.name)
                            }
                            className={`w-8 h-8 rounded-lg transition-all ${
                              hasAccess
                                ? "bg-green-500 text-white hover:bg-green-600"
                                : "bg-slate-200 text-slate-400 hover:bg-slate-300"
                            }`}
                          >
                            {hasAccess ? "✓" : "−"}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center gap-6 text-sm text-slate-500">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 bg-green-500 rounded flex items-center justify-center text-white text-xs">
            ✓
          </span>
          <span>Has access</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 bg-slate-200 rounded flex items-center justify-center text-slate-400 text-xs">
            −
          </span>
          <span>No access</span>
        </div>
      </div>
    </div>
  );
}
