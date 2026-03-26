"use client";

import type { ChartSpecPatch } from "@/lib/types/chat";
import type { ChartSpecV1 } from "@/lib/types/chartspec";

const ALLOWED_PREFIXES = [
  "chart.type",
  "encoding.x.field",
  "encoding.y",
  "filters",
  "sort",
  "limit",
];

const UNSET_ALLOWED = new Set(["filters", "sort"]);

function isAllowedPath(path: string): boolean {
  return ALLOWED_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}.`));
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function setByPath(target: Record<string, unknown>, path: string, value: unknown): void {
  if (!isAllowedPath(path)) {
    throw new Error(`Unsupported patch path: '${path}'`);
  }

  const parts = path.split(".");
  let cursor: unknown = target;
  for (let index = 0; index < parts.length - 1; index += 1) {
    const current = parts[index];
    const next = parts[index + 1];
    if (/^\d+$/.test(current)) {
      const listIndex = Number(current);
      if (!Array.isArray(cursor)) {
        throw new Error(`Patch path '${path}' is invalid.`);
      }
      while (cursor.length <= listIndex) {
        cursor.push(/^\d+$/.test(next) ? [] : {});
      }
      cursor = cursor[listIndex];
      continue;
    }
    if (!cursor || typeof cursor !== "object" || Array.isArray(cursor)) {
      throw new Error(`Patch path '${path}' is invalid.`);
    }
    const record = cursor as Record<string, unknown>;
    if (!(current in record) || record[current] == null) {
      record[current] = /^\d+$/.test(next) ? [] : {};
    }
    cursor = record[current];
  }

  const last = parts[parts.length - 1];
  if (/^\d+$/.test(last)) {
    const listIndex = Number(last);
    if (!Array.isArray(cursor)) {
      throw new Error(`Patch path '${path}' is invalid.`);
    }
    while (cursor.length <= listIndex) {
      cursor.push(null);
    }
    cursor[listIndex] = value;
    return;
  }

  if (!cursor || typeof cursor !== "object" || Array.isArray(cursor)) {
    throw new Error(`Patch path '${path}' is invalid.`);
  }
  (cursor as Record<string, unknown>)[last] = value;
}

function getByPath(target: Record<string, unknown>, path: string): unknown {
  let cursor: unknown = target;
  for (const part of path.split(".")) {
    if (/^\d+$/.test(part)) {
      const listIndex = Number(part);
      if (!Array.isArray(cursor) || cursor.length <= listIndex) {
        return null;
      }
      cursor = cursor[listIndex];
      continue;
    }
    if (!cursor || typeof cursor !== "object" || Array.isArray(cursor)) {
      return null;
    }
    cursor = (cursor as Record<string, unknown>)[part];
  }
  return cursor;
}

function unsetByPath(target: Record<string, unknown>, path: string): void {
  if (!UNSET_ALLOWED.has(path)) {
    throw new Error(`Unsupported unset path: '${path}'`);
  }
  delete target[path];
}

function addByPath(target: Record<string, unknown>, path: string, value: unknown): void {
  if (!isAllowedPath(path)) {
    throw new Error(`Unsupported add path: '${path}'`);
  }

  const existing = getByPath(target, path);
  if (path === "filters" || path === "sort" || path === "encoding.y") {
    if (existing != null && !Array.isArray(existing)) {
      throw new Error(`Patch add path '${path}' must reference a list.`);
    }
    const current = Array.isArray(existing) ? existing : [];
    const incoming = Array.isArray(value) ? value : [value];
    setByPath(target, path, [...current, ...incoming]);
    return;
  }

  if (existing && typeof existing === "object" && !Array.isArray(existing) && value && typeof value === "object" && !Array.isArray(value)) {
    setByPath(target, path, { ...(existing as Record<string, unknown>), ...(value as Record<string, unknown>) });
    return;
  }

  setByPath(target, path, value);
}

export function applyChartSpecPatch(chartSpec: ChartSpecV1, patch: ChartSpecPatch): ChartSpecV1 {
  const payload = clone(chartSpec) as unknown as Record<string, unknown>;

  Object.entries(patch.set ?? {}).forEach(([path, value]) => {
    setByPath(payload, path, value);
  });
  (patch.unset ?? []).forEach((path) => {
    unsetByPath(payload, path);
  });
  Object.entries(patch.add ?? {}).forEach(([path, value]) => {
    addByPath(payload, path, value);
  });

  return payload as unknown as ChartSpecV1;
}
