import type { DatasetProfileAPI, StrategyKpi } from "@/lib/api-types";
import type { AvailableMart } from "@/lib/store";
import type { ChartSemanticContext } from "@/lib/types/chartspec";

const PRODUCT_KEYWORDS = ["product", "sku", "item", "brand", "category"];
const CUSTOMER_KEYWORDS = ["customer", "segment", "cohort", "churn"];
const DRILLABLE_ROLES = new Set(["dimension", "datetime", "temporal", "id", "text", "boolean"]);
const TEMPORAL_ROLES = new Set(["datetime", "temporal"]);

type DrillConcept =
  | "channel"
  | "region"
  | "city"
  | "store_type"
  | "store"
  | "segment"
  | "customer"
  | "customer_risk"
  | "category"
  | "brand"
  | "product"
  | "sku"
  | "employee"
  | "date"
  | "month"
  | "quarter"
  | "year"
  | "inventory_risk";

export type DrillRecommendationReason =
  | "kpi_path"
  | "mart_path"
  | "semantic_policy"
  | "schema_fallback";

interface MartDrillRule {
  id: string;
  patterns: RegExp[];
  explicitPaths: string[][];
  fallbackConcepts: DrillConcept[];
  terminalDimensions?: string[];
}

interface MetricFamilyRule {
  id: string;
  label: string;
  patterns: string[];
  preferredConcepts: DrillConcept[];
  terminalConcepts?: DrillConcept[];
  discouragedConcepts?: DrillConcept[];
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
  semanticContext?: ChartSemanticContext | null;
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
  channel: ["channel_type", "channel", "source", "platform"],
  region: ["region", "state", "territory", "zone"],
  city: ["city", "town"],
  store_type: ["store_type", "store_group", "format", "store_class"],
  store: ["store_id", "store", "branch", "location", "outlet"],
  segment: ["segment", "customer_segment", "cohort"],
  customer: ["customer_id", "customer", "account", "member", "loyalty"],
  customer_risk: ["churn_risk_bucket", "risk_bucket", "risk_band", "risk", "bucket"],
  category: ["department", "category", "subcategory", "family", "class", "group", "top_category"],
  brand: ["brand"],
  product: ["product_id", "product", "item"],
  sku: ["sku_id", "sku", "article"],
  employee: ["salesperson_id", "employee_id", "employee", "staff", "associate"],
  date: ["date", "day", "time", "timestamp"],
  month: ["month"],
  quarter: ["quarter"],
  year: ["year"],
  inventory_risk: ["stockout_risk_flag", "overstock_flag", "needs_attention"],
};

const MART_DRILL_RULES: MartDrillRule[] = [
  {
    id: "sales-daily",
    patterns: [/gold_sales_daily/i],
    explicitPaths: [
      ["channel_type", "region", "city", "store_type", "store_id", "sales_date"],
      ["region", "city", "store_type", "store_id", "sales_date"],
      ["store_type", "store_id", "sales_date"],
    ],
    fallbackConcepts: ["channel", "region", "city", "store_type", "store", "date"],
    terminalDimensions: ["store_id", "sales_date"],
  },
  {
    id: "store-sku-daily",
    patterns: [/gold_store_sku_daily/i],
    explicitPaths: [
      ["store_id", "sku_id", "sales_date"],
      ["sales_date", "store_id", "sku_id"],
    ],
    fallbackConcepts: ["store", "sku", "date"],
    terminalDimensions: ["sku_id", "sales_date"],
  },
  {
    id: "store-360",
    patterns: [/gold_store_360/i],
    explicitPaths: [["region", "city", "store_type", "store_id"]],
    fallbackConcepts: ["region", "city", "store_type", "store"],
    terminalDimensions: ["store_id"],
  },
  {
    id: "product-360",
    patterns: [/gold_product_360/i],
    explicitPaths: [
      ["category", "brand", "product_id", "sku_id"],
      ["brand", "product_id", "sku_id"],
      ["category", "sku_id"],
    ],
    fallbackConcepts: ["category", "brand", "product", "sku"],
    terminalDimensions: ["sku_id"],
  },
  {
    id: "customer-360",
    patterns: [/gold_customer_360/i],
    explicitPaths: [
      ["segment", "region", "city", "top_category", "customer_id"],
      ["segment", "churn_risk_bucket", "city", "customer_id"],
      ["region", "city", "customer_id"],
    ],
    fallbackConcepts: ["segment", "region", "city", "customer_risk", "customer"],
    terminalDimensions: ["customer_id"],
  },
  {
    id: "employee-360",
    patterns: [/gold_employee_360/i],
    explicitPaths: [["role", "home_store_id", "salesperson_id"]],
    fallbackConcepts: ["store", "employee"],
    terminalDimensions: ["salesperson_id"],
  },
  {
    id: "inventory-health",
    patterns: [/gold_inventory_health_daily/i],
    explicitPaths: [
      ["store_id", "sku_id", "snapshot_date"],
      ["stockout_risk_flag", "store_id", "sku_id", "snapshot_date"],
      ["overstock_flag", "store_id", "sku_id", "snapshot_date"],
    ],
    fallbackConcepts: ["inventory_risk", "store", "sku", "date"],
    terminalDimensions: ["sku_id", "snapshot_date"],
  },
];

const METRIC_FAMILY_RULES: MetricFamilyRule[] = [
  {
    id: "revenue",
    label: "Revenue",
    patterns: ["sales", "revenue", "growth", "gross", "net"],
    preferredConcepts: ["channel", "region", "city", "store_type", "store", "category", "brand", "product", "sku", "date"],
    terminalConcepts: ["store", "sku", "date"],
    discouragedConcepts: ["customer_risk", "inventory_risk"],
  },
  {
    id: "margin",
    label: "Margin",
    patterns: ["margin", "profit", "net_sales_after_returns"],
    preferredConcepts: ["channel", "region", "city", "store", "category", "brand", "product", "date"],
    terminalConcepts: ["store", "product", "date"],
    discouragedConcepts: ["customer_risk"],
  },
  {
    id: "discount",
    label: "Discount",
    patterns: ["discount", "markdown", "price"],
    preferredConcepts: ["channel", "region", "city", "store", "category", "brand", "product", "date"],
    terminalConcepts: ["store", "product", "date"],
    discouragedConcepts: ["customer_risk"],
  },
  {
    id: "transactions",
    label: "Transactions",
    patterns: ["transaction", "order", "orders", "count", "volume"],
    preferredConcepts: ["channel", "region", "city", "store_type", "store", "date"],
    terminalConcepts: ["store", "date"],
    discouragedConcepts: ["customer_risk"],
  },
  {
    id: "basket",
    label: "Basket",
    patterns: ["basket", "aov", "upt", "units_per_transaction", "avg_order_value"],
    preferredConcepts: ["channel", "region", "city", "store", "category", "brand", "product", "date"],
    terminalConcepts: ["store", "product", "date"],
  },
  {
    id: "inventory",
    label: "Inventory",
    patterns: ["inventory", "stock", "sell", "stockout", "turnover", "reorder"],
    preferredConcepts: ["inventory_risk", "store", "sku", "date"],
    terminalConcepts: ["sku", "date"],
  },
  {
    id: "customer_retention",
    label: "Customer retention",
    patterns: ["repeat", "retention", "active_months", "frequency", "lifetime"],
    preferredConcepts: ["segment", "region", "city", "category", "customer"],
    terminalConcepts: ["customer"],
    discouragedConcepts: ["inventory_risk"],
  },
  {
    id: "customer_risk",
    label: "Customer risk",
    patterns: ["churn", "risk", "return_rate_flag", "rfm"],
    preferredConcepts: ["segment", "customer_risk", "region", "city", "customer"],
    terminalConcepts: ["customer"],
  },
  {
    id: "returns",
    label: "Returns",
    patterns: ["return", "refund"],
    preferredConcepts: ["channel", "region", "city", "store", "category", "brand", "product", "date"],
    terminalConcepts: ["store", "product", "date"],
  },
  {
    id: "marketing",
    label: "Marketing",
    patterns: ["campaign", "uplift", "roi"],
    preferredConcepts: ["channel", "region", "city", "store", "date"],
    terminalConcepts: ["store", "date"],
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

function scoreConceptMatch(columnName: string, keywords: string[]): number {
  const lower = columnName.toLowerCase();
  let score = 0;
  for (const keyword of keywords) {
    if (lower === keyword) score += 12;
    if (lower.startsWith(`${keyword}_`) || lower.endsWith(`_${keyword}`)) score += 10;
    if (lower.includes(keyword)) score += 6;
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

function resolveExplicitPath(path: string[], availableColumns: string[]): string[] {
  const available = new Set(availableColumns);
  return path.filter((dimension) => available.has(dimension));
}

function uniquePath(dimensions: string[]): string[] {
  const output: string[] = [];
  for (const dimension of dimensions) {
    if (!output.includes(dimension)) {
      output.push(dimension);
    }
  }
  return output;
}

function ruleForMart(martId: string | null | undefined): MartDrillRule | null {
  if (!martId) {
    return null;
  }
  return MART_DRILL_RULES.find((rule) => rule.patterns.some((pattern) => pattern.test(martId))) ?? null;
}

function resolveMartPaths(martId: string | null | undefined, availableColumns: string[]): string[][] {
  const rule = ruleForMart(martId);
  if (!rule) {
    return [];
  }
  const explicitPaths = rule.explicitPaths
    .map((path) => uniquePath(resolveExplicitPath(path, availableColumns)))
    .filter((path) => path.length >= 2);
  if (explicitPaths.length > 0) {
    return explicitPaths;
  }
  const fallbackPath = uniquePath(resolveConceptPath(rule.fallbackConcepts, availableColumns));
  return fallbackPath.length >= 2 ? [fallbackPath] : [];
}

function nextPathDimensions(paths: string[][], currentDimension: string, usedDimensions: Set<string>): string[] {
  for (const path of paths) {
    const currentIndex = path.indexOf(currentDimension);
    const candidates =
      currentIndex >= 0
        ? path.slice(currentIndex + 1)
        : path.filter((dimension) => dimension !== currentDimension);
    const filtered = candidates.filter((dimension) => !usedDimensions.has(dimension));
    if (filtered.length > 0) {
      return filtered;
    }
  }
  return [];
}

function hasProductLikeField(columnNames: string[]): boolean {
  return columnNames.some((name) => {
    const lower = name.toLowerCase();
    return PRODUCT_KEYWORDS.some((keyword) => lower.includes(keyword));
  });
}

function hasCustomerLikeField(columnNames: string[]): boolean {
  return columnNames.some((name) => {
    const lower = name.toLowerCase();
    return CUSTOMER_KEYWORDS.some((keyword) => lower.includes(keyword));
  });
}

function kpiLabel(kpi: StrategyKpi): string {
  const displayName = kpi.display_name?.trim();
  return displayName || kpi.id;
}

function kpiPathForMart(kpi: StrategyKpi, martId: string, semanticContext?: ChartSemanticContext | null): string[] {
  if (semanticContext?.matched_kpi_id === kpi.id && semanticContext.mart_hierarchy?.length) {
    return semanticContext.mart_hierarchy;
  }
  const martOverride = kpi.mart_drill_overrides?.[martId];
  if (martOverride && martOverride.length > 0) {
    return martOverride;
  }
  if ((kpi.preferred_drill_path || []).length > 0) {
    return kpi.preferred_drill_path || [];
  }
  return kpi.dimensions || [];
}

function matchStrategyKpis(params: {
  strategyKpis?: StrategyKpi[] | null;
  martId: string;
  metricField?: string | null;
  chartTitle?: string | null;
  currentDimension: string;
  availableColumns: Set<string>;
  semanticContext?: ChartSemanticContext | null;
}): MatchedKpi[] {
  const { strategyKpis, martId, metricField, chartTitle, currentDimension, availableColumns, semanticContext } = params;
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
        ...(kpi.business_concepts || []).flatMap((concept) => normalizeTokens(concept)),
        ...metricAliases.flatMap((alias) => normalizeTokens(alias)),
        ...formulaColumns,
      ]);
      const preferredPath = kpiPathForMart(kpi, martId, semanticContext).filter((dimension) => availableColumns.has(dimension));
      let relevance = 0;

      if ((kpi.marts || []).includes(martId)) relevance += 6;
      if (metricField && (kpi.required_columns || []).includes(metricField)) relevance += 14;
      if (metricField && formulaColumns.includes(metricField)) relevance += 10;
      if (metricField && metricAliases.includes(metricField)) relevance += 8;
      if (semanticContext?.matched_kpi_id === kpi.id) relevance += 24;
      if (preferredPath.includes(currentDimension)) relevance += 10;
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
  martId: string;
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
    const rankedPath =
      currentIndex >= 0
        ? path.filter((dimension) => match.preferredPath.indexOf(dimension) > currentIndex)
        : path;
    const visiblePath = rankedPath.length > 0 ? rankedPath : path;
    const isMartOverride = Boolean(match.kpi.mart_drill_overrides?.[params.martId]?.length);
    const pathLabelPrefix = isMartOverride
      ? `Recommended from KPI path for this mart: ${match.label}`
      : `Recommended from KPI path: ${match.label}`;

    visiblePath.slice(0, 5).forEach((dimension, index) => {
      const boost = Math.max(12, match.relevance + 12 - index * 2);
      const existing = boosts.get(dimension);
      boosts.set(dimension, {
        score: Math.max(existing?.score ?? 0, boost),
        recommendationReason: "kpi_path",
        recommendationLabel: pathLabelPrefix,
        supportingKpis: Array.from(new Set([...(existing?.supportingKpis ?? []), match.label])),
      });
    });

    if (
      match.terminalDimensions.has(params.currentDimension) &&
      visiblePath.length === 0 &&
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
  semanticContext?: ChartSemanticContext | null;
}): MetricFamilyRule | null {
  if (params.semanticContext?.semantic_family) {
    const persistedRule = METRIC_FAMILY_RULES.find((rule) => rule.id === params.semanticContext?.semantic_family);
    if (persistedRule) {
      return persistedRule;
    }
  }

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
      ...(item.kpi.business_concepts || []).flatMap((concept) => normalizeTokens(concept)),
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
  let terminalReason: string | null = null;
  const familyRule = params.familyRule;

  if (familyRule) {
    const resolvedPath = resolveConceptPath(familyRule.preferredConcepts, params.availableColumns);
    const currentIndex = resolvedPath.indexOf(params.currentDimension);
    const nextDimensions =
      currentIndex >= 0
        ? resolvedPath.slice(currentIndex + 1)
        : resolvedPath.filter((dimension) => dimension !== params.currentDimension);

    nextDimensions
      .filter((dimension) => !params.usedDimensions.has(dimension))
      .slice(0, 5)
      .forEach((dimension, index) => {
        boosts.set(dimension, {
          score: Math.max(10, 18 - index * 2),
          recommendationReason: "semantic_policy",
          recommendationLabel: `Recommended from semantic policy: ${familyRule.label}`,
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

    for (const concept of familyRule.discouragedConcepts || []) {
      const discouragedDimensions = resolveConceptPath([concept], params.availableColumns);
      for (const dimension of discouragedDimensions) {
        if (params.usedDimensions.has(dimension) || dimension === params.currentDimension || boosts.has(dimension)) {
          continue;
        }
        boosts.set(dimension, {
          score: -6,
          recommendationReason: "schema_fallback",
          recommendationLabel: `Lower priority for ${familyRule.label.toLowerCase()} analysis`,
          supportingKpis: [],
        });
      }
    }
  }

  const martPaths = resolveMartPaths(params.martId, params.availableColumns);
  const martNextDimensions = nextPathDimensions(martPaths, params.currentDimension, params.usedDimensions);
  martNextDimensions.slice(0, 4).forEach((dimension, index) => {
    const existing = boosts.get(dimension);
    boosts.set(dimension, {
      score: Math.max(existing?.score ?? 0, 16 - index * 2),
      recommendationReason: existing?.recommendationReason ?? "mart_path",
      recommendationLabel: existing?.recommendationLabel ?? "Recommended from mart-specific path",
      supportingKpis: existing?.supportingKpis ?? [],
    });
  });

  const martRule = ruleForMart(params.martId);
  if (
    martRule &&
    martRule.terminalDimensions?.includes(params.currentDimension) &&
    martNextDimensions.length === 0 &&
    terminalReason === null
  ) {
    terminalReason = "You've reached the deepest mart-specific drill level for this view.";
  }

  return {
    boosts,
    terminalReason,
    familyLabel: familyRule?.label ?? null,
  };
}

function keywordScore(name: string, current: string): number {
  const lower = name.toLowerCase();
  const currentLower = current.toLowerCase();
  let score = 0;

  if (lower.includes("category")) score += 10;
  if (lower.includes("brand")) score += 12;
  if (lower.includes("product_id")) score += 14;
  if (lower.includes("sku_id")) score += 15;
  if (lower.includes("segment") || lower.includes("customer_id")) score += 10;
  if (lower.includes("region") || lower.includes("city") || lower.includes("store")) score += 8;
  if (lower.includes("date") || lower.includes("day") || lower.includes("month")) score -= 1;

  if (currentLower.includes("category") && lower.includes("brand")) score += 12;
  if (currentLower.includes("brand") && lower.includes("product_id")) score += 12;
  if (currentLower.includes("product_id") && lower.includes("sku_id")) score += 14;
  if (currentLower.includes("region") && lower.includes("city")) score += 10;
  if (currentLower.includes("city") && lower.includes("store")) score += 10;
  if (currentLower.includes("segment") && lower.includes("customer_id")) score += 12;
  if (currentLower.includes("store") && (lower.includes("product") || lower.includes("sku"))) score += 6;

  return score;
}

function roleScore(role: string): number {
  if (role === "id") return 6;
  if (role === "dimension" || role === "text") return 5;
  if (role === "boolean") return 2;
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

  if (chartType === "histogram") return -100;
  if (chartType === "line") {
    if (currentIsTemporal) return -20;
    if (candidateIsTemporal) return -8;
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
    if (!currentIsTemporal && candidateIsTemporal) return -4;
    return 0;
  }
  return 0;
}

export function suggestProductDrillMarts(availableMarts: AvailableMart[]): string[] {
  return availableMarts
    .filter((mart) => {
      const lower = mart.id.toLowerCase();
      return lower.includes("sku") || lower.includes("product") || lower.includes("inventory");
    })
    .map((mart) => mart.label?.trim() || mart.id)
    .slice(0, 4);
}

function suggestCustomerDrillMarts(availableMarts: AvailableMart[]): string[] {
  return availableMarts
    .filter((mart) => mart.id.toLowerCase().includes("customer"))
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
  const columns = params.availableColumnNames ?? [];
  const martId = params.martId ?? "";
  const martLower = martId.toLowerCase();

  const hasProductColumns = columns.length > 0 && hasProductLikeField(columns);
  const martLikelyHasProduct = martLower.includes("product") || martLower.includes("sku") || martLower.includes("inventory");
  if ((xField.includes("store") || xField.includes("region") || xField.includes("city")) && !hasProductColumns && !martLikelyHasProduct) {
    const suggested = suggestProductDrillMarts(params.availableMarts);
    return suggested.length > 0
      ? `This mart stops at store geography. Switch to ${suggested.join(", ")} for category, brand, product, or SKU drill paths.`
      : "This mart stops at store geography because product-level fields are not exposed here.";
  }

  const hasCustomerColumns = columns.length > 0 && hasCustomerLikeField(columns);
  if ((xField.includes("segment") || xField.includes("churn")) && !hasCustomerColumns && !martLower.includes("customer")) {
    const suggested = suggestCustomerDrillMarts(params.availableMarts);
    return suggested.length > 0
      ? `This mart does not expose customer-level drill fields. Try ${suggested.join(", ")} for segment, cohort, or customer drill paths.`
      : "This mart does not expose customer-level drill fields.";
  }

  return null;
}

export function resolveMartDrillHierarchy(martId: string | null | undefined, availableColumns: string[]): string[] {
  const paths = resolveMartPaths(martId, availableColumns);
  return paths[0] ?? [];
}

export function getConfiguredNextDimensions(params: {
  martId: string | null | undefined;
  currentDimension: string;
  usedDimensions: Set<string>;
  availableColumns: string[];
}): string[] {
  return nextPathDimensions(resolveMartPaths(params.martId, params.availableColumns), params.currentDimension, params.usedDimensions);
}

export function analyzeDrilldown(params: RankDrillCandidatesParams): DrillAnalysis {
  const availableColumns = params.profile.columns.map((column) => column.name);
  const availableColumnSet = new Set(availableColumns);
  const currentColumn = params.profile.columns.find((column) => column.name === params.currentDimension);
  const currentRole = currentColumn?.effective_role ?? "";
  const configuredHierarchy = params.semanticContext?.mart_hierarchy?.length
    ? params.semanticContext.mart_hierarchy.filter((dimension) => availableColumnSet.has(dimension))
    : resolveMartDrillHierarchy(params.martId, availableColumns);
  const preferredNextDimensions =
    configuredHierarchy.length > 0
      ? nextPathDimensions([configuredHierarchy], params.currentDimension, params.usedDimensions)
      : getConfiguredNextDimensions({
          martId: params.martId,
          currentDimension: params.currentDimension,
          usedDimensions: params.usedDimensions,
          availableColumns,
        });
  const configuredBoosts = new Map(
    preferredNextDimensions.map((dimension, index) => [
      dimension,
      {
        score: Math.max(10, 18 - index * 2),
        recommendationReason: "mart_path" as const,
        recommendationLabel: "Recommended from mart-specific path",
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
    semanticContext: params.semanticContext,
  });
  const kpiAnalysis = buildKpiDimensionBoosts({
    matches: matchedKpis,
    martId: params.martId,
    currentDimension: params.currentDimension,
    usedDimensions: params.usedDimensions,
  });
  const familyRule = resolveMetricFamily({
    metricField: params.metricField,
    chartTitle: params.chartTitle,
    matches: matchedKpis,
    semanticContext: params.semanticContext,
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
        Math.min(column.distinct_count, 1000) / 120;
      const configuredBoost = configuredBoosts.get(column.name);
      const kpiBoost = kpiAnalysis.boosts.get(column.name);
      const semanticBoost = semanticAnalysis.boosts.get(column.name);
      const currentConcept = resolveConcept(params.currentDimension);
      const candidateConcept = resolveConcept(column.name);
      const familyPenalty =
        currentConcept &&
        candidateConcept &&
        familyRule?.discouragedConcepts?.includes(candidateConcept) &&
        currentConcept === candidateConcept
          ? -8
          : 0;
      const disallowedPenalty = topMatchedKpi?.disallowedDimensions.has(column.name) ? -10 : 0;
      const winningBoost = [kpiBoost, configuredBoost, semanticBoost]
        .filter((item): item is BoostDetails => Boolean(item))
        .sort((left, right) => right.score - left.score)[0];

      return {
        name: column.name,
        score:
          heuristicScore +
          (configuredBoost?.score ?? 0) +
          (kpiBoost?.score ?? 0) +
          (semanticBoost?.score ?? 0) +
          familyPenalty +
          disallowedPenalty,
        distinctCount: column.distinct_count,
        supportingKpis: winningBoost?.supportingKpis ?? [],
        recommendationReason: winningBoost?.recommendationReason ?? "schema_fallback",
        recommendationLabel: winningBoost?.recommendationLabel ?? "Recommended from schema fallback",
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
          ? "No deeper business dimensions are available for this view."
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

  if (top.recommendationReason === "kpi_path") {
    return top.score >= 14 && (scoreGap >= 1.5 || !runnerUp || runnerUp.recommendationReason === "schema_fallback");
  }
  if (top.recommendationReason === "mart_path") {
    return top.score >= 13 && (scoreGap >= 1 || !runnerUp);
  }
  if (top.recommendationReason === "semantic_policy") {
    return top.score >= 12 && (scoreGap >= 2 || !runnerUp || runnerUp.score <= top.score - 1);
  }
  return top.score >= 16 && scoreGap >= 4;
}
