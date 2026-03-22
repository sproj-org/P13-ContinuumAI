"use client";

import type { DatasetProfileAPI, StrategyKpi } from "@/lib/api-types";
import type { RankedDrillCandidate } from "@/lib/mart-drill-utils";
import type { ChartSpecV1, ChartType } from "@/lib/types/chartspec";

export type TitleStrategy = "comparison" | "trend" | "composition" | "distribution";
export type AxisFormattingStrategy = "categorical" | "temporal" | "distribution";
export type DrillMode = "direct" | "picker" | "disabled";

export interface ChartDisplayPolicy {
  supportsDrill: boolean;
  defaultDrillMode: DrillMode;
  allowQuickDrill: boolean;
  disabledReason?: string;
  titleStrategy: TitleStrategy;
  xAxisStrategy: AxisFormattingStrategy;
}

const TOKEN_LABELS: Record<string, string> = {
  acct: "Account",
  amt: "Amount",
  avg: "Average",
  cust: "Customer",
  dt: "Date",
  geo: "Geo",
  id: "ID",
  inv: "Inventory",
  kpi: "KPI",
  pct: "Percent",
  qty: "Quantity",
  sku: "SKU",
  ts: "Timestamp",
  usd: "USD",
  yoy: "YoY",
};

const TEMPORAL_TOKEN_SET = new Set(["date", "day", "week", "month", "quarter", "year", "hour", "time", "timestamp"]);

function splitIdentifier(value: string): string[] {
  return value
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[^a-zA-Z0-9]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter((token) => token.length > 0);
}

function normalizeWhitespace(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function formatToken(token: string): string {
  const lower = token.toLowerCase();
  const mapped = TOKEN_LABELS[lower];
  if (mapped) {
    return mapped;
  }
  if (/^[A-Z0-9]{2,}$/.test(token)) {
    return token;
  }
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

function shouldHumanizeCategoryValue(value: string): boolean {
  return /^[a-z]+([_-][a-z0-9]+)+$/.test(value);
}

function formatQuarterLabel(raw: string): string | null {
  const normalized = raw.trim();
  const match =
    normalized.match(/^(\d{4})[-/]?Q([1-4])$/i) ??
    normalized.match(/^Q([1-4])[-/ ]?(\d{4})$/i);
  if (!match) {
    return null;
  }
  if (match[1]?.startsWith("Q")) {
    return `Q${match[1].slice(1)} ${match[2]}`;
  }
  return `Q${match[2]} ${match[1]}`;
}

function parseDateValue(value: string): Date | null {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function inferTemporalGranularity(fieldName: string | null | undefined, value: unknown): "time" | "day" | "month" | "quarter" | "year" {
  const lowerField = (fieldName ?? "").toLowerCase();
  if (lowerField.includes("quarter")) return "quarter";
  if (lowerField.includes("month")) return "month";
  if (lowerField.includes("year")) return "year";
  if (lowerField.includes("hour") || lowerField.includes("time") || lowerField.includes("timestamp") || lowerField.endsWith("_at")) {
    return "time";
  }
  if (typeof value === "string") {
    if (formatQuarterLabel(value)) return "quarter";
    if (/^\d{4}$/.test(value.trim())) return "year";
    if (/^\d{4}-\d{2}$/.test(value.trim())) return "month";
    if (value.includes("T") || /\d{2}:\d{2}/.test(value)) return "time";
  }
  return "day";
}

function formatTemporalValue(value: string, fieldName?: string | null): string {
  const quarterLabel = formatQuarterLabel(value);
  if (quarterLabel) {
    return quarterLabel;
  }

  const trimmed = value.trim();
  const granularity = inferTemporalGranularity(fieldName, trimmed);
  if (granularity === "year" && /^\d{4}$/.test(trimmed)) {
    return trimmed;
  }
  if (granularity === "month" && /^\d{4}-\d{2}$/.test(trimmed)) {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }).format(new Date(`${trimmed}-01T00:00:00Z`));
  }

  const parsed = parseDateValue(trimmed);
  if (!parsed) {
    return value;
  }

  if (granularity === "time") {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(parsed);
  }
  if (granularity === "month") {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      year: "numeric",
    }).format(parsed);
  }
  if (granularity === "year") {
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
    }).format(parsed);
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(parsed);
}

function normalizeTokens(value: string | null | undefined): string[] {
  return splitIdentifier(value ?? "").map((token) => token.toLowerCase()).filter((token) => token.length >= 3);
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

function overlaps(left: Iterable<string>, right: Iterable<string>): number {
  const rightSet = new Set(right);
  let count = 0;
  for (const token of left) {
    if (rightSet.has(token)) {
      count += 1;
    }
  }
  return count;
}

function matchedKpiLabel(kpi: StrategyKpi): string {
  return normalizeWhitespace(kpi.display_name?.trim() || kpi.id);
}

function findBestMatchingKpi(chartSpec: ChartSpecV1, strategyKpis?: StrategyKpi[] | null): StrategyKpi | null {
  if (!strategyKpis || strategyKpis.length === 0) {
    return null;
  }

  const metric = chartSpec.encoding.y[0];
  const xField = chartSpec.encoding.x.field;
  const metricTokens = new Set(normalizeTokens(metric.field));
  const xTokens = new Set(normalizeTokens(xField));
  let best: { kpi: StrategyKpi; score: number } | null = null;

  for (const kpi of strategyKpis) {
    const kpiTokens = new Set([
      ...normalizeTokens(kpi.id),
      ...normalizeTokens(kpi.display_name),
      ...extractFormulaColumns(kpi.formula),
    ]);
    let score = 0;
    if ((kpi.marts || []).includes(chartSpec.table)) score += 4;
    if ((kpi.required_columns || []).includes(metric.field)) score += 8;
    if (extractFormulaColumns(kpi.formula).includes(metric.field)) score += 6;
    if ((kpi.dimensions || []).includes(xField)) score += 4;
    score += overlaps(metricTokens, kpiTokens) * 2;
    score += overlaps(xTokens, kpiTokens);
    if (!best || score > best.score) {
      best = { kpi, score };
    }
  }

  return best && best.score >= 8 ? best.kpi : null;
}

function aggregationPrefix(aggregation: ChartSpecV1["encoding"]["y"][0]["aggregation"]): string {
  switch (aggregation) {
    case "avg":
      return "Average";
    case "count":
      return "Count";
    case "min":
      return "Minimum";
    case "max":
      return "Maximum";
    default:
      return "";
  }
}

function timeGrainLabel(fieldName: string): string {
  const lower = fieldName.toLowerCase();
  if (lower.includes("quarter")) return "Quarter";
  if (lower.includes("month")) return "Month";
  if (lower.includes("week")) return "Week";
  if (lower.includes("year")) return "Year";
  if (lower.includes("hour")) return "Hour";
  if (lower.includes("time") || lower.includes("timestamp") || lower.endsWith("_at")) return "Time";
  return "Day";
}

function resolveTitleStrategy(chartSpec: ChartSpecV1): TitleStrategy {
  if (chartSpec.chart.type === "line") return "trend";
  if (chartSpec.chart.type === "pie") return "composition";
  if (chartSpec.chart.type === "histogram") return "distribution";
  return "comparison";
}

function isTemporalRole(role: string | null | undefined): boolean {
  return role === "datetime" || role === "temporal";
}

export function looksTemporalFieldName(value: string | null | undefined): boolean {
  const tokens = splitIdentifier(value ?? "").map((token) => token.toLowerCase());
  return tokens.some((token) => TEMPORAL_TOKEN_SET.has(token));
}

export function humanizeFieldLabel(
  value: string | null | undefined,
  options: { dropIdSuffix?: boolean } = {},
): string {
  const tokens = splitIdentifier(value ?? "");
  if (tokens.length === 0) {
    return "Unknown";
  }

  const normalizedTokens = [...tokens];
  if (options.dropIdSuffix && normalizedTokens.length > 1 && normalizedTokens.at(-1)?.toLowerCase() === "id") {
    normalizedTokens.pop();
  }

  return normalizedTokens.map(formatToken).join(" ");
}

export function chartDimensionLabel(fieldName: string): string {
  if (looksTemporalFieldName(fieldName)) {
    const lower = fieldName.toLowerCase();
    if (lower.includes("date") && !lower.includes("created") && !lower.includes("updated")) {
      return timeGrainLabel(fieldName);
    }
  }
  return humanizeFieldLabel(fieldName, { dropIdSuffix: true });
}

export function humanizeMartLabel(martId: string): string {
  return humanizeFieldLabel(martId.replace(/^(gold|mart)[_-]?/i, ""));
}

export function humanizeChartType(chartType: ChartType | string): string {
  if (chartType === "kpi") {
    return "KPI";
  }
  return humanizeFieldLabel(chartType);
}

export function formatChartCategoryLabel(value: unknown, fieldName?: string | null): string {
  if (value == null || value === "") {
    return "No value";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  if (typeof value === "number") {
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
  }
  if (typeof value === "string") {
    if (looksTemporalFieldName(fieldName) || /^\d{4}(-\d{2}){0,2}/.test(value.trim()) || value.includes("T")) {
      return formatTemporalValue(value, fieldName);
    }
    if (shouldHumanizeCategoryValue(value)) {
      return humanizeFieldLabel(value);
    }
    return value;
  }
  return JSON.stringify(value);
}

export function chartMetricLabel(
  chartSpec: ChartSpecV1,
  options: { strategyKpis?: StrategyKpi[] | null } = {},
): string {
  const matchedKpi = findBestMatchingKpi(chartSpec, options.strategyKpis);
  if (matchedKpi) {
    return matchedKpiLabel(matchedKpi);
  }

  const metric = chartSpec.encoding.y[0];
  const baseLabel = humanizeFieldLabel(metric.field, { dropIdSuffix: metric.aggregation === "count" });
  if (chartSpec.chart.type === "histogram") {
    return baseLabel;
  }

  if (metric.aggregation === "sum") {
    return baseLabel;
  }

  if (metric.aggregation === "count") {
    return baseLabel === "Unknown" ? "Record Count" : `${baseLabel} Count`;
  }

  const prefix = aggregationPrefix(metric.aggregation);
  return prefix ? `${prefix} ${baseLabel}` : baseLabel;
}

export function isTechnicalChartTitle(title: string | null | undefined): boolean {
  const normalized = normalizeWhitespace(title ?? "");
  if (!normalized) {
    return true;
  }
  return (
    /\b(sum|avg|count|min|max)\s*\(/i.test(normalized) ||
    /^computed\b/i.test(normalized) ||
    normalized.includes("_") ||
    /^[a-z0-9_]+ by [a-z0-9_]+$/i.test(normalized)
  );
}

export function resolveChartTitle(params: {
  chartSpec: ChartSpecV1;
  preferredTitle?: string | null;
  strategyKpis?: StrategyKpi[] | null;
}): string {
  const preferredTitle = normalizeWhitespace(params.preferredTitle ?? "");
  if (preferredTitle && !isTechnicalChartTitle(preferredTitle)) {
    return preferredTitle;
  }

  const metricLabel = chartMetricLabel(params.chartSpec, {
    strategyKpis: params.strategyKpis,
  });
  const xField = params.chartSpec.encoding.x.field;
  const groupLabel = chartDimensionLabel(xField);
  const titleStrategy = resolveTitleStrategy(params.chartSpec);

  if (titleStrategy === "distribution") {
    return `Distribution of ${metricLabel}`;
  }
  if (titleStrategy === "composition") {
    return `${metricLabel} Mix by ${groupLabel}`;
  }
  if (titleStrategy === "trend") {
    return `${metricLabel} Trend by ${timeGrainLabel(xField)}`;
  }
  return `${metricLabel} by ${groupLabel}`;
}

export function getChartDisplayPolicy(params: {
  chartSpec: ChartSpecV1;
  currentDimension?: string | null;
  profile?: DatasetProfileAPI | null;
  rankedCandidates?: RankedDrillCandidate[];
}): ChartDisplayPolicy {
  const currentDimension = params.currentDimension ?? params.chartSpec.encoding.x.field;
  const chartType = params.chartSpec.chart.type as ChartType;
  const currentColumn = params.profile?.columns.find((column) => column.name === currentDimension);
  const rankedCandidates = params.rankedCandidates ?? [];
  const currentIsTemporal =
    isTemporalRole(currentColumn?.effective_role) || looksTemporalFieldName(currentDimension);

  const basePolicy: ChartDisplayPolicy = {
    supportsDrill: rankedCandidates.length > 0,
    defaultDrillMode: "direct",
    allowQuickDrill: true,
    titleStrategy: resolveTitleStrategy(params.chartSpec),
    xAxisStrategy: currentIsTemporal ? "temporal" : chartType === "histogram" ? "distribution" : "categorical",
  };

  if (chartType === "histogram") {
    return {
      ...basePolicy,
      supportsDrill: false,
      defaultDrillMode: "disabled",
      allowQuickDrill: false,
      disabledReason: "Histogram drill is disabled because bins are derived ranges, not business entities.",
    };
  }

  if (chartType === "pie") {
    return {
      ...basePolicy,
      defaultDrillMode: "picker",
      allowQuickDrill: true,
      disabledReason: rankedCandidates.length === 0 ? "No deeper dimensions are available for this slice." : undefined,
    };
  }

  if (chartType === "line") {
    if (currentIsTemporal) {
      return {
        ...basePolicy,
        supportsDrill: false,
        defaultDrillMode: "disabled",
        allowQuickDrill: false,
        disabledReason: "Line drill is disabled for time-series trends. Use bar or pie to drill into a selected period.",
      };
    }

    const topCandidate = rankedCandidates[0];
    const hasExplicitBusinessPath =
      topCandidate?.recommendationReason === "kpi_context" ||
      topCandidate?.recommendationReason === "mart_hierarchy";

    if (!hasExplicitBusinessPath) {
      return {
        ...basePolicy,
        supportsDrill: false,
        defaultDrillMode: "disabled",
        allowQuickDrill: false,
        disabledReason: "Line drill stays off unless a clear business drill path is configured.",
      };
    }

    return {
      ...basePolicy,
      defaultDrillMode: "picker",
      allowQuickDrill: false,
    };
  }

  return {
    ...basePolicy,
    disabledReason: rankedCandidates.length === 0 ? "No deeper dimensions are available for this view." : undefined,
  };
}
