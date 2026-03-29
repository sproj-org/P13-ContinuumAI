"use client";

import type { ChartSemanticContext, ChartSpecV1, FilterOperator, SortDirection } from "@/lib/types/chartspec";

export interface ChartBuilderSeedFilter {
  field: string;
  op: FilterOperator;
  value: string;
}

export interface ChartBuilderSeed {
  filters: ChartBuilderSeedFilter[];
  sortTarget: "x" | "metric";
  sortDirection: SortDirection;
  resultLimit: number;
  semanticContext?: Partial<ChartSemanticContext> | null;
}

function filterValueToString(op: FilterOperator, value: unknown): string {
  if (op === "between" && Array.isArray(value)) {
    return value.map((item) => String(item ?? "")).join(", ");
  }
  if (op === "in" && Array.isArray(value)) {
    return value.map((item) => String(item ?? "")).join(", ");
  }
  return value == null ? "" : String(value);
}

export function createChartBuilderSeed(chartSpec: ChartSpecV1): ChartBuilderSeed {
  const primarySort = chartSpec.sort?.[0];
  return {
    filters: (chartSpec.filters ?? []).map((filter) => ({
      field: filter.field,
      op: filter.op,
      value: filterValueToString(filter.op, filter.value),
    })),
    sortTarget: primarySort?.field === chartSpec.encoding.x.field ? "x" : "metric",
    sortDirection: primarySort?.direction ?? "desc",
    resultLimit: chartSpec.limit ?? 20,
    semanticContext: chartSpec.semantic_context ?? null,
  };
}
