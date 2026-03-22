"use client";

import type { ChartSpecV1 } from "@/lib/types/chartspec";

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

export function toDisplayLabel(value: unknown): string {
  if (value == null) return "NULL";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return `${value}`;
  return JSON.stringify(value);
}

export function metricColumnCandidates(chartSpec: ChartSpecV1): string[] {
  const metric = chartSpec.encoding.y[0];
  const candidates = [metric.alias, metric.field, "agg_value"].filter(
    (value): value is string => typeof value === "string" && value.length > 0,
  );
  return Array.from(new Set(candidates));
}

export function chartMetricLabel(chartSpec: ChartSpecV1): string {
  const metric = chartSpec.encoding.y[0];
  if (chartSpec.chart.type === "histogram") {
    return metric.field;
  }
  return `${metric.aggregation.toUpperCase()}(${metric.field})`;
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
): { labels: string[]; values: number[]; data: Array<{ category: string; value: number }> } {
  const labels = rows.map((row) => toDisplayLabel(row[xField]));
  const values = rows.map((row) => pickRowMetricValue(row, metricCandidates) ?? 0);
  return {
    labels,
    values,
    data: labels.map((category, index) => ({
      category,
      value: values[index] ?? 0,
    })),
  };
}

export function buildPieData(
  labels: string[],
  values: number[],
  maxSlices = 8,
): Array<{ type: string; value: number }> {
  const pieDataRaw = labels.map((type, index) => ({
    type,
    value: values[index] ?? 0,
  }));

  if (pieDataRaw.length <= maxSlices) {
    return pieDataRaw;
  }

  const sorted = [...pieDataRaw].sort((left, right) => right.value - left.value);
  const head = sorted.slice(0, maxSlices - 1);
  const otherValue = sorted.slice(maxSlices - 1).reduce((sum, item) => sum + item.value, 0);
  return otherValue > 0 ? [...head, { type: "Other", value: otherValue }] : head;
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
