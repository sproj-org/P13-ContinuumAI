"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AlertTriangle, RefreshCw, Save } from "lucide-react";

import { ApiRequestError, apiClient } from "@/lib/api";
import type { CoverageGap, DecisionStateResponse } from "@/lib/api-types";
import { useAuth } from "@/lib/auth-context";

type EditorMode = "base" | "override";
type EditorKind = "strategy" | "kpi";

function scoreText(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function gapSummary(gap: CoverageGap): string {
  const missingMarts = gap.details?.missing_marts ?? [];
  const missingColumnsByMart = gap.details?.missing_columns_by_mart ?? {};
  const missingColumnEntries = Object.entries(missingColumnsByMart)
    .filter(([, columns]) => Array.isArray(columns) && columns.length > 0)
    .map(([mart, columns]) => `${mart}: ${columns.join(", ")}`);
  const martsText = missingMarts.length > 0 ? `Missing marts: ${missingMarts.join(", ")}` : "";
  const columnsText = missingColumnEntries.length > 0 ? `Missing columns: ${missingColumnEntries.join(" | ")}` : "";
  if (martsText && columnsText) {
    return `${martsText}. ${columnsText}`;
  }
  return martsText || columnsText || "No details";
}

export default function StrategyTab() {
  const params = useParams<{ datasetId: string }>();
  const { user } = useAuth();
  const datasetId = params?.datasetId ?? "silkroute";

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [decisionState, setDecisionState] = useState<DecisionStateResponse | null>(null);
  const [activeEditor, setActiveEditor] = useState<EditorKind>("strategy");
  const [strategyMode, setStrategyMode] = useState<EditorMode>("base");
  const [kpiMode, setKpiMode] = useState<EditorMode>("base");

  const [strategyBaseYaml, setStrategyBaseYaml] = useState("");
  const [strategyOverrideYaml, setStrategyOverrideYaml] = useState("");
  const [kpiBaseYaml, setKpiBaseYaml] = useState("");
  const [kpiOverrideYaml, setKpiOverrideYaml] = useState("");

  const [strategyText, setStrategyText] = useState("");
  const [kpiText, setKpiText] = useState("");

  const loadStrategyState = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [decision, strategyBundle, kpiBundle] = await Promise.all([
        apiClient.getDecisionState(datasetId),
        apiClient.getStrategyBundle(),
        apiClient.getKpiRegistryBundle(),
      ]);

      setDecisionState(decision);

      setStrategyBaseYaml(strategyBundle.base_yaml);
      setStrategyOverrideYaml(strategyBundle.override_yaml);
      setStrategyMode("base");
      setStrategyText(strategyBundle.base_yaml);

      setKpiBaseYaml(kpiBundle.base_yaml);
      setKpiOverrideYaml(kpiBundle.override_yaml);
      setKpiMode("base");
      setKpiText(kpiBundle.base_yaml);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load strategy state");
    } finally {
      setIsLoading(false);
    }
  }, [datasetId]);

  useEffect(() => {
    void loadStrategyState();
  }, [loadStrategyState]);

  useEffect(() => {
    setStrategyText(strategyMode === "base" ? strategyBaseYaml : strategyOverrideYaml);
  }, [strategyBaseYaml, strategyMode, strategyOverrideYaml]);

  useEffect(() => {
    setKpiText(kpiMode === "base" ? kpiBaseYaml : kpiOverrideYaml);
  }, [kpiBaseYaml, kpiMode, kpiOverrideYaml]);

  const readiness = decisionState?.readiness;
  const readinessFlags = decisionState?.readiness_flags ?? null;
  const kpisDefined = readinessFlags?.kpis_defined ?? true;
  const revision = decisionState?.revision;

  const saveStrategy = async () => {
    if (!revision) {
      setError("Missing revision. Refresh and try again.");
      return;
    }
    setIsSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await apiClient.putStrategyBundle({
        expected_revision: revision,
        mode: strategyMode,
        yaml: strategyText,
        author: user?.username ?? "strategy_editor",
        reason: "Updated strategy bundle from Strategy tab",
      });
      setSuccess("Strategy bundle saved.");
      await loadStrategyState();
    } catch (requestError) {
      if (requestError instanceof ApiRequestError && requestError.status === 409) {
        setError("Your strategy changed on disk. Refresh and try again.");
      } else {
        setError(requestError instanceof Error ? requestError.message : "Failed to save strategy bundle");
      }
    } finally {
      setIsSaving(false);
    }
  };

  const saveKpiRegistry = async () => {
    if (!revision) {
      setError("Missing revision. Refresh and try again.");
      return;
    }
    setIsSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await apiClient.putKpiRegistryBundle({
        expected_revision: revision,
        mode: kpiMode,
        yaml: kpiText,
        author: user?.username ?? "strategy_editor",
        reason: "Updated KPI registry from Strategy tab",
      });
      setSuccess("KPI registry saved.");
      await loadStrategyState();
    } catch (requestError) {
      if (requestError instanceof ApiRequestError && requestError.status === 409) {
        setError("Your strategy changed on disk. Refresh and try again.");
      } else {
        setError(requestError instanceof Error ? requestError.message : "Failed to save KPI registry");
      }
    } finally {
      setIsSaving(false);
    }
  };

  const gapRows = useMemo(() => decisionState?.coverage_gaps ?? [], [decisionState]);

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4 bg-gradient-to-br from-white via-indigo-50/20 to-violet-50/20">
      <div className="rounded-xl border border-indigo-200/60 bg-white/80 backdrop-blur-sm p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-slate-900 font-semibold">Strategy</h2>
            <p className="text-xs text-slate-600">
              Dataset: {datasetId} | Revision: {revision ?? "n/a"}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void loadStrategyState()}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">Loading strategy state...</div>
      ) : null}

      {error ? (
        <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <AlertTriangle className="h-4 w-4 mt-0.5" />
          <span>{error}</span>
        </div>
      ) : null}

      {success ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {success}
        </div>
      ) : null}

      {!kpisDefined ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          No KPIs defined yet. Add KPIs to enable coverage and readiness.
        </div>
      ) : null}

      {readiness ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
          <div className="rounded-xl border border-indigo-200 bg-white p-3">
            <p className="text-xs text-slate-500">Overall</p>
            <p className="text-lg font-semibold text-indigo-700">{scoreText(readiness.overall_score)}</p>
          </div>
          <div className="rounded-xl border border-indigo-200 bg-white p-3">
            <p className="text-xs text-slate-500">KPI Coverage</p>
            <p className="text-lg font-semibold text-indigo-700">{scoreText(readiness.kpi_coverage)}</p>
          </div>
          <div className="rounded-xl border border-indigo-200 bg-white p-3">
            <p className="text-xs text-slate-500">Data Readiness</p>
            <p className="text-lg font-semibold text-indigo-700">
              {kpisDefined ? scoreText(readiness.data_readiness) : "—"}
            </p>
          </div>
          <div className="rounded-xl border border-indigo-200 bg-white p-3">
            <p className="text-xs text-slate-500">Rule Readiness</p>
            <p className="text-lg font-semibold text-indigo-700">{scoreText(readiness.rule_readiness)}</p>
          </div>
          <div className="rounded-xl border border-indigo-200 bg-white p-3">
            <p className="text-xs text-slate-500">Hierarchy Readiness</p>
            <p className="text-lg font-semibold text-indigo-700">{scoreText(readiness.hierarchy_readiness)}</p>
          </div>
        </div>
      ) : null}

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-slate-900">Coverage Gaps</h3>
        {gapRows.length === 0 ? (
          <p className="mt-2 text-sm text-slate-600">No coverage gaps detected.</p>
        ) : (
          <div className="mt-2 overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500">
                  <th className="px-2 py-2 font-medium">KPI</th>
                  <th className="px-2 py-2 font-medium">Reason</th>
                  <th className="px-2 py-2 font-medium">Details</th>
                </tr>
              </thead>
              <tbody>
                {gapRows.map((gap) => (
                  <tr key={`${gap.kpi_id}-${gap.reason}`} className="border-b border-slate-100 align-top text-slate-700">
                    <td className="px-2 py-2 font-medium">{gap.kpi_id}</td>
                    <td className="px-2 py-2">{gap.reason}</td>
                    <td className="px-2 py-2">{gapSummary(gap)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveEditor("strategy")}
            className={`rounded-lg px-3 py-1.5 text-xs border ${
              activeEditor === "strategy"
                ? "border-indigo-300 bg-indigo-100 text-indigo-700"
                : "border-slate-300 bg-white text-slate-700"
            }`}
          >
            Strategy Bundle
          </button>
          <button
            type="button"
            onClick={() => setActiveEditor("kpi")}
            className={`rounded-lg px-3 py-1.5 text-xs border ${
              activeEditor === "kpi"
                ? "border-indigo-300 bg-indigo-100 text-indigo-700"
                : "border-slate-300 bg-white text-slate-700"
            }`}
          >
            KPI Registry
          </button>
        </div>

        {activeEditor === "strategy" ? (
          <div className="mt-3 space-y-2">
            <div className="flex items-center justify-between">
              <label className="inline-flex items-center gap-2 text-xs text-slate-700">
                <input
                  type="checkbox"
                  checked={strategyMode === "override"}
                  onChange={(event) => setStrategyMode(event.target.checked ? "override" : "base")}
                />
                Edit override YAML
              </label>
              <button
                type="button"
                onClick={() => void saveStrategy()}
                disabled={isSaving}
                className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700 disabled:opacity-60"
              >
                <Save className="h-3.5 w-3.5" />
                Save
              </button>
            </div>
            <textarea
              value={strategyText}
              onChange={(event) => setStrategyText(event.target.value)}
              className="h-72 w-full rounded-lg border border-slate-300 bg-slate-50 p-3 font-mono text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
        ) : (
          <div className="mt-3 space-y-2">
            <div className="flex items-center justify-between">
              <label className="inline-flex items-center gap-2 text-xs text-slate-700">
                <input
                  type="checkbox"
                  checked={kpiMode === "override"}
                  onChange={(event) => setKpiMode(event.target.checked ? "override" : "base")}
                />
                Edit override YAML
              </label>
              <button
                type="button"
                onClick={() => void saveKpiRegistry()}
                disabled={isSaving}
                className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700 disabled:opacity-60"
              >
                <Save className="h-3.5 w-3.5" />
                Save
              </button>
            </div>
            <textarea
              value={kpiText}
              onChange={(event) => setKpiText(event.target.value)}
              className="h-72 w-full rounded-lg border border-slate-300 bg-slate-50 p-3 font-mono text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
        )}
      </div>
    </div>
  );
}
