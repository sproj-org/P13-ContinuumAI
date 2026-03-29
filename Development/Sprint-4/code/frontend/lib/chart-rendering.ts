"use client";

import type { ChartSpecV1 } from "@/lib/types/chartspec";
import {
  chartMetricLabel as resolveChartMetricLabel,
  formatChartCategoryLabel,
} from "@/lib/chart-display";

export const CHART_PALETTE = [
  "#8b5cf6",
  "#3b82f6",
  "#4f46e5",
  "#6366f1",
  "#f59e0b",
  "#ef4444",
  "#10b981",
  "#ec4899",
];

type ChartRows = Array<Record<string, unknown>>;

export interface CategoricalSeriesDatum {
  category: string;
  rawCategory: unknown;
  value: number;
}

export function toDisplayLabel(value: unknown, fieldName?: string): string {
  return formatChartCategoryLabel(value, fieldName);
}

export function metricColumnCandidates(chartSpec: ChartSpecV1): string[] {
  const metric = chartSpec.encoding.y[0];
  const candidates = [metric.alias, metric.field, "agg_value"].filter(
    (value): value is string => typeof value === "string" && value.length > 0,
  );
  return Array.from(new Set(candidates));
}

export function chartMetricLabel(chartSpec: ChartSpecV1): string {
  return resolveChartMetricLabel(chartSpec);
}

export function pickRowMetricValue(
  row: Record<string, unknown>,
  candidates: string[],
): number | null {
  for (const candidate of candidates) {
    const raw = row[candidate];
    if (raw == null || raw === "") {
      continue;
    }
    const value = Number(raw);
    if (Number.isFinite(value)) {
      return value;
    }
  }
  return null;
}

export function buildCategoricalSeries(
  rows: ChartRows,
  {
    xField,
    metricCandidates,
  }: {
    xField: string;
    metricCandidates: string[];
  },
): { labels: string[]; values: number[]; data: CategoricalSeriesDatum[] } {
  const data = rows.map((row) => {
    const rawCategory = row[xField];
    return {
      category: toDisplayLabel(rawCategory, xField),
      rawCategory,
      value: pickRowMetricValue(row, metricCandidates) ?? 0,
    };
  });
  const labels = data.map((item) => item.category);
  const values = data.map((item) => item.value);
  return {
    labels,
    values,
    data,
  };
}

export function buildPieData(
  data: CategoricalSeriesDatum[],
  maxSlices = 8,
): Array<{ type: string; value: number; rawCategory: unknown }> {
  const pieDataRaw = data.map((item) => ({
    type: item.category,
    value: item.value,
    rawCategory: item.rawCategory,
  }));

  if (pieDataRaw.length <= maxSlices) {
    return pieDataRaw;
  }

  const sorted = [...pieDataRaw].sort((left, right) => right.value - left.value);
  const head = sorted.slice(0, maxSlices - 1);
  const otherValue = sorted.slice(maxSlices - 1).reduce((sum, item) => sum + item.value, 0);
  return otherValue > 0 ? [...head, { type: "Other", value: otherValue, rawCategory: null }] : head;
}

export function buildHistogramData(
  rows: ChartRows,
  metricCandidates: string[],
): Array<{ value: number }> {
  return rows
    .map((row) => pickRowMetricValue(row, metricCandidates))
    .filter((value): value is number => value !== null)
    .map((value) => ({ value }));
}
