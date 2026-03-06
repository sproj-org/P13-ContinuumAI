"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AlertTriangle, Plus, RefreshCw, Save, Trash2, X } from "lucide-react";

import { ApiRequestError, apiClient } from "@/lib/api";
import type {
  CoverageGap,
  DecisionStateResponse,
  StrategyAgentMissingItem,
  StrategyContextPayload,
  StrategyKpi,
  StrategyKpiLibraryResponse,
  StrategyPillarPayload,
  StrategyRule,
  StrategyRulesResponse,
  StrategySwotPayload,
  StrategyTarget,
  StrategyTargetsResponse,
} from "@/lib/api-types";
import { useAuth } from "@/lib/auth-context";

type Section = "overview" | "kpi_library" | "targets" | "rules" | "reconciliation" | "advanced_yaml";
type EditorMode = "base" | "override";
type EditorKind = "strategy" | "kpi";
type KpiFormMode = "create" | "edit" | "duplicate";
type TargetFormMode = "create" | "edit";
type RuleFormMode = "create" | "edit";

type RuleDraft = {
  id: string;
  kpi_id: string;
  operator: "<" | "<=" | ">" | ">=" | "==";
  threshold: string;
  severity: "info" | "warn" | "block";
  action: string;
  rationale: string;
};

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
    derived_metrics: {},
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
    derived_metrics: Object.fromEntries(
      Object.entries(kpi.derived_metrics || {})
        .map(([key, formula]) => [key.trim(), (formula || "").trim()])
        .filter(([key, formula]) => Boolean(key) && Boolean(formula))
    ),
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

function linesToList(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function listToLines(value: string[] | undefined | null): string {
  return (value || []).join("\n");
}

function extractRuleReferences(condition: string): string[] {
  const regex = /(?:kpi|target)\(\s*["']([^"']+)["']\s*\)/g;
  const refs = new Set<string>();
  let match = regex.exec(condition);
  while (match) {
    refs.add(match[1]);
    match = regex.exec(condition);
  }
  return Array.from(refs);
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
  const [derivedMetricsDraft, setDerivedMetricsDraft] = useState("");
  const [kpiSearch, setKpiSearch] = useState("");
  const [strategyNotes, setStrategyNotes] = useState("");
  const [agentCandidates, setAgentCandidates] = useState<StrategyKpi[]>([]);
  const [agentNotes, setAgentNotes] = useState<string[]>([]);
  const [agentMissingById, setAgentMissingById] = useState<Record<string, string>>({});
  const [agentColumnMatchesById, setAgentColumnMatchesById] = useState<Record<string, string[]>>({});
  const [ignoredCandidateIds, setIgnoredCandidateIds] = useState<string[]>([]);
  const [agentLoading, setAgentLoading] = useState(false);
  const [addingCandidateId, setAddingCandidateId] = useState<string | null>(null);
  const [overviewRevision, setOverviewRevision] = useState<string | null>(null);
  const [strategyContextDraft, setStrategyContextDraft] = useState<StrategyContextPayload>({
    company: "",
    horizon: "",
    north_star_metric: "",
    narrative: "",
  });
  const [pillarsDraft, setPillarsDraft] = useState<StrategyPillarPayload[]>([]);
  const [swotText, setSwotText] = useState({
    strengths: "",
    weaknesses: "",
    opportunities: "",
    threats: "",
  });
  const [targetsState, setTargetsState] = useState<StrategyTargetsResponse | null>(null);
  const [targetModalOpen, setTargetModalOpen] = useState(false);
  const [targetFormMode, setTargetFormMode] = useState<TargetFormMode>("create");
  const [targetDraft, setTargetDraft] = useState<StrategyTarget>({
    kpi_id: "",
    target_value: 0,
    red_threshold: null,
    yellow_threshold: null,
    direction: "up",
    owner: "",
    horizon: "",
  });
  const [rulesState, setRulesState] = useState<StrategyRulesResponse | null>(null);
  const [ruleModalOpen, setRuleModalOpen] = useState(false);
  const [ruleFormMode, setRuleFormMode] = useState<RuleFormMode>("create");
  const [ruleDraft, setRuleDraft] = useState<RuleDraft>({
    id: "",
    kpi_id: "",
    operator: "<",
    threshold: "",
    severity: "warn",
    action: "",
    rationale: "",
  });

  const revision = kpiLibrary?.revision ?? decision?.revision ?? null;
  const readiness = decision?.readiness;
  const kpisDefined = decision?.readiness_flags?.kpis_defined ?? true;
  const targetsDefined = decision?.readiness_flags?.targets_defined ?? false;
  const rulesDefined = decision?.readiness_flags?.rules_defined ?? false;
  const kpis = kpiLibrary?.kpis ?? [];
  const availableMarts = kpiLibrary?.available_marts ?? [];
  const martColumns = kpiLibrary?.mart_columns ?? {};
  const targets = targetsState?.targets ?? [];

  const targetByKpiId = useMemo(() => {
    const map = new Map<string, StrategyTarget>();
    for (const item of targets) {
      map.set(item.kpi_id, item);
    }
    return map;
  }, [targets]);
  const rules = rulesState?.rules ?? [];
  const knownRuleKpis = useMemo(() => new Set(rulesState?.available_kpis || []), [rulesState]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [decisionState, strategyBundle, kpiBundle, kpiState, overviewState, targetState, rulesBundle] = await Promise.all([
        apiClient.getDecisionState(datasetId),
        apiClient.getStrategyBundle(),
        apiClient.getKpiRegistryBundle(),
        apiClient.getStrategyKpis(datasetId),
        apiClient.getStrategyOverview(),
        apiClient.getStrategyTargets(),
        apiClient.getStrategyRules(),
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
      setOverviewRevision(overviewState.revision);
      setStrategyContextDraft({
        company: overviewState.strategy_context.company || "",
        horizon: overviewState.strategy_context.horizon || "",
        north_star_metric: overviewState.strategy_context.north_star_metric || "",
        narrative: overviewState.strategy_context.narrative || "",
      });
      setPillarsDraft(overviewState.pillars || []);
      const nextSwot: StrategySwotPayload = overviewState.swot || {
        strengths: [],
        weaknesses: [],
        opportunities: [],
        threats: [],
      };
      setSwotText({
        strengths: listToLines(nextSwot.strengths),
        weaknesses: listToLines(nextSwot.weaknesses),
        opportunities: listToLines(nextSwot.opportunities),
        threats: listToLines(nextSwot.threats),
      });
      setTargetsState(targetState);
      setRulesState(rulesBundle);
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

  const draftDependencyPreview = useMemo(() => {
    return (draft.marts || []).map((mart) => {
      const availableSet = new Set(martColumns[mart] || []);
      const required = draft.required_columns || [];
      const missing = required.filter((column) => !availableSet.has(column));
      return {
        mart,
        required,
        available: required.filter((column) => availableSet.has(column)),
        missing,
      };
    });
  }, [draft.marts, draft.required_columns, martColumns]);

  const filteredKpis = useMemo(() => {
    const query = kpiSearch.trim().toLowerCase();
    if (!query) return kpis;
    return kpis.filter((kpi) => {
      const haystack = [
        kpi.id,
        kpi.display_name || "",
        kpi.description || "",
        kpi.pillar_id || "",
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [kpiSearch, kpis]);

  const groupedKpis = useMemo(() => {
    const groups = new Map<string, StrategyKpi[]>();
    for (const kpi of filteredKpis) {
      const pillar = (kpi.pillar_id || "unassigned").trim() || "unassigned";
      if (!groups.has(pillar)) {
        groups.set(pillar, []);
      }
      groups.get(pillar)?.push(kpi);
    }
    return Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [filteredKpis]);

  const visibleAgentCandidates = useMemo(
    () => agentCandidates.filter((item) => !ignoredCandidateIds.includes(item.id)),
    [agentCandidates, ignoredCandidateIds]
  );

  const kpiStatus = useCallback(
    (kpi: StrategyKpi): "computable" | "missing_columns" | "missing_mart" | "no_target" => {
      const missingMarts = (kpi.marts || []).filter((mart) => !availableMarts.includes(mart));
      if (missingMarts.length > 0) return "missing_mart";
      for (const mart of kpi.marts || []) {
        const available = new Set(martColumns[mart] || []);
        const hasMissing = (kpi.required_columns || []).some((column) => !available.has(column));
        if (hasMissing) return "missing_columns";
      }
      if (!targetByKpiId.has(kpi.id)) {
        return "no_target";
      }
      return "computable";
    },
    [availableMarts, martColumns, targetByKpiId]
  );

  const openModal = (mode: KpiFormMode, kpi?: StrategyKpi) => {
    setFormMode(mode);
    if (!kpi) {
      setEditingId(null);
      setDraft(emptyKpi());
      setDimensionsDraft("");
      setDerivedMetricsDraft("");
    } else {
      const next = { ...kpi };
      if (mode === "duplicate") {
        next.id = `${kpi.id}_copy`;
      }
      setEditingId(mode === "edit" ? kpi.id : null);
      setDraft(next);
      setDimensionsDraft((next.dimensions || []).join(", "));
      setDerivedMetricsDraft(
        Object.entries(next.derived_metrics || {})
          .map(([name, formula]) => `${name}=${formula}`)
          .join("\n")
      );
    }
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingId(null);
    setDraft(emptyKpi());
    setDimensionsDraft("");
    setDerivedMetricsDraft("");
  };

  const handleApiError = (requestError: unknown, fallback: string) => {
    if (requestError instanceof ApiRequestError && requestError.status === 409) {
      setError("Your strategy changed on disk. Refresh and try again.");
      return;
    }
    setError(requestError instanceof Error ? requestError.message : fallback);
  };

  const addPillarRow = () => {
    setPillarsDraft((prev) => [...prev, { id: "", description: "", owner: "" }]);
  };

  const removePillarRow = (index: number) => {
    setPillarsDraft((prev) => prev.filter((_, itemIndex) => itemIndex !== index));
  };

  const updatePillarField = (index: number, field: keyof StrategyPillarPayload, value: string) => {
    setPillarsDraft((prev) =>
      prev.map((item, itemIndex) => (itemIndex === index ? { ...item, [field]: value } : item))
    );
  };

  const saveOverview = async () => {
    const expectedRevision = overviewRevision || revision;
    if (!expectedRevision) return setError("Missing revision. Refresh and try again.");

    const pillars = pillarsDraft
      .map((item) => ({
        id: (item.id || "").trim(),
        description: (item.description || "").trim(),
        owner: (item.owner || "").trim() || null,
      }))
      .filter((item) => item.id && item.description);

    const swotPayload: StrategySwotPayload = {
      strengths: linesToList(swotText.strengths),
      weaknesses: linesToList(swotText.weaknesses),
      opportunities: linesToList(swotText.opportunities),
      threats: linesToList(swotText.threats),
    };

    const contextPayload: StrategyContextPayload = {
      company: (strategyContextDraft.company || "").trim(),
      horizon: (strategyContextDraft.horizon || "").trim(),
      north_star_metric: (strategyContextDraft.north_star_metric || "").trim(),
      narrative: (strategyContextDraft.narrative || "").trim() || null,
    };
    if (!contextPayload.company || !contextPayload.horizon || !contextPayload.north_star_metric) {
      return setError("Company, horizon, and north star metric are required.");
    }

    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await apiClient.putStrategyOverview({
        expected_revision: expectedRevision,
        strategy_context: contextPayload,
        pillars,
        swot: swotPayload,
        author: user?.username ?? "strategy_editor",
        reason: "Update strategy overview",
      });
      setOverviewRevision(updated.revision);
      setSuccess("Overview saved.");
      await load();
    } catch (requestError) {
      handleApiError(requestError, "Failed to save strategy overview.");
    } finally {
      setSaving(false);
    }
  };

  const openTargetModal = (mode: TargetFormMode, target?: StrategyTarget, fallbackKpiId?: string) => {
    setTargetFormMode(mode);
    if (target) {
      setTargetDraft({
        kpi_id: target.kpi_id,
        target_value: Number(target.target_value ?? 0),
        red_threshold: target.red_threshold ?? null,
        yellow_threshold: target.yellow_threshold ?? null,
        direction: target.direction || "up",
        owner: target.owner || "",
        horizon: target.horizon || "",
      });
    } else {
      setTargetDraft({
        kpi_id: fallbackKpiId || "",
        target_value: 0,
        red_threshold: null,
        yellow_threshold: null,
        direction: "up",
        owner: "",
        horizon: "",
      });
    }
    setTargetModalOpen(true);
  };

  const closeTargetModal = () => {
    setTargetModalOpen(false);
    setTargetFormMode("create");
    setTargetDraft({
      kpi_id: "",
      target_value: 0,
      red_threshold: null,
      yellow_threshold: null,
      direction: "up",
      owner: "",
      horizon: "",
    });
  };

  const saveTarget = async () => {
    const expectedRevision = targetsState?.revision || revision;
    if (!expectedRevision) return setError("Missing revision. Refresh and try again.");
    if (!targetDraft.kpi_id) return setError("KPI is required.");

    const payload = {
      expected_revision: expectedRevision,
      target: {
        kpi_id: targetDraft.kpi_id,
        target_value: Number(targetDraft.target_value),
        red_threshold: targetDraft.red_threshold == null ? null : Number(targetDraft.red_threshold),
        yellow_threshold: targetDraft.yellow_threshold == null ? null : Number(targetDraft.yellow_threshold),
        direction: targetDraft.direction,
        owner: (targetDraft.owner || "").trim() || null,
        horizon: (targetDraft.horizon || "").trim() || null,
      },
      author: user?.username ?? "strategy_editor",
      reason: targetFormMode === "edit" ? `Update target ${targetDraft.kpi_id}` : `Create target ${targetDraft.kpi_id}`,
    };

    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updatedTargets =
        targetFormMode === "edit"
          ? await apiClient.updateStrategyTarget(targetDraft.kpi_id, payload)
          : await apiClient.createStrategyTarget(payload);
      setTargetsState(updatedTargets);
      setSuccess("Target saved.");
      closeTargetModal();
      await load();
    } catch (requestError) {
      handleApiError(requestError, "Failed to save target.");
    } finally {
      setSaving(false);
    }
  };

  const deleteTarget = async (kpiId: string) => {
    const expectedRevision = targetsState?.revision || revision;
    if (!expectedRevision) return setError("Missing revision. Refresh and try again.");
    if (!globalThis.confirm(`Delete target for '${kpiId}'?`)) return;

    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updatedTargets = await apiClient.deleteStrategyTarget(kpiId, {
        expected_revision: expectedRevision,
        author: user?.username ?? "strategy_editor",
        reason: `Delete target ${kpiId}`,
      });
      setTargetsState(updatedTargets);
      setSuccess("Target deleted.");
      await load();
    } catch (requestError) {
      handleApiError(requestError, "Failed to delete target.");
    } finally {
      setSaving(false);
    }
  };

  const generatedRuleCondition = `kpi("${ruleDraft.kpi_id}") ${ruleDraft.operator} ${ruleDraft.threshold || "0"}`;

  const openRuleModal = (mode: RuleFormMode, rule?: StrategyRule) => {
    setRuleFormMode(mode);
    if (!rule) {
      setRuleDraft({
        id: "",
        kpi_id: "",
        operator: "<",
        threshold: "",
        severity: "warn",
        action: "",
        rationale: "",
      });
      setRuleModalOpen(true);
      return;
    }

    const match = rule.condition.match(/kpi\(\s*["']([^"']+)["']\s*\)\s*(<=|>=|<|>|==)\s*([0-9.+-eE]+)/);
    setRuleDraft({
      id: rule.id,
      kpi_id: match?.[1] || "",
      operator: (match?.[2] as RuleDraft["operator"]) || "<",
      threshold: match?.[3] || "",
      severity: rule.severity,
      action: rule.action,
      rationale: rule.rationale || "",
    });
    setRuleModalOpen(true);
  };

  const closeRuleModal = () => {
    setRuleModalOpen(false);
    setRuleFormMode("create");
    setRuleDraft({
      id: "",
      kpi_id: "",
      operator: "<",
      threshold: "",
      severity: "warn",
      action: "",
      rationale: "",
    });
  };

  const saveRule = async () => {
    const expectedRevision = rulesState?.revision || revision;
    if (!expectedRevision) return setError("Missing revision. Refresh and try again.");
    if (!ruleDraft.id.trim()) return setError("Rule id is required.");
    if (!ruleDraft.kpi_id.trim()) return setError("KPI is required.");
    if (!ruleDraft.threshold.trim()) return setError("Threshold is required.");
    if (!ruleDraft.action.trim()) return setError("Action is required.");

    const payload = {
      expected_revision: expectedRevision,
      rule: {
        id: ruleDraft.id.trim(),
        condition: generatedRuleCondition,
        action: ruleDraft.action.trim(),
        severity: ruleDraft.severity,
        rationale: ruleDraft.rationale.trim() || null,
      },
      author: user?.username ?? "strategy_editor",
      reason: ruleFormMode === "edit" ? `Update rule ${ruleDraft.id.trim()}` : `Create rule ${ruleDraft.id.trim()}`,
    };

    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updatedRules =
        ruleFormMode === "edit"
          ? await apiClient.updateStrategyRule(ruleDraft.id.trim(), payload)
          : await apiClient.createStrategyRule(payload);
      setRulesState(updatedRules);
      setSuccess("Rule saved.");
      closeRuleModal();
      await load();
    } catch (requestError) {
      handleApiError(requestError, "Failed to save rule.");
    } finally {
      setSaving(false);
    }
  };

  const deleteRule = async (ruleId: string) => {
    const expectedRevision = rulesState?.revision || revision;
    if (!expectedRevision) return setError("Missing revision. Refresh and try again.");
    if (!globalThis.confirm(`Delete rule '${ruleId}'?`)) return;

    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updatedRules = await apiClient.deleteStrategyRule(ruleId, {
        expected_revision: expectedRevision,
        author: user?.username ?? "strategy_editor",
        reason: `Delete rule ${ruleId}`,
      });
      setRulesState(updatedRules);
      setSuccess("Rule deleted.");
      await load();
    } catch (requestError) {
      handleApiError(requestError, "Failed to delete rule.");
    } finally {
      setSaving(false);
    }
  };

  const saveKpi = async () => {
    if (!revision) return setError("Missing revision. Refresh and try again.");
    const derivedMetrics = Object.fromEntries(
      derivedMetricsDraft
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
          const [left, ...right] = line.includes("=") ? line.split("=") : line.split(":");
          return [left?.trim() || "", right.join("=").trim()];
        })
        .filter(([name, formula]) => Boolean(name) && Boolean(formula))
    );
    const normalized = normalizeKpi({
      ...draft,
      dimensions: dimensionsDraft.split(",").map((v) => v.trim()).filter(Boolean),
      derived_metrics: derivedMetrics,
    });
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
        setAgentCandidates((reconciled.candidates || extracted.candidates || []) as StrategyKpi[]);
        const nextMissing: Record<string, string> = {};
        for (const item of reconciled.missing_dependencies || reconciled.missing || []) {
          nextMissing[item.kpi_id] = missingSummary(item);
        }
        setAgentMissingById(nextMissing);
        const nextMatches: Record<string, string[]> = {};
        for (const item of reconciled.column_matches || []) {
          const rendered = `${item.missing_column} -> ${item.suggested_columns.join(", ")}`;
          if (!nextMatches[item.kpi_id]) {
            nextMatches[item.kpi_id] = [];
          }
          nextMatches[item.kpi_id].push(rendered);
        }
        setAgentColumnMatchesById(nextMatches);
        setIgnoredCandidateIds([]);
      } else {
        setAgentMissingById({});
        setAgentColumnMatchesById({});
        setIgnoredCandidateIds([]);
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
      setAgentColumnMatchesById((prev) => {
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

  const ignoreSuggestedKpi = (kpiId: string) => {
    setIgnoredCandidateIds((prev) => (prev.includes(kpiId) ? prev : [...prev, kpiId]));
  };

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4 bg-gradient-to-br from-white via-indigo-50/20 to-violet-50/20">
      <div className="rounded-xl border border-indigo-200/60 bg-white p-4 shadow-sm flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-slate-900">Strategy</h2>
          <p className="text-xs text-slate-600">
            Dataset: {datasetId} | Revision: {revision ?? "n/a"} | Readiness: {readiness ? scoreText(readiness.overall_score) : "n/a"}
          </p>
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

      {section === "overview" ? (
        <div className="space-y-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-900">Strategy Overview</h3>
              <button
                type="button"
                onClick={() => void saveOverview()}
                disabled={saving}
                className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700 disabled:opacity-60"
              >
                <Save className="h-3.5 w-3.5" />
                Save Overview
              </button>
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <input
                value={strategyContextDraft.company}
                onChange={(event) => setStrategyContextDraft((prev) => ({ ...prev, company: event.target.value }))}
                placeholder="Company"
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
              />
              <input
                value={strategyContextDraft.horizon}
                onChange={(event) => setStrategyContextDraft((prev) => ({ ...prev, horizon: event.target.value }))}
                placeholder="Horizon"
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
              />
              <input
                value={strategyContextDraft.north_star_metric}
                onChange={(event) => setStrategyContextDraft((prev) => ({ ...prev, north_star_metric: event.target.value }))}
                placeholder="North Star Metric"
                className="rounded border border-slate-300 px-2 py-1.5 text-xs md:col-span-2"
              />
              <textarea
                value={strategyContextDraft.narrative || ""}
                onChange={(event) => setStrategyContextDraft((prev) => ({ ...prev, narrative: event.target.value }))}
                placeholder="Narrative"
                className="h-20 rounded border border-slate-300 px-2 py-1.5 text-xs md:col-span-2"
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold text-slate-700">Pillars</h4>
                <button
                  type="button"
                  onClick={addPillarRow}
                  className="inline-flex items-center gap-1 rounded border border-slate-300 px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-50"
                >
                  <Plus className="h-3 w-3" />
                  Add Pillar
                </button>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-500">
                      <th className="px-2 py-2">ID</th>
                      <th className="px-2 py-2">Description</th>
                      <th className="px-2 py-2">Owner</th>
                      <th className="px-2 py-2">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pillarsDraft.map((pillar, index) => (
                      <tr key={`${pillar.id || "pillar"}-${index}`} className="border-b border-slate-100">
                        <td className="px-2 py-2">
                          <input
                            value={pillar.id}
                            onChange={(event) => updatePillarField(index, "id", event.target.value)}
                            className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
                          />
                        </td>
                        <td className="px-2 py-2">
                          <input
                            value={pillar.description}
                            onChange={(event) => updatePillarField(index, "description", event.target.value)}
                            className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
                          />
                        </td>
                        <td className="px-2 py-2">
                          <input
                            value={pillar.owner || ""}
                            onChange={(event) => updatePillarField(index, "owner", event.target.value)}
                            className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
                          />
                        </td>
                        <td className="px-2 py-2">
                          <button
                            type="button"
                            onClick={() => removePillarRow(index)}
                            className="inline-flex items-center gap-1 rounded border border-red-300 px-2 py-1 text-[11px] text-red-700 hover:bg-red-50"
                          >
                            <Trash2 className="h-3 w-3" />
                            Remove
                          </button>
                        </td>
                      </tr>
                    ))}
                    {pillarsDraft.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-2 py-3 text-center text-slate-500">
                          No pillars configured.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <textarea value={swotText.strengths} onChange={(event) => setSwotText((prev) => ({ ...prev, strengths: event.target.value }))} placeholder="Strengths (one per line)" className="h-24 rounded border border-slate-300 px-2 py-1.5 text-xs" />
              <textarea value={swotText.weaknesses} onChange={(event) => setSwotText((prev) => ({ ...prev, weaknesses: event.target.value }))} placeholder="Weaknesses (one per line)" className="h-24 rounded border border-slate-300 px-2 py-1.5 text-xs" />
              <textarea value={swotText.opportunities} onChange={(event) => setSwotText((prev) => ({ ...prev, opportunities: event.target.value }))} placeholder="Opportunities (one per line)" className="h-24 rounded border border-slate-300 px-2 py-1.5 text-xs" />
              <textarea value={swotText.threats} onChange={(event) => setSwotText((prev) => ({ ...prev, threats: event.target.value }))} placeholder="Threats (one per line)" className="h-24 rounded border border-slate-300 px-2 py-1.5 text-xs" />
            </div>
          </div>
          {readiness ? (
            <>
              {!kpisDefined ? <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">No KPIs defined yet. Add KPIs to enable coverage and readiness.</div> : null}
              {kpisDefined && !targetsDefined ? <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">Targets are missing. Configure targets to improve readiness.</div> : null}
              {kpisDefined && !rulesDefined ? <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">Rules are missing. Add strategy rules to improve readiness.</div> : null}
              <div className="grid grid-cols-1 gap-3 md:grid-cols-6">
                <div className="rounded-xl border border-indigo-200 bg-white p-3"><p className="text-xs text-slate-500">Overall</p><p className="text-lg font-semibold text-indigo-700">{scoreText(readiness.overall_score)}</p></div>
                <div className="rounded-xl border border-indigo-200 bg-white p-3"><p className="text-xs text-slate-500">Strategy</p><p className="text-lg font-semibold text-indigo-700">{scoreText(readiness.strategy_completeness)}</p></div>
                <div className="rounded-xl border border-indigo-200 bg-white p-3"><p className="text-xs text-slate-500">KPI</p><p className="text-lg font-semibold text-indigo-700">{scoreText(readiness.kpi_completeness)}</p></div>
                <div className="rounded-xl border border-indigo-200 bg-white p-3"><p className="text-xs text-slate-500">Targets</p><p className="text-lg font-semibold text-indigo-700">{scoreText(readiness.target_completeness)}</p></div>
                <div className="rounded-xl border border-indigo-200 bg-white p-3"><p className="text-xs text-slate-500">Rules</p><p className="text-lg font-semibold text-indigo-700">{scoreText(readiness.rule_completeness)}</p></div>
                <div className="rounded-xl border border-indigo-200 bg-white p-3"><p className="text-xs text-slate-500">Data Readiness</p><p className="text-lg font-semibold text-indigo-700">{kpisDefined ? scoreText(readiness.data_readiness) : "-"}</p></div>
                <div className="rounded-xl border border-indigo-200 bg-white p-3"><p className="text-xs text-slate-500">Reconciliation</p><p className="text-lg font-semibold text-indigo-700">{scoreText(readiness.reconciliation_completeness)}</p></div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <h3 className="text-sm font-semibold text-slate-900">Coverage Gaps</h3>
                {(decision?.coverage_gaps || []).length === 0 ? <p className="mt-2 text-sm text-slate-600">No coverage gaps detected.</p> : (
                  <div className="mt-2 overflow-x-auto"><table className="min-w-full text-left text-xs"><thead><tr className="border-b border-slate-200 text-slate-500"><th className="px-2 py-2">KPI</th><th className="px-2 py-2">Reason</th><th className="px-2 py-2">Details</th></tr></thead><tbody>{(decision?.coverage_gaps || []).map((gap) => <tr key={`${gap.kpi_id}-${gap.reason}`} className="border-b border-slate-100"><td className="px-2 py-2 font-medium">{gap.kpi_id}</td><td className="px-2 py-2">{gap.reason}</td><td className="px-2 py-2">{gapSummary(gap)}</td></tr>)}</tbody></table></div>
                )}
              </div>
            </>
          ) : null}
        </div>
      ) : null}

      {section === "kpi_library" ? (
        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-slate-900">KPI Library</h3>
            <div className="flex items-center gap-2">
              <input
                value={kpiSearch}
                onChange={(event) => setKpiSearch(event.target.value)}
                placeholder="Search KPIs..."
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
              />
              <button
                type="button"
                onClick={() => openModal("create")}
                className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700"
              >
                <Plus className="h-3.5 w-3.5" />
                Add KPI
              </button>
            </div>
          </div>
          {groupedKpis.map(([pillar, items]) => (
            <div key={`pillar-${pillar}`} className="space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-600">{pillar}</h4>
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-500">
                      <th className="px-2 py-2">ID</th>
                      <th className="px-2 py-2">Name</th>
                      <th className="px-2 py-2">Marts</th>
                      <th className="px-2 py-2">Status</th>
                      <th className="px-2 py-2">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((kpi) => {
                      const status = kpiStatus(kpi);
                      const statusLabel =
                        status === "computable"
                          ? "computable"
                          : status === "missing_columns"
                          ? "missing columns"
                          : status === "missing_mart"
                          ? "missing mart"
                          : "no target";
                      const statusClass =
                        status === "computable"
                          ? "bg-emerald-100 text-emerald-700"
                          : status === "no_target"
                          ? "bg-amber-100 text-amber-700"
                          : "bg-red-100 text-red-700";
                      return (
                        <tr key={kpi.id} className="border-b border-slate-100">
                          <td className="px-2 py-2 font-medium">{kpi.id}</td>
                          <td className="px-2 py-2">{kpi.display_name || kpi.description}</td>
                          <td className="px-2 py-2">{(kpi.marts || []).join(", ") || "-"}</td>
                          <td className="px-2 py-2">
                            <span className={`rounded-full px-2 py-0.5 text-[10px] ${statusClass}`}>{statusLabel}</span>
                          </td>
                          <td className="px-2 py-2">
                            <div className="flex flex-wrap gap-1">
                              <button type="button" onClick={() => openModal("edit", kpi)} className="rounded border border-slate-300 px-2 py-0.5 text-[10px] hover:bg-slate-100">Edit</button>
                              <button type="button" onClick={() => openModal("duplicate", kpi)} className="rounded border border-slate-300 px-2 py-0.5 text-[10px] hover:bg-slate-100">Duplicate</button>
                              <button type="button" onClick={() => void deleteKpi(kpi.id)} className="inline-flex items-center gap-1 rounded border border-red-300 px-2 py-0.5 text-[10px] text-red-700 hover:bg-red-50"><Trash2 className="h-3 w-3" />Delete</button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
          {groupedKpis.length === 0 ? <div className="rounded border border-slate-200 px-3 py-4 text-center text-xs text-slate-500">No KPIs match the current filter.</div> : null}
        </div>
      ) : null}

      {section === "targets" ? (
        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">Targets</h3>
            <button
              type="button"
              onClick={() => openTargetModal("create")}
              className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Target
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500">
                  <th className="px-2 py-2">KPI</th>
                  <th className="px-2 py-2">Target</th>
                  <th className="px-2 py-2">Yellow</th>
                  <th className="px-2 py-2">Red</th>
                  <th className="px-2 py-2">Direction</th>
                  <th className="px-2 py-2">Owner</th>
                  <th className="px-2 py-2">Horizon</th>
                  <th className="px-2 py-2">Status</th>
                  <th className="px-2 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {kpis.map((kpi) => {
                  const target = targetByKpiId.get(kpi.id);
                  const status = target ? "configured" : "missing target";
                  return (
                    <tr key={`target-${kpi.id}`} className="border-b border-slate-100">
                      <td className="px-2 py-2 font-medium">{kpi.id}</td>
                      <td className="px-2 py-2">{target ? target.target_value : "-"}</td>
                      <td className="px-2 py-2">{target?.yellow_threshold ?? "-"}</td>
                      <td className="px-2 py-2">{target?.red_threshold ?? "-"}</td>
                      <td className="px-2 py-2">{target?.direction ?? "-"}</td>
                      <td className="px-2 py-2">{target?.owner || "-"}</td>
                      <td className="px-2 py-2">{target?.horizon || "-"}</td>
                      <td className="px-2 py-2">
                        <span className={`rounded-full px-2 py-0.5 text-[10px] ${target ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                          {status}
                        </span>
                      </td>
                      <td className="px-2 py-2">
                        <div className="flex flex-wrap gap-1">
                          {target ? (
                            <>
                              <button
                                type="button"
                                onClick={() => openTargetModal("edit", target)}
                                className="rounded border border-slate-300 px-2 py-0.5 text-[10px] hover:bg-slate-100"
                              >
                                Edit
                              </button>
                              <button
                                type="button"
                                onClick={() => void deleteTarget(kpi.id)}
                                className="inline-flex items-center gap-1 rounded border border-red-300 px-2 py-0.5 text-[10px] text-red-700 hover:bg-red-50"
                              >
                                <Trash2 className="h-3 w-3" />
                                Delete
                              </button>
                            </>
                          ) : (
                            <button
                              type="button"
                              onClick={() => openTargetModal("create", undefined, kpi.id)}
                              className="rounded border border-indigo-300 px-2 py-0.5 text-[10px] text-indigo-700 hover:bg-indigo-50"
                            >
                              Configure
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {kpis.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-2 py-4 text-center text-slate-500">
                      No KPIs found. Add KPIs first.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
      {section === "rules" ? (
        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">Rules</h3>
            <button
              type="button"
              onClick={() => openRuleModal("create")}
              className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Rule
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500">
                  <th className="px-2 py-2">ID</th>
                  <th className="px-2 py-2">Condition</th>
                  <th className="px-2 py-2">Severity</th>
                  <th className="px-2 py-2">Action</th>
                  <th className="px-2 py-2">Status</th>
                  <th className="px-2 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule) => {
                  const refs = extractRuleReferences(rule.condition);
                  const unknownRefs = refs.filter((item) => !knownRuleKpis.has(item));
                  const isValid = unknownRefs.length === 0;
                  return (
                    <tr key={rule.id} className="border-b border-slate-100">
                      <td className="px-2 py-2 font-medium">{rule.id}</td>
                      <td className="px-2 py-2 font-mono text-[11px]">{rule.condition}</td>
                      <td className="px-2 py-2">{rule.severity}</td>
                      <td className="px-2 py-2">{rule.action}</td>
                      <td className="px-2 py-2">
                        <span className={`rounded-full px-2 py-0.5 text-[10px] ${isValid ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                          {isValid ? "valid" : `invalid refs: ${unknownRefs.join(", ")}`}
                        </span>
                      </td>
                      <td className="px-2 py-2">
                        <div className="flex flex-wrap gap-1">
                          <button
                            type="button"
                            onClick={() => openRuleModal("edit", rule)}
                            className="rounded border border-slate-300 px-2 py-0.5 text-[10px] hover:bg-slate-100"
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => void deleteRule(rule.id)}
                            className="inline-flex items-center gap-1 rounded border border-red-300 px-2 py-0.5 text-[10px] text-red-700 hover:bg-red-50"
                          >
                            <Trash2 className="h-3 w-3" />
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {rules.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-2 py-4 text-center text-slate-500">
                      No rules configured.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
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
            <span className="text-xs text-slate-500">{visibleAgentCandidates.length} suggestion(s)</span>
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
          {visibleAgentCandidates.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500">
                    <th className="px-2 py-2">ID</th>
                    <th className="px-2 py-2">Description</th>
                    <th className="px-2 py-2">Formula</th>
                    <th className="px-2 py-2">Dependencies</th>
                    <th className="px-2 py-2">Column Suggestions</th>
                    <th className="px-2 py-2">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleAgentCandidates.map((candidate) => (
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
                        {(agentColumnMatchesById[candidate.id] || []).length > 0 ? (
                          <div className="space-y-1 text-[11px] text-slate-700">
                            {agentColumnMatchesById[candidate.id].map((line) => (
                              <div key={`${candidate.id}-${line}`}>{line}</div>
                            ))}
                          </div>
                        ) : (
                          <span className="text-[11px] text-slate-500">-</span>
                        )}
                      </td>
                      <td className="px-2 py-2">
                        <div className="flex gap-1">
                          <button
                            type="button"
                            onClick={() => void addSuggestedKpi(candidate)}
                            disabled={addingCandidateId === candidate.id}
                            className="rounded border border-indigo-300 px-2 py-1 text-[11px] text-indigo-700 hover:bg-indigo-50 disabled:opacity-60"
                          >
                            {addingCandidateId === candidate.id ? "Adding..." : "Add KPI"}
                          </button>
                          <button
                            type="button"
                            onClick={() => ignoreSuggestedKpi(candidate.id)}
                            className="rounded border border-slate-300 px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-100"
                          >
                            Ignore
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {ignoredCandidateIds.length > 0 ? (
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
              Ignored suggestions: {ignoredCandidateIds.join(", ")}
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

      {targetModalOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-4 shadow-xl">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-900">{targetFormMode === "edit" ? "Edit Target" : "Add Target"}</h3>
              <button type="button" onClick={closeTargetModal} className="rounded-lg p-1 hover:bg-slate-100">
                <X className="h-4 w-4 text-slate-600" />
              </button>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <select
                value={targetDraft.kpi_id}
                onChange={(event) => setTargetDraft((prev) => ({ ...prev, kpi_id: event.target.value }))}
                disabled={targetFormMode === "edit"}
                className="rounded border border-slate-300 px-2 py-1.5 text-xs md:col-span-2"
              >
                <option value="">Select KPI</option>
                {(targetsState?.available_kpis || kpis.map((item) => item.id)).map((kpiId) => (
                  <option key={kpiId} value={kpiId}>
                    {kpiId}
                  </option>
                ))}
              </select>
              <input
                type="number"
                value={targetDraft.target_value}
                onChange={(event) => setTargetDraft((prev) => ({ ...prev, target_value: Number(event.target.value) }))}
                placeholder="Target"
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
              />
              <select
                value={targetDraft.direction}
                onChange={(event) => setTargetDraft((prev) => ({ ...prev, direction: event.target.value as "up" | "down" }))}
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
              >
                <option value="up">up</option>
                <option value="down">down</option>
              </select>
              <input
                type="number"
                value={targetDraft.yellow_threshold ?? ""}
                onChange={(event) =>
                  setTargetDraft((prev) => ({
                    ...prev,
                    yellow_threshold: event.target.value === "" ? null : Number(event.target.value),
                  }))
                }
                placeholder="Yellow threshold"
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
              />
              <input
                type="number"
                value={targetDraft.red_threshold ?? ""}
                onChange={(event) =>
                  setTargetDraft((prev) => ({
                    ...prev,
                    red_threshold: event.target.value === "" ? null : Number(event.target.value),
                  }))
                }
                placeholder="Red threshold"
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
              />
              <input
                value={targetDraft.owner || ""}
                onChange={(event) => setTargetDraft((prev) => ({ ...prev, owner: event.target.value }))}
                placeholder="Owner"
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
              />
              <input
                value={targetDraft.horizon || ""}
                onChange={(event) => setTargetDraft((prev) => ({ ...prev, horizon: event.target.value }))}
                placeholder="Horizon"
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
              />
            </div>
            <div className="mt-4 flex items-center justify-end gap-2">
              <button type="button" onClick={closeTargetModal} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50">Cancel</button>
              <button type="button" onClick={() => void saveTarget()} disabled={saving} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700 disabled:opacity-60">Save Target</button>
            </div>
          </div>
        </div>
      ) : null}

      {ruleModalOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-4 shadow-xl">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-900">{ruleFormMode === "edit" ? "Edit Rule" : "Add Rule"}</h3>
              <button type="button" onClick={closeRuleModal} className="rounded-lg p-1 hover:bg-slate-100">
                <X className="h-4 w-4 text-slate-600" />
              </button>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <input
                value={ruleDraft.id}
                onChange={(event) => setRuleDraft((prev) => ({ ...prev, id: event.target.value }))}
                placeholder="Rule id"
                disabled={ruleFormMode === "edit"}
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
              />
              <select
                value={ruleDraft.severity}
                onChange={(event) =>
                  setRuleDraft((prev) => ({ ...prev, severity: event.target.value as "info" | "warn" | "block" }))
                }
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
              >
                <option value="info">info</option>
                <option value="warn">warn</option>
                <option value="block">block</option>
              </select>
              <select
                value={ruleDraft.kpi_id}
                onChange={(event) => setRuleDraft((prev) => ({ ...prev, kpi_id: event.target.value }))}
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
              >
                <option value="">Select KPI</option>
                {(rulesState?.available_kpis || kpis.map((item) => item.id)).map((kpiId) => (
                  <option key={kpiId} value={kpiId}>
                    {kpiId}
                  </option>
                ))}
              </select>
              <select
                value={ruleDraft.operator}
                onChange={(event) =>
                  setRuleDraft((prev) => ({ ...prev, operator: event.target.value as RuleDraft["operator"] }))
                }
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
              >
                <option value="<">&lt;</option>
                <option value="<=">&lt;=</option>
                <option value=">">&gt;</option>
                <option value=">=">&gt;=</option>
                <option value="==">==</option>
              </select>
              <input
                value={ruleDraft.threshold}
                onChange={(event) => setRuleDraft((prev) => ({ ...prev, threshold: event.target.value }))}
                placeholder="Threshold"
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
              />
              <input
                value={ruleDraft.action}
                onChange={(event) => setRuleDraft((prev) => ({ ...prev, action: event.target.value }))}
                placeholder="Action"
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
              />
              <textarea
                value={ruleDraft.rationale}
                onChange={(event) => setRuleDraft((prev) => ({ ...prev, rationale: event.target.value }))}
                placeholder="Rationale"
                className="h-20 rounded border border-slate-300 px-2 py-1.5 text-xs md:col-span-2"
              />
              <div className="rounded border border-slate-200 bg-slate-50 px-2 py-2 text-[11px] text-slate-700 md:col-span-2">
                Condition: <span className="font-mono">{generatedRuleCondition}</span>
              </div>
            </div>
            <div className="mt-4 flex items-center justify-end gap-2">
              <button type="button" onClick={closeRuleModal} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50">Cancel</button>
              <button type="button" onClick={() => void saveRule()} disabled={saving} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700 disabled:opacity-60">Save Rule</button>
            </div>
          </div>
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
              <textarea
                value={derivedMetricsDraft}
                onChange={(event) => setDerivedMetricsDraft(event.target.value)}
                placeholder={"derived metrics (one per line)\nexample: margin_pct=sum(margin)/sum(net_sales)"}
                className="h-24 rounded border border-slate-300 px-2 py-1.5 text-xs md:col-span-2"
              />
              <div className="md:col-span-2 rounded border border-slate-200 p-2"><p className="text-[11px] text-slate-600 mb-1">Marts</p><div className="grid grid-cols-2 gap-2">{availableMarts.map((mart) => <label key={mart} className="inline-flex items-center gap-2 text-xs text-slate-700"><input type="checkbox" checked={(draft.marts || []).includes(mart)} onChange={(event) => setDraft((prev) => { const next = new Set(prev.marts || []); if (event.target.checked) next.add(mart); else next.delete(mart); return { ...prev, marts: Array.from(next) }; })} />{mart}</label>)}</div></div>
              <div className="md:col-span-2 rounded border border-slate-200 p-2"><p className="text-[11px] text-slate-600 mb-1">Required Columns</p><div className="grid grid-cols-2 gap-2 max-h-32 overflow-y-auto">{draftColumns.map((column) => <label key={column} className="inline-flex items-center gap-2 text-xs text-slate-700"><input type="checkbox" checked={(draft.required_columns || []).includes(column)} onChange={(event) => setDraft((prev) => { const next = new Set(prev.required_columns || []); if (event.target.checked) next.add(column); else next.delete(column); return { ...prev, required_columns: Array.from(next) }; })} />{column}</label>)}</div></div>
              <div className="md:col-span-2 rounded border border-slate-200 p-2">
                <p className="text-[11px] text-slate-600 mb-1">Dependency Preview</p>
                <div className="space-y-1 text-[11px] text-slate-700">
                  {draftDependencyPreview.map((entry) => (
                    <div key={`dep-${entry.mart}`}>
                      <span className="font-medium">{entry.mart}</span>
                      <span className="ml-2">required: {(entry.required || []).join(", ") || "-"}</span>
                      <span className={`ml-2 ${entry.missing.length === 0 ? "text-emerald-700" : "text-red-700"}`}>
                        {entry.missing.length === 0 ? "all available" : `missing: ${entry.missing.join(", ")}`}
                      </span>
                    </div>
                  ))}
                  {draftDependencyPreview.length === 0 ? <div>No marts selected.</div> : null}
                </div>
              </div>
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
