"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AlertTriangle, Plus, RefreshCw, Save, Trash2, X } from "lucide-react";

import { ApiRequestError, apiClient } from "@/lib/api";
import type {
  CoverageGap,
  DecisionStateResponse,
  StrategyAgentMissingItem,
  StrategyKpi,
  StrategyKpiLibraryResponse,
} from "@/lib/api-types";
import { useAuth } from "@/lib/auth-context";

type Section = "overview" | "kpi_library" | "targets" | "rules" | "reconciliation" | "advanced_yaml";
type EditorMode = "base" | "override";
type EditorKind = "strategy" | "kpi";
type KpiFormMode = "create" | "edit" | "duplicate";

const sections: Array<{ id: Section; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "kpi_library", label: "KPI Library" },
  { id: "targets", label: "Targets" },
  { id: "rules", label: "Rules" },
  { id: "reconciliation", label: "Reconciliation" },
  { id: "advanced_yaml", label: "Advanced YAML" },
];

function scoreText(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function emptyKpi(): StrategyKpi {
  return {
    id: "",
    display_name: "",
    description: "",
    formula: "sum(net_sales)",
    marts: [],
    required_columns: [],
    dimensions: [],
    default_grain: "day",
    pillar_id: "",
    owner: "",
  };
}

function normalizeKpi(kpi: StrategyKpi): StrategyKpi {
  const clean = (value: string | null | undefined) => (value || "").trim() || null;
  return {
    id: (kpi.id || "").trim(),
    display_name: clean(kpi.display_name),
    description: (kpi.description || "").trim(),
    formula: (kpi.formula || "").trim(),
    marts: (kpi.marts || []).map((item) => item.trim()).filter(Boolean),
    required_columns: (kpi.required_columns || []).map((item) => item.trim()).filter(Boolean),
    dimensions: (kpi.dimensions || []).map((item) => item.trim()).filter(Boolean),
    default_grain: clean(kpi.default_grain),
    pillar_id: clean(kpi.pillar_id),
    owner: clean(kpi.owner),
  };
}

function gapSummary(gap: CoverageGap): string {
  const missingMarts = gap.details?.missing_marts ?? [];
  const missingColumnsByMart = gap.details?.missing_columns_by_mart ?? {};
  const parts: string[] = [];
  if (missingMarts.length > 0) {
    parts.push(`Missing marts: ${missingMarts.join(", ")}`);
  }
  const columnParts = Object.entries(missingColumnsByMart)
    .map(([mart, cols]) => `${mart}: ${cols.join(", ")}`)
    .filter(Boolean);
  if (columnParts.length > 0) {
    parts.push(`Missing columns: ${columnParts.join(" | ")}`);
  }
  return parts.join(". ") || "No details";
}

function missingSummary(item: StrategyAgentMissingItem): string {
  const parts: string[] = [];
  const missingMarts = item.details?.missing_marts ?? [];
  const missingColumns = item.details?.missing_columns_by_mart ?? {};
  if (missingMarts.length > 0) {
    parts.push(`Missing marts: ${missingMarts.join(", ")}`);
  }
  const columnParts = Object.entries(missingColumns)
    .map(([mart, cols]) => `${mart}: ${cols.join(", ")}`)
    .filter(Boolean);
  if (columnParts.length > 0) {
    parts.push(`Missing columns: ${columnParts.join(" | ")}`);
  }
  return parts.join(". ");
}

export default function StrategyTab() {
  const params = useParams<{ datasetId: string }>();
  const datasetId = params?.datasetId ?? "silkroute";
  const { user } = useAuth();

  const [section, setSection] = useState<Section>("overview");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [decision, setDecision] = useState<DecisionStateResponse | null>(null);
  const [kpiLibrary, setKpiLibrary] = useState<StrategyKpiLibraryResponse | null>(null);

  const [strategyBaseYaml, setStrategyBaseYaml] = useState("");
  const [strategyOverrideYaml, setStrategyOverrideYaml] = useState("");
  const [kpiBaseYaml, setKpiBaseYaml] = useState("");
  const [kpiOverrideYaml, setKpiOverrideYaml] = useState("");
  const [strategyMode, setStrategyMode] = useState<EditorMode>("base");
  const [kpiMode, setKpiMode] = useState<EditorMode>("base");
  const [editor, setEditor] = useState<EditorKind>("strategy");
  const [strategyText, setStrategyText] = useState("");
  const [kpiText, setKpiText] = useState("");

  const [modalOpen, setModalOpen] = useState(false);
  const [formMode, setFormMode] = useState<KpiFormMode>("create");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<StrategyKpi>(emptyKpi());
  const [dimensionsDraft, setDimensionsDraft] = useState("");
  const [strategyNotes, setStrategyNotes] = useState("");
  const [agentCandidates, setAgentCandidates] = useState<StrategyKpi[]>([]);
  const [agentNotes, setAgentNotes] = useState<string[]>([]);
  const [agentMissingById, setAgentMissingById] = useState<Record<string, string>>({});
  const [agentLoading, setAgentLoading] = useState(false);
  const [addingCandidateId, setAddingCandidateId] = useState<string | null>(null);

  const revision = kpiLibrary?.revision ?? decision?.revision ?? null;
  const readiness = decision?.readiness;
  const kpisDefined = decision?.readiness_flags?.kpis_defined ?? true;
  const kpis = kpiLibrary?.kpis ?? [];
  const availableMarts = kpiLibrary?.available_marts ?? [];
  const martColumns = kpiLibrary?.mart_columns ?? {};

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [decisionState, strategyBundle, kpiBundle, kpiState] = await Promise.all([
        apiClient.getDecisionState(datasetId),
        apiClient.getStrategyBundle(),
        apiClient.getKpiRegistryBundle(),
        apiClient.getStrategyKpis(datasetId),
      ]);
      setDecision(decisionState);
      setKpiLibrary(kpiState);
      setStrategyBaseYaml(strategyBundle.base_yaml);
      setStrategyOverrideYaml(strategyBundle.override_yaml);
      setKpiBaseYaml(kpiBundle.base_yaml);
      setKpiOverrideYaml(kpiBundle.override_yaml);
      setStrategyMode("base");
      setKpiMode("base");
      setStrategyText(strategyBundle.base_yaml);
      setKpiText(kpiBundle.base_yaml);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load strategy state");
    } finally {
      setLoading(false);
    }
  }, [datasetId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    setStrategyText(strategyMode === "base" ? strategyBaseYaml : strategyOverrideYaml);
  }, [strategyBaseYaml, strategyMode, strategyOverrideYaml]);

  useEffect(() => {
    setKpiText(kpiMode === "base" ? kpiBaseYaml : kpiOverrideYaml);
  }, [kpiBaseYaml, kpiMode, kpiOverrideYaml]);

  const draftColumns = useMemo(() => {
    const values = new Set<string>();
    for (const mart of draft.marts || []) {
      for (const column of martColumns[mart] || []) {
        values.add(column);
      }
    }
    return Array.from(values).sort();
  }, [draft.marts, martColumns]);

  const kpiStatus = useCallback(
    (kpi: StrategyKpi): "computable" | "missing_deps" => {
      const missingMarts = (kpi.marts || []).filter((mart) => !availableMarts.includes(mart));
      if (missingMarts.length > 0) return "missing_deps";
      for (const mart of kpi.marts || []) {
        const available = new Set(martColumns[mart] || []);
        const hasMissing = (kpi.required_columns || []).some((column) => !available.has(column));
        if (hasMissing) return "missing_deps";
      }
      return "computable";
    },
    [availableMarts, martColumns]
  );

  const openModal = (mode: KpiFormMode, kpi?: StrategyKpi) => {
    setFormMode(mode);
    if (!kpi) {
      setEditingId(null);
      setDraft(emptyKpi());
      setDimensionsDraft("");
    } else {
      const next = { ...kpi };
      if (mode === "duplicate") {
        next.id = `${kpi.id}_copy`;
      }
      setEditingId(mode === "edit" ? kpi.id : null);
      setDraft(next);
      setDimensionsDraft((next.dimensions || []).join(", "));
    }
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingId(null);
    setDraft(emptyKpi());
    setDimensionsDraft("");
  };

  const handleApiError = (requestError: unknown, fallback: string) => {
    if (requestError instanceof ApiRequestError && requestError.status === 409) {
      setError("Your strategy changed on disk. Refresh and try again.");
      return;
    }
    setError(requestError instanceof Error ? requestError.message : fallback);
  };

  const saveKpi = async () => {
    if (!revision) return setError("Missing revision. Refresh and try again.");
    const normalized = normalizeKpi({ ...draft, dimensions: dimensionsDraft.split(",").map((v) => v.trim()).filter(Boolean) });
    if (!normalized.id || !normalized.description || !normalized.formula || normalized.marts.length === 0) {
      return setError("ID, description, formula, and at least one mart are required.");
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const payload = {
        expected_revision: revision,
        dataset_id: datasetId,
        kpi: normalized,
        author: user?.username ?? "strategy_editor",
        reason: formMode === "edit" ? `Update ${normalized.id}` : `Create ${normalized.id}`,
      };
      if (formMode === "edit" && editingId) {
        await apiClient.updateStrategyKpi(editingId, payload);
      } else {
        await apiClient.createStrategyKpi(payload);
      }
      closeModal();
      setSuccess("KPI saved.");
      await load();
    } catch (requestError) {
      handleApiError(requestError, "Failed to save KPI.");
    } finally {
      setSaving(false);
    }
  };

  const deleteKpi = async (kpiId: string) => {
    if (!revision) return setError("Missing revision. Refresh and try again.");
    if (!globalThis.confirm(`Delete KPI '${kpiId}'?`)) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await apiClient.deleteStrategyKpi(kpiId, {
        expected_revision: revision,
        dataset_id: datasetId,
        author: user?.username ?? "strategy_editor",
        reason: `Delete ${kpiId}`,
      });
      setSuccess("KPI deleted.");
      await load();
    } catch (requestError) {
      handleApiError(requestError, "Failed to delete KPI.");
    } finally {
      setSaving(false);
    }
  };

  const saveYaml = async () => {
    if (!revision) return setError("Missing revision. Refresh and try again.");
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      if (editor === "strategy") {
        await apiClient.putStrategyBundle({
          expected_revision: revision,
          mode: strategyMode,
          yaml: strategyText,
          author: user?.username ?? "strategy_editor",
          reason: "Update strategy YAML",
        });
      } else {
        await apiClient.putKpiRegistryBundle({
          expected_revision: revision,
          mode: kpiMode,
          yaml: kpiText,
          author: user?.username ?? "strategy_editor",
          reason: "Update KPI YAML",
        });
      }
      setSuccess("Saved.");
      await load();
    } catch (requestError) {
      handleApiError(requestError, "Failed to save YAML.");
    } finally {
      setSaving(false);
    }
  };

  const suggestKpis = async () => {
    if (!revision) {
      setError("Missing revision. Refresh and try again.");
      return;
    }
    if (!strategyNotes.trim()) {
      setError("Add strategy notes before requesting KPI suggestions.");
      return;
    }

    setAgentLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const extracted = await apiClient.extractStrategyKpis({
        dataset_id: datasetId,
        text: strategyNotes,
        expected_revision: revision,
      });
      setAgentCandidates(extracted.candidates || []);
      setAgentNotes(extracted.notes || []);

      if ((extracted.candidates || []).length > 0) {
        const reconciled = await apiClient.reconcileStrategyKpis({
          dataset_id: datasetId,
          candidates: extracted.candidates || [],
          expected_revision: extracted.revision,
        });
        const nextMissing: Record<string, string> = {};
        for (const item of reconciled.missing || []) {
          nextMissing[item.kpi_id] = missingSummary(item);
        }
        setAgentMissingById(nextMissing);
      } else {
        setAgentMissingById({});
      }

      setSuccess(`Suggested ${(extracted.candidates || []).length} KPI(s).`);
    } catch (requestError) {
      handleApiError(requestError, "Failed to generate KPI suggestions.");
    } finally {
      setAgentLoading(false);
    }
  };

  const addSuggestedKpi = async (candidate: StrategyKpi) => {
    if (!revision) {
      setError("Missing revision. Refresh and try again.");
      return;
    }
    const normalized = normalizeKpi(candidate);
    setAddingCandidateId(normalized.id);
    setError(null);
    setSuccess(null);
    try {
      await apiClient.createStrategyKpi({
        expected_revision: revision,
        dataset_id: datasetId,
        kpi: normalized,
        author: user?.username ?? "strategy_editor",
        reason: `Add suggested KPI ${normalized.id}`,
      });
      setSuccess(`Added KPI '${normalized.id}'.`);
      setAgentCandidates((prev) => prev.filter((item) => item.id !== normalized.id));
      setAgentMissingById((prev) => {
        const next = { ...prev };
        delete next[normalized.id];
        return next;
      });
      await load();
    } catch (requestError) {
      handleApiError(requestError, "Failed to add suggested KPI.");
    } finally {
      setAddingCandidateId(null);
    }
  };

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4 bg-gradient-to-br from-white via-indigo-50/20 to-violet-50/20">
      <div className="rounded-xl border border-indigo-200/60 bg-white p-4 shadow-sm flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-slate-900">Strategy</h2>
          <p className="text-xs text-slate-600">Dataset: {datasetId} | Revision: {revision ?? "n/a"}</p>
        </div>
        <button type="button" onClick={() => void load()} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50">
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-3 flex flex-wrap gap-2">
        {sections.map((item) => (
          <button key={item.id} type="button" onClick={() => setSection(item.id)} className={`rounded-lg px-3 py-1.5 text-xs border ${section === item.id ? "border-indigo-300 bg-indigo-100 text-indigo-700" : "border-slate-300 bg-white text-slate-700"}`}>{item.label}</button>
        ))}
      </div>

      {loading ? <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">Loading...</div> : null}
      {error ? <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"><div className="flex items-center gap-2"><AlertTriangle className="h-4 w-4" /><span>{error}</span></div></div> : null}
      {success ? <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{success}</div> : null}

      {section === "overview" && readiness ? (
        <div className="space-y-3">
          {!kpisDefined ? <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">No KPIs defined yet. Add KPIs to enable coverage and readiness.</div> : null}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
            <div className="rounded-xl border border-indigo-200 bg-white p-3"><p className="text-xs text-slate-500">Overall</p><p className="text-lg font-semibold text-indigo-700">{scoreText(readiness.overall_score)}</p></div>
            <div className="rounded-xl border border-indigo-200 bg-white p-3"><p className="text-xs text-slate-500">KPI Coverage</p><p className="text-lg font-semibold text-indigo-700">{scoreText(readiness.kpi_coverage)}</p></div>
            <div className="rounded-xl border border-indigo-200 bg-white p-3"><p className="text-xs text-slate-500">Data Readiness</p><p className="text-lg font-semibold text-indigo-700">{kpisDefined ? scoreText(readiness.data_readiness) : "-"}</p></div>
            <div className="rounded-xl border border-indigo-200 bg-white p-3"><p className="text-xs text-slate-500">Rule Readiness</p><p className="text-lg font-semibold text-indigo-700">{scoreText(readiness.rule_readiness)}</p></div>
            <div className="rounded-xl border border-indigo-200 bg-white p-3"><p className="text-xs text-slate-500">Hierarchy Readiness</p><p className="text-lg font-semibold text-indigo-700">{scoreText(readiness.hierarchy_readiness)}</p></div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-slate-900">Coverage Gaps</h3>
            {(decision?.coverage_gaps || []).length === 0 ? <p className="mt-2 text-sm text-slate-600">No coverage gaps detected.</p> : (
              <div className="mt-2 overflow-x-auto"><table className="min-w-full text-left text-xs"><thead><tr className="border-b border-slate-200 text-slate-500"><th className="px-2 py-2">KPI</th><th className="px-2 py-2">Reason</th><th className="px-2 py-2">Details</th></tr></thead><tbody>{(decision?.coverage_gaps || []).map((gap) => <tr key={`${gap.kpi_id}-${gap.reason}`} className="border-b border-slate-100"><td className="px-2 py-2 font-medium">{gap.kpi_id}</td><td className="px-2 py-2">{gap.reason}</td><td className="px-2 py-2">{gapSummary(gap)}</td></tr>)}</tbody></table></div>
            )}
          </div>
        </div>
      ) : null}

      {section === "kpi_library" ? (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">KPI Library</h3>
            <button type="button" onClick={() => openModal("create")} className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700"><Plus className="h-3.5 w-3.5" />Add KPI</button>
          </div>
          <div className="mt-3 overflow-x-auto"><table className="min-w-full text-left text-xs"><thead><tr className="border-b border-slate-200 text-slate-500"><th className="px-2 py-2">ID</th><th className="px-2 py-2">Name</th><th className="px-2 py-2">Pillar</th><th className="px-2 py-2">Marts</th><th className="px-2 py-2">Status</th><th className="px-2 py-2">Actions</th></tr></thead><tbody>{kpis.map((kpi) => { const status = kpiStatus(kpi); return <tr key={kpi.id} className="border-b border-slate-100"><td className="px-2 py-2 font-medium">{kpi.id}</td><td className="px-2 py-2">{kpi.display_name || kpi.description}</td><td className="px-2 py-2">{kpi.pillar_id || "-"}</td><td className="px-2 py-2">{(kpi.marts || []).join(", ") || "-"}</td><td className="px-2 py-2"><span className={`rounded-full px-2 py-0.5 text-[10px] ${status === "computable" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{status === "computable" ? "Computable" : "Missing deps"}</span></td><td className="px-2 py-2"><div className="flex flex-wrap gap-1"><button type="button" onClick={() => openModal("edit", kpi)} className="rounded border border-slate-300 px-2 py-0.5 text-[10px] hover:bg-slate-100">Edit</button><button type="button" onClick={() => openModal("duplicate", kpi)} className="rounded border border-slate-300 px-2 py-0.5 text-[10px] hover:bg-slate-100">Duplicate</button><button type="button" onClick={() => void deleteKpi(kpi.id)} className="inline-flex items-center gap-1 rounded border border-red-300 px-2 py-0.5 text-[10px] text-red-700 hover:bg-red-50"><Trash2 className="h-3 w-3" />Delete</button></div></td></tr>; })}{kpis.length === 0 ? <tr><td colSpan={6} className="px-2 py-4 text-center text-slate-500">No KPIs yet.</td></tr> : null}</tbody></table></div>
        </div>
      ) : null}

      {section === "targets" ? <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">Targets UI stub. Full editor is next iteration.</div> : null}
      {section === "rules" ? <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">Rules UI stub. Full editor is next iteration.</div> : null}
      {section === "reconciliation" ? (
        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Reconciliation</h3>
            <p className="text-xs text-slate-600">Paste strategic notes to suggest KPI candidates, then add selected KPIs to the library.</p>
          </div>
          <textarea
            value={strategyNotes}
            onChange={(event) => setStrategyNotes(event.target.value)}
            placeholder="Paste strategy notes..."
            className="h-28 w-full rounded-lg border border-slate-300 bg-slate-50 p-3 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => void suggestKpis()}
              disabled={agentLoading}
              className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700 disabled:opacity-60"
            >
              <Plus className="h-3.5 w-3.5" />
              Suggest KPIs
            </button>
            <span className="text-xs text-slate-500">{agentCandidates.length} suggestion(s)</span>
          </div>
          {agentNotes.length > 0 ? (
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="text-[11px] font-medium text-slate-600">Agent Notes</p>
              <ul className="mt-1 space-y-1 text-xs text-slate-700">
                {agentNotes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {agentCandidates.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500">
                    <th className="px-2 py-2">ID</th>
                    <th className="px-2 py-2">Description</th>
                    <th className="px-2 py-2">Formula</th>
                    <th className="px-2 py-2">Dependencies</th>
                    <th className="px-2 py-2">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {agentCandidates.map((candidate) => (
                    <tr key={candidate.id} className="border-b border-slate-100">
                      <td className="px-2 py-2 font-medium">{candidate.id}</td>
                      <td className="px-2 py-2">{candidate.display_name || candidate.description}</td>
                      <td className="px-2 py-2 font-mono text-[11px]">{candidate.formula}</td>
                      <td className="px-2 py-2">
                        <div>{(candidate.marts || []).join(", ") || "-"}</div>
                        {agentMissingById[candidate.id] ? (
                          <div className="mt-1 text-[11px] text-amber-700">{agentMissingById[candidate.id]}</div>
                        ) : null}
                      </td>
                      <td className="px-2 py-2">
                        <button
                          type="button"
                          onClick={() => void addSuggestedKpi(candidate)}
                          disabled={addingCandidateId === candidate.id}
                          className="rounded border border-indigo-300 px-2 py-1 text-[11px] text-indigo-700 hover:bg-indigo-50 disabled:opacity-60"
                        >
                          {addingCandidateId === candidate.id ? "Adding..." : "Add"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      ) : null}

      {section === "advanced_yaml" ? (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => setEditor("strategy")} className={`rounded-lg px-3 py-1.5 text-xs border ${editor === "strategy" ? "border-indigo-300 bg-indigo-100 text-indigo-700" : "border-slate-300 bg-white text-slate-700"}`}>Strategy Bundle</button>
            <button type="button" onClick={() => setEditor("kpi")} className={`rounded-lg px-3 py-1.5 text-xs border ${editor === "kpi" ? "border-indigo-300 bg-indigo-100 text-indigo-700" : "border-slate-300 bg-white text-slate-700"}`}>KPI Registry</button>
          </div>
          <div className="mt-3 flex items-center justify-between">
            <label className="inline-flex items-center gap-2 text-xs text-slate-700">
              <input type="checkbox" checked={editor === "strategy" ? strategyMode === "override" : kpiMode === "override"} onChange={(event) => editor === "strategy" ? setStrategyMode(event.target.checked ? "override" : "base") : setKpiMode(event.target.checked ? "override" : "base")} />
              Edit override YAML
            </label>
            <button type="button" onClick={() => void saveYaml()} disabled={saving} className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700 disabled:opacity-60"><Save className="h-3.5 w-3.5" />Save</button>
          </div>
          <textarea value={editor === "strategy" ? strategyText : kpiText} onChange={(event) => editor === "strategy" ? setStrategyText(event.target.value) : setKpiText(event.target.value)} className="mt-2 h-72 w-full rounded-lg border border-slate-300 bg-slate-50 p-3 font-mono text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-400" />
        </div>
      ) : null}

      {modalOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-2xl rounded-xl border border-slate-200 bg-white p-4 shadow-xl">
            <div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-slate-900">{formMode === "edit" ? "Edit KPI" : formMode === "duplicate" ? "Duplicate KPI" : "Add KPI"}</h3><button type="button" onClick={closeModal} className="rounded-lg p-1 hover:bg-slate-100"><X className="h-4 w-4 text-slate-600" /></button></div>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <input value={draft.id} onChange={(event) => setDraft((prev) => ({ ...prev, id: event.target.value }))} placeholder="id" className="rounded border border-slate-300 px-2 py-1.5 text-xs" />
              <input value={draft.display_name || ""} onChange={(event) => setDraft((prev) => ({ ...prev, display_name: event.target.value }))} placeholder="display name" className="rounded border border-slate-300 px-2 py-1.5 text-xs" />
              <input value={draft.description} onChange={(event) => setDraft((prev) => ({ ...prev, description: event.target.value }))} placeholder="description" className="rounded border border-slate-300 px-2 py-1.5 text-xs md:col-span-2" />
              <input value={draft.formula} onChange={(event) => setDraft((prev) => ({ ...prev, formula: event.target.value }))} placeholder="formula" className="rounded border border-slate-300 px-2 py-1.5 text-xs md:col-span-2" />
              <input value={dimensionsDraft} onChange={(event) => setDimensionsDraft(event.target.value)} placeholder="dimensions (comma-separated)" className="rounded border border-slate-300 px-2 py-1.5 text-xs" />
              <input value={draft.pillar_id || ""} onChange={(event) => setDraft((prev) => ({ ...prev, pillar_id: event.target.value }))} placeholder="pillar_id" className="rounded border border-slate-300 px-2 py-1.5 text-xs" />
              <input value={draft.owner || ""} onChange={(event) => setDraft((prev) => ({ ...prev, owner: event.target.value }))} placeholder="owner" className="rounded border border-slate-300 px-2 py-1.5 text-xs" />
              <select value={draft.default_grain || ""} onChange={(event) => setDraft((prev) => ({ ...prev, default_grain: event.target.value }))} className="rounded border border-slate-300 px-2 py-1.5 text-xs"><option value="">default grain</option><option value="day">day</option><option value="week">week</option><option value="month">month</option><option value="quarter">quarter</option><option value="year">year</option></select>
              <div className="md:col-span-2 rounded border border-slate-200 p-2"><p className="text-[11px] text-slate-600 mb-1">Marts</p><div className="grid grid-cols-2 gap-2">{availableMarts.map((mart) => <label key={mart} className="inline-flex items-center gap-2 text-xs text-slate-700"><input type="checkbox" checked={(draft.marts || []).includes(mart)} onChange={(event) => setDraft((prev) => { const next = new Set(prev.marts || []); if (event.target.checked) next.add(mart); else next.delete(mart); return { ...prev, marts: Array.from(next) }; })} />{mart}</label>)}</div></div>
              <div className="md:col-span-2 rounded border border-slate-200 p-2"><p className="text-[11px] text-slate-600 mb-1">Required Columns</p><div className="grid grid-cols-2 gap-2 max-h-32 overflow-y-auto">{draftColumns.map((column) => <label key={column} className="inline-flex items-center gap-2 text-xs text-slate-700"><input type="checkbox" checked={(draft.required_columns || []).includes(column)} onChange={(event) => setDraft((prev) => { const next = new Set(prev.required_columns || []); if (event.target.checked) next.add(column); else next.delete(column); return { ...prev, required_columns: Array.from(next) }; })} />{column}</label>)}</div></div>
            </div>
            <div className="mt-4 flex items-center justify-end gap-2">
              <button type="button" onClick={closeModal} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50">Cancel</button>
              <button type="button" onClick={() => void saveKpi()} disabled={saving} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700 disabled:opacity-60">Save KPI</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
