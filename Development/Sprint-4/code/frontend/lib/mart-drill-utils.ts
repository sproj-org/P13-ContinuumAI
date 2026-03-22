import type { DatasetProfileAPI, StrategyKpi } from "@/lib/api-types";
import type { AvailableMart } from "@/lib/store";

const PRODUCT_KEYWORDS = ["product", "sku", "item"];
const DRILLABLE_ROLES = new Set(["dimension", "datetime", "temporal", "id", "text", "boolean"]);
const TEMPORAL_ROLES = new Set(["datetime", "temporal"]);

type DrillConcept = "store" | "product" | "date" | "category" | "customer" | "employee" | "region" | "city";
type DrillRecommendationReason = "kpi_context" | "mart_hierarchy" | "heuristic";

interface MartDrillRule {
  id: string;
  patterns: RegExp[];
  concepts: DrillConcept[];
}

type KpiBoostDetails = {
  score: number;
  supportingKpis: string[];
};

export interface RankedDrillCandidate {
  name: string;
  score: number;
  distinctCount: number;
  supportingKpis: string[];
  recommendationReason: DrillRecommendationReason;
  recommendationLabel: string;
}

export interface RankDrillCandidatesParams {
  profile: DatasetProfileAPI;
  martId: string;
  currentDimension: string;
  usedDimensions: Set<string>;
  metricField?: string | null;
  chartTitle?: string | null;
  chartType?: string | null;
  strategyKpis?: StrategyKpi[] | null;
}

const CONCEPT_KEYWORDS: Record<DrillConcept, string[]> = {
  store: ["store_id", "store", "branch", "location", "outlet"],
  product: ["sku_id", "product_id", "sku", "product", "item"],
  date: ["date", "day", "month", "week", "quarter", "year"],
  category: ["category", "segment", "family", "department"],
  customer: ["customer_id", "customer", "account"],
  employee: ["employee_id", "employee", "staff", "associate"],
  region: ["region", "state", "zone", "territory"],
  city: ["city", "town"],
};

const MART_DRILL_RULES: MartDrillRule[] = [
  {
    id: "store-sales",
    patterns: [/store_sku/i, /sales/i, /transactions?/i],
    concepts: ["store", "product", "date"],
  },
  {
    id: "inventory",
    patterns: [/inventory/i],
    concepts: ["store", "product", "date"],
  },
  {
    id: "product",
    patterns: [/product/i],
    concepts: ["product", "category", "store", "date"],
  },
  {
    id: "customer",
    patterns: [/customer/i],
    concepts: ["customer", "region", "city", "date"],
  },
  {
    id: "employee",
    patterns: [/employee/i],
    concepts: ["employee", "store", "date"],
  },
  {
    id: "store",
    patterns: [/store/i],
    concepts: ["region", "city", "store", "date"],
  },
];

function normalizeTokens(value: string | null | undefined): string[] {
  return (value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .split(" ")
    .map((token) => token.trim())
    .filter((token) => token.length >= 3);
}

function extractFormulaColumns(formula: string | null | undefined): string[] {
  const reserved = new Set([
    "sum",
    "avg",
    "count",
    "min",
    "max",
    "case",
    "when",
    "then",
    "else",
    "end",
    "and",
    "or",
    "not",
    "null",
    "coalesce",
    "round",
    "abs",
    "nullif",
  ]);
  const matches = (formula ?? "").match(/[a-zA-Z_][a-zA-Z0-9_]*/g) ?? [];
  return Array.from(new Set(matches.filter((token) => !reserved.has(token.toLowerCase()))));
}

function overlapCount(left: Iterable<string>, right: Iterable<string>): number {
  const rightSet = new Set(right);
  let overlap = 0;
  for (const token of left) {
    if (rightSet.has(token)) {
      overlap += 1;
    }
  }
  return overlap;
}

function keywordScore(name: string, current: string): number {
  const lower = name.toLowerCase();
  const currentLower = current.toLowerCase();
  let score = 0;

  if (lower.includes("sku") || lower.includes("product") || lower.includes("item")) score += 8;
  if (lower.includes("store") || lower.includes("city") || lower.includes("region")) score += 5;
  if (lower.includes("category") || lower.includes("segment") || lower.includes("channel")) score += 4;
  if (lower.includes("date") || lower.includes("day") || lower.includes("month")) score -= 2;
  if (currentLower.includes("store") && (lower.includes("sku") || lower.includes("product"))) score += 6;

  return score;
}

function roleScore(role: string): number {
  if (role === "id") return 6;
  if (role === "dimension" || role === "text") return 5;
  if (role === "boolean") return 3;
  if (TEMPORAL_ROLES.has(role)) return 1;
  return 0;
}

function looksTemporalFieldName(name: string): boolean {
  const lower = name.toLowerCase();
  return ["date", "day", "week", "month", "quarter", "year", "time", "timestamp"].some((token) => lower.includes(token));
}

function chartCompatibilityScore(params: RankDrillCandidatesParams, column: DatasetProfileAPI["columns"][number], currentRole: string): number {
  const chartType = params.chartType ?? "bar";
  const candidateIsTemporal = TEMPORAL_ROLES.has(column.effective_role) || looksTemporalFieldName(column.name);
  const currentIsTemporal = TEMPORAL_ROLES.has(currentRole) || looksTemporalFieldName(params.currentDimension);

  if (chartType === "histogram") {
    return -100;
  }

  if (chartType === "line") {
    if (currentIsTemporal) {
      return -20;
    }
    if (candidateIsTemporal) {
      return -8;
    }
    return 4;
  }

  if (chartType === "pie") {
    let score = 0;
    if (candidateIsTemporal) score -= 6;
    if (column.distinct_count > 48) score -= 8;
    if (column.distinct_count <= 12) score += 3;
    return score;
  }

  if (chartType === "bar") {
    if (!currentIsTemporal && candidateIsTemporal) {
      return -4;
    }
    return 0;
  }

  return 0;
}

function scoreConceptMatch(columnName: string, keywords: string[]): number {
  const lower = columnName.toLowerCase();
  let score = 0;

  for (const keyword of keywords) {
    if (lower === keyword) score += 10;
    if (lower.startsWith(`${keyword}_`) || lower.endsWith(`_${keyword}`)) score += 8;
    if (lower.includes(keyword)) score += 5;
  }

  return score;
}

function hasProductLikeField(columnNames: string[]): boolean {
  return columnNames.some((name) => {
    const lower = name.toLowerCase();
    return PRODUCT_KEYWORDS.some((keyword) => lower.includes(keyword));
  });
}

function kpiLabel(kpi: StrategyKpi): string {
  const displayName = kpi.display_name?.trim();
  return displayName || kpi.id;
}

function buildKpiDimensionBoosts(params: {
  strategyKpis?: StrategyKpi[] | null;
  martId: string;
  metricField?: string | null;
  chartTitle?: string | null;
  currentDimension: string;
  usedDimensions: Set<string>;
  availableColumns: Set<string>;
}): Map<string, KpiBoostDetails> {
  const { strategyKpis, martId, metricField, chartTitle, currentDimension, usedDimensions, availableColumns } = params;
  if (!strategyKpis || strategyKpis.length === 0) {
    return new Map();
  }

  const metricTokens = new Set(normalizeTokens(metricField));
  const titleTokens = new Set(normalizeTokens(chartTitle));
  const boosts = new Map<string, KpiBoostDetails>();

  const relevantKpis = strategyKpis
    .map((kpi) => {
      const formulaColumns = extractFormulaColumns(kpi.formula);
      const kpiTokens = new Set([...normalizeTokens(kpiLabel(kpi)), ...normalizeTokens(kpi.id), ...formulaColumns]);
      let relevance = 0;

      if ((kpi.marts || []).includes(martId)) relevance += 3;
      if (metricField && (kpi.required_columns || []).includes(metricField)) relevance += 12;
      if (metricField && formulaColumns.includes(metricField)) relevance += 10;
      if ((kpi.dimensions || []).includes(currentDimension)) relevance += 6;
      relevance += overlapCount(metricTokens, kpiTokens) * 2;
      relevance += overlapCount(titleTokens, kpiTokens) * 2;

      return { kpi, relevance };
    })
    .filter((item) => item.relevance >= 6)
    .sort((left, right) => right.relevance - left.relevance)
    .slice(0, 4);

  for (const item of relevantKpis) {
    const dimensionPath = (item.kpi.dimensions || []).filter(
      (dimension) => availableColumns.has(dimension) && dimension !== currentDimension && !usedDimensions.has(dimension),
    );
    if (dimensionPath.length === 0) {
      continue;
    }

    const currentIndex = (item.kpi.dimensions || []).indexOf(currentDimension);
    const preferredPath = currentIndex >= 0 ? dimensionPath.filter((dimension) => (item.kpi.dimensions || []).indexOf(dimension) > currentIndex) : dimensionPath;
    const rankedPath = (preferredPath.length > 0 ? preferredPath : dimensionPath).slice(0, 3);

    rankedPath.forEach((dimension, index) => {
      const boost = Math.max(5, item.relevance + (currentIndex >= 0 ? 6 : 3) - index * 2);
      const existing = boosts.get(dimension);
      const label = kpiLabel(item.kpi);
      boosts.set(dimension, {
        score: (existing?.score ?? 0) + boost,
        supportingKpis: Array.from(new Set([...(existing?.supportingKpis ?? []), label])),
      });
    });
  }

  return boosts;
}

export function suggestProductDrillMarts(availableMarts: AvailableMart[]): string[] {
  return availableMarts
    .map((mart) => mart.id)
    .filter((id) => {
      const lower = id.toLowerCase();
      return lower.includes("sku") || lower.includes("product") || lower.includes("inventory");
    })
    .slice(0, 3);
}

export function getMartDrillAdvisory(params: {
  xField: string | null | undefined;
  martId: string | null | undefined;
  availableMarts: AvailableMart[];
  availableColumnNames?: string[];
}): string | null {
  const xField = params.xField?.toLowerCase() ?? "";
  if (!xField.includes("store")) return null;

  const columns = params.availableColumnNames ?? [];
  const martId = params.martId ?? "";
  const martLower = martId.toLowerCase();

  const hasProductColumns = columns.length > 0 && hasProductLikeField(columns);
  const martLikelyHasProduct =
    martLower.includes("product") || martLower.includes("sku") || martLower.includes("inventory");

  if (hasProductColumns || martLikelyHasProduct) {
    return null;
  }

  const suggested = suggestProductDrillMarts(params.availableMarts);
  if (suggested.length === 0) {
    return "This mart does not expose product-level fields for drilldown.";
  }
  return `This mart does not expose product-level fields for drilldown. Try: ${suggested.join(", ")}.`;
}

export function resolveMartDrillHierarchy(martId: string | null | undefined, availableColumns: string[]): string[] {
  if (!martId || availableColumns.length === 0) return [];

  const rule = MART_DRILL_RULES.find((candidate) => candidate.patterns.some((pattern) => pattern.test(martId)));
  if (!rule) return [];

  const remaining = [...availableColumns];
  const resolved: string[] = [];

  for (const concept of rule.concepts) {
    const keywords = CONCEPT_KEYWORDS[concept];
    let bestColumn: string | null = null;
    let bestScore = 0;

    for (const column of remaining) {
      const score = scoreConceptMatch(column, keywords);
      if (score > bestScore) {
        bestScore = score;
        bestColumn = column;
      }
    }

    if (bestColumn && bestScore > 0) {
      resolved.push(bestColumn);
      const index = remaining.indexOf(bestColumn);
      if (index >= 0) {
        remaining.splice(index, 1);
      }
    }
  }

  return resolved;
}

export function getConfiguredNextDimensions(params: {
  martId: string | null | undefined;
  currentDimension: string;
  usedDimensions: Set<string>;
  availableColumns: string[];
}): string[] {
  const configuredHierarchy = resolveMartDrillHierarchy(params.martId, params.availableColumns);
  if (configuredHierarchy.length === 0) return [];

  const currentIndex = configuredHierarchy.findIndex((name) => name === params.currentDimension);
  const candidates = currentIndex >= 0 ? configuredHierarchy.slice(currentIndex + 1) : configuredHierarchy;

  return candidates.filter((name) => name !== params.currentDimension && !params.usedDimensions.has(name));
}

export function rankDrillCandidates(params: RankDrillCandidatesParams): RankedDrillCandidate[] {
  const availableColumns = params.profile.columns.map((column) => column.name);
  const availableColumnSet = new Set(availableColumns);
  const currentColumn = params.profile.columns.find((column) => column.name === params.currentDimension);
  const currentRole = currentColumn?.effective_role ?? "";
  const configuredNext = getConfiguredNextDimensions({
    martId: params.martId,
    currentDimension: params.currentDimension,
    usedDimensions: params.usedDimensions,
    availableColumns,
  });
  const configuredBoosts = new Map(configuredNext.map((dimension, index) => [dimension, Math.max(7, 16 - index * 2)]));
  const kpiBoosts = buildKpiDimensionBoosts({
    strategyKpis: params.strategyKpis,
    martId: params.martId,
    metricField: params.metricField,
    chartTitle: params.chartTitle,
    currentDimension: params.currentDimension,
    usedDimensions: params.usedDimensions,
    availableColumns: availableColumnSet,
  });

  return params.profile.columns
    .filter((column) => DRILLABLE_ROLES.has(column.effective_role))
    .filter((column) => column.name !== params.currentDimension)
    .filter((column) => !params.usedDimensions.has(column.name))
    .map((column) => {
      const compatibility = chartCompatibilityScore(params, column, currentRole);
      const heuristicScore =
        compatibility +
        keywordScore(column.name, params.currentDimension) +
        roleScore(column.effective_role) +
        Math.min(column.distinct_count, 1000) / 100;
      const configuredBoost = configuredBoosts.get(column.name) ?? 0;
      const kpiBoost = kpiBoosts.get(column.name)?.score ?? 0;

      let recommendationReason: DrillRecommendationReason = "heuristic";
      if (kpiBoost > configuredBoost && kpiBoost > 0) {
        recommendationReason = "kpi_context";
      } else if (configuredBoost > 0) {
        recommendationReason = "mart_hierarchy";
      }

      const supportingKpis = kpiBoosts.get(column.name)?.supportingKpis ?? [];
      const recommendationLabel =
        recommendationReason === "kpi_context"
          ? supportingKpis.length > 0
            ? `Recommended from KPI context: ${supportingKpis.join(", ")}`
            : "Recommended from KPI context"
          : recommendationReason === "mart_hierarchy"
          ? "Recommended from mart hierarchy"
          : "Recommended from field semantics";

      return {
        name: column.name,
        score: heuristicScore + configuredBoost + kpiBoost,
        distinctCount: column.distinct_count,
        supportingKpis,
        recommendationReason,
        recommendationLabel,
      };
    })
    .sort((left, right) => {
      if (right.score !== left.score) return right.score - left.score;
      if (right.distinctCount !== left.distinctCount) return right.distinctCount - left.distinctCount;
      return left.name.localeCompare(right.name);
    });
}

export function isStrongDrillRecommendation(candidates: RankedDrillCandidate[]): boolean {
  if (candidates.length === 0) {
    return false;
  }
  if (candidates.length === 1) {
    return true;
  }

  const top = candidates[0];
  const runnerUp = candidates[1];
  const scoreGap = top.score - runnerUp.score;
  if (top.recommendationReason === "kpi_context") {
    return top.score >= 18 && scoreGap >= 3;
  }
  if (top.recommendationReason === "mart_hierarchy") {
    return top.score >= 14 && scoreGap >= 2;
  }
  return top.score >= 16 && scoreGap >= 7;
}
