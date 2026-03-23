import type { DatasetProfileAPI, StrategyKpi } from "@/lib/api-types";
import type { AvailableMart } from "@/lib/store";

const PRODUCT_KEYWORDS = ["product", "sku", "item"];
const DRILLABLE_ROLES = new Set(["dimension", "datetime", "temporal", "id", "text", "boolean"]);
const TEMPORAL_ROLES = new Set(["datetime", "temporal"]);

type DrillConcept =
  | "channel"
  | "city"
  | "customer"
  | "date"
  | "employee"
  | "product"
  | "region"
  | "risk"
  | "category"
  | "store";

export type DrillRecommendationReason =
  | "kpi_context"
  | "semantic_policy"
  | "mart_hierarchy"
  | "heuristic";

interface MartDrillRule {
  id: string;
  patterns: RegExp[];
  preferredConcepts: DrillConcept[];
  terminalConcepts?: DrillConcept[];
}

interface MetricFamilyRule {
  id: string;
  label: string;
  patterns: string[];
  preferredConcepts: DrillConcept[];
  terminalConcepts?: DrillConcept[];
  lowPriorityConcepts?: DrillConcept[];
}

interface MatchedKpi {
  kpi: StrategyKpi;
  label: string;
  relevance: number;
  preferredPath: string[];
  terminalDimensions: Set<string>;
  disallowedDimensions: Set<string>;
}

type BoostDetails = {
  score: number;
  recommendationReason: DrillRecommendationReason;
  recommendationLabel: string;
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

export interface DrillAnalysis {
  candidates: RankedDrillCandidate[];
  configuredHierarchy: string[];
  preferredNextDimensions: string[];
  terminalReason: string | null;
  matchedKpiLabel: string | null;
  metricFamilyLabel: string | null;
}

const CONCEPT_KEYWORDS: Record<DrillConcept, string[]> = {
  channel: ["channel", "source", "platform"],
  city: ["city", "town"],
  customer: ["customer_id", "customer", "account", "member", "loyalty"],
  date: ["date", "day", "week", "month", "quarter", "year", "time", "timestamp"],
  employee: ["employee_id", "employee", "staff", "associate", "salesperson"],
  product: ["sku_id", "product_id", "sku", "product", "item", "article"],
  region: ["region", "state", "zone", "territory"],
  risk: ["bucket", "risk", "band", "status"],
  category: ["category", "segment", "family", "department", "class", "group"],
  store: ["store_id", "store", "branch", "location", "outlet"],
};

const MART_DRILL_RULES: MartDrillRule[] = [
  {
    id: "store-sales",
    patterns: [/store_sku/i, /sales/i, /transactions?/i],
    preferredConcepts: ["channel", "region", "store", "product", "date"],
    terminalConcepts: ["product", "date"],
  },
  {
    id: "inventory",
    patterns: [/inventory/i],
    preferredConcepts: ["store", "product", "date"],
    terminalConcepts: ["product", "date"],
  },
  {
    id: "product",
    patterns: [/product/i],
    preferredConcepts: ["category", "store", "product", "date"],
    terminalConcepts: ["product", "date"],
  },
  {
    id: "customer",
    patterns: [/customer/i],
    preferredConcepts: ["category", "region", "city", "customer", "date"],
    terminalConcepts: ["customer", "date"],
  },
  {
    id: "employee",
    patterns: [/employee/i],
    preferredConcepts: ["region", "store", "employee", "date"],
    terminalConcepts: ["employee", "date"],
  },
  {
    id: "store",
    patterns: [/store/i],
    preferredConcepts: ["region", "city", "store", "date"],
    terminalConcepts: ["store", "date"],
  },
];

const METRIC_FAMILY_RULES: MetricFamilyRule[] = [
  {
    id: "revenue",
    label: "Revenue",
    patterns: ["sales", "revenue", "margin", "discount", "campaign", "growth"],
    preferredConcepts: ["channel", "region", "store", "product", "date"],
    terminalConcepts: ["product", "date"],
    lowPriorityConcepts: ["risk"],
  },
  {
    id: "transactions",
    label: "Transactions",
    patterns: ["transaction", "order", "orders", "count", "volume"],
    preferredConcepts: ["channel", "store", "date"],
    terminalConcepts: ["store", "date"],
  },
  {
    id: "basket",
    label: "Basket",
    patterns: ["basket", "aov", "upt", "units_per_transaction"],
    preferredConcepts: ["channel", "store", "date"],
    terminalConcepts: ["store", "date"],
  },
  {
    id: "inventory",
    label: "Inventory",
    patterns: ["inventory", "stock", "sell_through", "turnover", "stockout", "sku"],
    preferredConcepts: ["store", "product", "date"],
    terminalConcepts: ["product", "date"],
  },
  {
    id: "customer",
    label: "Customer",
    patterns: ["customer", "repeat", "segment", "churn", "retention", "lifetime"],
    preferredConcepts: ["category", "region", "city", "customer", "risk"],
    terminalConcepts: ["customer", "risk"],
  },
  {
    id: "returns",
    label: "Returns",
    patterns: ["return", "refund"],
    preferredConcepts: ["channel", "store", "product", "date"],
    terminalConcepts: ["product", "date"],
  },
];

const GENERIC_CONCEPT_TRANSITIONS: Partial<Record<DrillConcept, DrillConcept[]>> = {
  region: ["city", "store", "channel"],
  city: ["store", "channel"],
  channel: ["store", "product", "date"],
  category: ["store", "product", "date"],
  store: ["product", "date"],
  product: ["date"],
  customer: ["region", "city", "risk", "date"],
};

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

function chartCompatibilityScore(
  params: RankDrillCandidatesParams,
  column: DatasetProfileAPI["columns"][number],
  currentRole: string,
): number {
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

function resolveConcept(columnName: string | null | undefined): DrillConcept | null {
  if (!columnName) {
    return null;
  }
  let bestConcept: DrillConcept | null = null;
  let bestScore = 0;

  for (const [concept, keywords] of Object.entries(CONCEPT_KEYWORDS) as Array<[DrillConcept, string[]]>) {
    const score = scoreConceptMatch(columnName, keywords);
    if (score > bestScore) {
      bestScore = score;
      bestConcept = concept;
    }
  }

  return bestScore > 0 ? bestConcept : null;
}

function resolveConceptPath(concepts: DrillConcept[], availableColumns: string[]): string[] {
  const remaining = [...availableColumns];
  const resolved: string[] = [];

  for (const concept of concepts) {
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
      remaining.splice(remaining.indexOf(bestColumn), 1);
    }
  }

  return resolved;
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

function semanticFamilyLabel(family: string): string {
  return family
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function matchStrategyKpis(params: {
  strategyKpis?: StrategyKpi[] | null;
  martId: string;
  metricField?: string | null;
  chartTitle?: string | null;
  currentDimension: string;
  availableColumns: Set<string>;
}): MatchedKpi[] {
  const { strategyKpis, martId, metricField, chartTitle, currentDimension, availableColumns } = params;
  if (!strategyKpis || strategyKpis.length === 0) {
    return [];
  }

  const metricTokens = new Set(normalizeTokens(metricField));
  const titleTokens = new Set(normalizeTokens(chartTitle));

  return strategyKpis
    .map((kpi) => {
      const formulaColumns = extractFormulaColumns(kpi.formula);
      const metricAliases = kpi.metric_aliases || [];
      const kpiTokens = new Set([
        ...normalizeTokens(kpiLabel(kpi)),
        ...normalizeTokens(kpi.id),
        ...normalizeTokens(kpi.semantic_family),
        ...metricAliases.flatMap((alias) => normalizeTokens(alias)),
        ...formulaColumns,
      ]);
      const preferredPath = (kpi.preferred_drill_path || kpi.dimensions || []).filter((dimension) => availableColumns.has(dimension));
      let relevance = 0;

      if ((kpi.marts || []).includes(martId)) relevance += 4;
      if (metricField && (kpi.required_columns || []).includes(metricField)) relevance += 14;
      if (metricField && formulaColumns.includes(metricField)) relevance += 10;
      if (metricField && metricAliases.includes(metricField)) relevance += 8;
      if ((kpi.preferred_drill_path || []).includes(currentDimension)) relevance += 8;
      else if ((kpi.dimensions || []).includes(currentDimension)) relevance += 5;
      relevance += overlapCount(metricTokens, kpiTokens) * 2;
      relevance += overlapCount(titleTokens, kpiTokens) * 2;

      return {
        kpi,
        label: kpiLabel(kpi),
        relevance,
        preferredPath,
        terminalDimensions: new Set(kpi.terminal_dimensions || []),
        disallowedDimensions: new Set(kpi.disallowed_drill_dimensions || []),
      };
    })
    .filter((item) => item.relevance >= 8)
    .sort((left, right) => right.relevance - left.relevance)
    .slice(0, 4);
}

function buildKpiDimensionBoosts(params: {
  matches: MatchedKpi[];
  currentDimension: string;
  usedDimensions: Set<string>;
}): { boosts: Map<string, BoostDetails>; terminalReason: string | null; matchedKpiLabel: string | null } {
  const boosts = new Map<string, BoostDetails>();
  let terminalReason: string | null = null;
  const topMatch = params.matches[0] ?? null;

  for (const match of params.matches) {
    const path = match.preferredPath.filter(
      (dimension) => dimension !== params.currentDimension && !params.usedDimensions.has(dimension),
    );
    const currentIndex = match.preferredPath.indexOf(params.currentDimension);
    const preferredPath =
      currentIndex >= 0
        ? path.filter((dimension) => match.preferredPath.indexOf(dimension) > currentIndex)
        : path;
    const rankedPath = (preferredPath.length > 0 ? preferredPath : path).slice(0, 4);
    const pathLabelPrefix =
      (match.kpi.preferred_drill_path || []).length > 0
        ? `Recommended from KPI path: ${match.label}`
        : `Recommended from KPI context: ${match.label}`;

    rankedPath.forEach((dimension, index) => {
      const boost = Math.max(12, match.relevance + ((match.kpi.preferred_drill_path || []).length > 0 ? 10 : 6) - index * 2);
      const existing = boosts.get(dimension);
      boosts.set(dimension, {
        score: Math.max(existing?.score ?? 0, boost),
        recommendationReason: "kpi_context",
        recommendationLabel: pathLabelPrefix,
        supportingKpis: Array.from(new Set([...(existing?.supportingKpis ?? []), match.label])),
      });
    });

    if (
      match.terminalDimensions.has(params.currentDimension) &&
      rankedPath.length === 0 &&
      terminalReason === null
    ) {
      terminalReason = `You've reached the deepest KPI breakdown for ${match.label}.`;
    }
  }

  return {
    boosts,
    terminalReason,
    matchedKpiLabel: topMatch?.label ?? null,
  };
}

function resolveMetricFamily(params: {
  metricField?: string | null;
  chartTitle?: string | null;
  matches: MatchedKpi[];
}): MetricFamilyRule | null {
  const matchedFamily = params.matches.find((item) => typeof item.kpi.semantic_family === "string" && item.kpi.semantic_family.trim());
  if (matchedFamily?.kpi.semantic_family) {
    return METRIC_FAMILY_RULES.find((rule) => rule.id === matchedFamily.kpi.semantic_family) ?? null;
  }

  const tokens = new Set([
    ...normalizeTokens(params.metricField),
    ...normalizeTokens(params.chartTitle),
    ...params.matches.flatMap((item) => [
      ...normalizeTokens(item.label),
      ...normalizeTokens(item.kpi.semantic_family),
      ...(item.kpi.metric_aliases || []).flatMap((alias) => normalizeTokens(alias)),
    ]),
  ]);
  let bestRule: { rule: MetricFamilyRule; score: number } | null = null;

  for (const rule of METRIC_FAMILY_RULES) {
    const score = overlapCount(tokens, rule.patterns);
    if (!bestRule || score > bestRule.score) {
      bestRule = { rule, score };
    }
  }

  return bestRule && bestRule.score > 0 ? bestRule.rule : null;
}

function buildSemanticPolicyBoosts(params: {
  familyRule: MetricFamilyRule | null;
  martId: string;
  availableColumns: string[];
  currentDimension: string;
  usedDimensions: Set<string>;
}): { boosts: Map<string, BoostDetails>; terminalReason: string | null; familyLabel: string | null } {
  const boosts = new Map<string, BoostDetails>();
  const familyRule = params.familyRule;
  let terminalReason: string | null = null;

  if (familyRule) {
    const resolvedPath = resolveConceptPath(familyRule.preferredConcepts, params.availableColumns);
    const currentIndex = resolvedPath.indexOf(params.currentDimension);
    const nextDimensions =
      currentIndex >= 0
        ? resolvedPath.slice(currentIndex + 1)
        : resolvedPath.filter((dimension) => dimension !== params.currentDimension);

    nextDimensions
      .filter((dimension) => !params.usedDimensions.has(dimension))
      .slice(0, 4)
      .forEach((dimension, index) => {
        boosts.set(dimension, {
          score: Math.max(10, 18 - index * 2),
          recommendationReason: "semantic_policy",
          recommendationLabel: `Recommended from business metric policy: ${familyRule.label}`,
          supportingKpis: [],
        });
      });

    const currentConcept = resolveConcept(params.currentDimension);
    if (
      currentConcept &&
      (familyRule.terminalConcepts || []).includes(currentConcept) &&
      nextDimensions.length === 0
    ) {
      terminalReason = `No deeper ${familyRule.label.toLowerCase()} breakdown is configured after this dimension.`;
    }

    for (const concept of familyRule.lowPriorityConcepts || []) {
      const lowPriorityDimensions = resolveConceptPath([concept], params.availableColumns);
      for (const dimension of lowPriorityDimensions) {
        if (params.usedDimensions.has(dimension) || dimension === params.currentDimension || boosts.has(dimension)) {
          continue;
        }
        boosts.set(dimension, {
          score: -4,
          recommendationReason: "heuristic",
          recommendationLabel: "Lower priority for this metric family",
          supportingKpis: [],
        });
      }
    }
  }

  const martRule = MART_DRILL_RULES.find((rule) => rule.patterns.some((pattern) => pattern.test(params.martId)));
  const currentConcept = resolveConcept(params.currentDimension);
  if (martRule && currentConcept) {
    const conceptPath = GENERIC_CONCEPT_TRANSITIONS[currentConcept] || martRule.preferredConcepts;
    const transitionDimensions = resolveConceptPath(conceptPath, params.availableColumns)
      .filter((dimension) => dimension !== params.currentDimension && !params.usedDimensions.has(dimension))
      .slice(0, 3);

    transitionDimensions.forEach((dimension, index) => {
      const existing = boosts.get(dimension);
      const score = Math.max(existing?.score ?? 0, 8 - index * 2);
      boosts.set(dimension, {
        score,
        recommendationReason: existing?.recommendationReason ?? "semantic_policy",
        recommendationLabel: existing?.recommendationLabel ?? "Recommended from semantic field relationships",
        supportingKpis: existing?.supportingKpis ?? [],
      });
    });
  }

  return {
    boosts,
    terminalReason,
    familyLabel: familyRule?.label ?? null,
  };
}

export function suggestProductDrillMarts(availableMarts: AvailableMart[]): string[] {
  return availableMarts
    .filter((mart) => {
      const lower = mart.id.toLowerCase();
      return lower.includes("sku") || lower.includes("product") || lower.includes("inventory");
    })
    .map((mart) => mart.label?.trim() || mart.id)
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

  return resolveConceptPath(rule.preferredConcepts, availableColumns);
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

export function analyzeDrilldown(params: RankDrillCandidatesParams): DrillAnalysis {
  const availableColumns = params.profile.columns.map((column) => column.name);
  const availableColumnSet = new Set(availableColumns);
  const currentColumn = params.profile.columns.find((column) => column.name === params.currentDimension);
  const currentRole = currentColumn?.effective_role ?? "";
  const configuredHierarchy = resolveMartDrillHierarchy(params.martId, availableColumns);
  const preferredNextDimensions = getConfiguredNextDimensions({
    martId: params.martId,
    currentDimension: params.currentDimension,
    usedDimensions: params.usedDimensions,
    availableColumns,
  });
  const configuredBoosts = new Map(
    preferredNextDimensions.map((dimension, index) => [
      dimension,
      {
        score: Math.max(9, 18 - index * 2),
        recommendationReason: "mart_hierarchy" as const,
        recommendationLabel: "Recommended from mart hierarchy",
        supportingKpis: [],
      },
    ]),
  );
  const matchedKpis = matchStrategyKpis({
    strategyKpis: params.strategyKpis,
    martId: params.martId,
    metricField: params.metricField,
    chartTitle: params.chartTitle,
    currentDimension: params.currentDimension,
    availableColumns: availableColumnSet,
  });
  const kpiAnalysis = buildKpiDimensionBoosts({
    matches: matchedKpis,
    currentDimension: params.currentDimension,
    usedDimensions: params.usedDimensions,
  });
  const familyRule = resolveMetricFamily({
    metricField: params.metricField,
    chartTitle: params.chartTitle,
    matches: matchedKpis,
  });
  const semanticAnalysis = buildSemanticPolicyBoosts({
    familyRule,
    martId: params.martId,
    availableColumns,
    currentDimension: params.currentDimension,
    usedDimensions: params.usedDimensions,
  });
  const topMatchedKpi = matchedKpis[0] ?? null;

  const candidates = params.profile.columns
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
      const configuredBoost = configuredBoosts.get(column.name);
      const kpiBoost = kpiAnalysis.boosts.get(column.name);
      const semanticBoost = semanticAnalysis.boosts.get(column.name);
      const currentConcept = resolveConcept(params.currentDimension);
      const candidateConcept = resolveConcept(column.name);
      const disallowedPenalty =
        topMatchedKpi?.disallowedDimensions.has(column.name) ||
        (currentConcept &&
          candidateConcept &&
          familyRule?.lowPriorityConcepts?.includes(candidateConcept) &&
          currentConcept === candidateConcept)
          ? -8
          : 0;

      const winningBoost = [kpiBoost, semanticBoost, configuredBoost]
        .filter((item): item is BoostDetails => Boolean(item))
        .sort((left, right) => right.score - left.score)[0];
      const recommendationReason = winningBoost?.recommendationReason ?? "heuristic";
      const recommendationLabel = winningBoost?.recommendationLabel ?? "Recommended from field semantics";
      const supportingKpis = winningBoost?.supportingKpis ?? [];

      return {
        name: column.name,
        score:
          heuristicScore +
          (configuredBoost?.score ?? 0) +
          (kpiBoost?.score ?? 0) +
          (semanticBoost?.score ?? 0) +
          disallowedPenalty,
        distinctCount: column.distinct_count,
        supportingKpis,
        recommendationReason,
        recommendationLabel,
      };
    })
    .filter((candidate) => candidate.score > -20)
    .sort((left, right) => {
      if (right.score !== left.score) return right.score - left.score;
      if (right.distinctCount !== left.distinctCount) return right.distinctCount - left.distinctCount;
      return left.name.localeCompare(right.name);
    });

  const terminalReason =
    candidates.length === 0
      ? kpiAnalysis.terminalReason ||
        semanticAnalysis.terminalReason ||
        (preferredNextDimensions.length === 0
          ? "No deeper dimensions are available for this view."
          : "No stronger drill candidate is available from this point.")
      : null;

  return {
    candidates,
    configuredHierarchy,
    preferredNextDimensions,
    terminalReason,
    matchedKpiLabel: kpiAnalysis.matchedKpiLabel,
    metricFamilyLabel: semanticAnalysis.familyLabel,
  };
}

export function rankDrillCandidates(params: RankDrillCandidatesParams): RankedDrillCandidate[] {
  return analyzeDrilldown(params).candidates;
}

export function isStrongDrillRecommendation(candidates: RankedDrillCandidate[]): boolean {
  if (candidates.length === 0) {
    return false;
  }

  const top = candidates[0];
  const runnerUp = candidates[1] ?? null;
  const scoreGap = runnerUp ? top.score - runnerUp.score : top.score;

  if (top.recommendationReason === "kpi_context") {
    return top.score >= 14 && (scoreGap >= 1.5 || !runnerUp || runnerUp.recommendationReason === "heuristic");
  }
  if (top.recommendationReason === "semantic_policy") {
    return top.score >= 13 && (scoreGap >= 2 || !runnerUp || runnerUp.score <= top.score - 1);
  }
  if (top.recommendationReason === "mart_hierarchy") {
    return top.score >= 12 && (scoreGap >= 1 || !runnerUp);
  }
  return top.score >= 16 && scoreGap >= 4;
}
