import type { AvailableMart } from '@/lib/store';

const PRODUCT_KEYWORDS = ['product', 'sku', 'item'];

type DrillConcept = 'store' | 'product' | 'date' | 'category' | 'customer' | 'employee' | 'region' | 'city';

interface MartDrillRule {
  id: string;
  patterns: RegExp[];
  concepts: DrillConcept[];
}

const CONCEPT_KEYWORDS: Record<DrillConcept, string[]> = {
  store: ['store_id', 'store', 'branch', 'location', 'outlet'],
  product: ['sku_id', 'product_id', 'sku', 'product', 'item'],
  date: ['date', 'day', 'month', 'week', 'quarter', 'year'],
  category: ['category', 'segment', 'family', 'department'],
  customer: ['customer_id', 'customer', 'account'],
  employee: ['employee_id', 'employee', 'staff', 'associate'],
  region: ['region', 'state', 'zone', 'territory'],
  city: ['city', 'town'],
};

const MART_DRILL_RULES: MartDrillRule[] = [
  {
    id: 'store-sales',
    patterns: [/store_sku/i, /sales/i, /transactions?/i],
    concepts: ['store', 'product', 'date'],
  },
  {
    id: 'inventory',
    patterns: [/inventory/i],
    concepts: ['store', 'product', 'date'],
  },
  {
    id: 'product',
    patterns: [/product/i],
    concepts: ['product', 'category', 'store', 'date'],
  },
  {
    id: 'customer',
    patterns: [/customer/i],
    concepts: ['customer', 'region', 'city', 'date'],
  },
  {
    id: 'employee',
    patterns: [/employee/i],
    concepts: ['employee', 'store', 'date'],
  },
  {
    id: 'store',
    patterns: [/store/i],
    concepts: ['region', 'city', 'store', 'date'],
  },
];

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

export function suggestProductDrillMarts(availableMarts: AvailableMart[]): string[] {
  return availableMarts
    .map((mart) => mart.id)
    .filter((id) => {
      const lower = id.toLowerCase();
      return lower.includes('sku') || lower.includes('product') || lower.includes('inventory');
    })
    .slice(0, 3);
}

export function getMartDrillAdvisory(params: {
  xField: string | null | undefined;
  martId: string | null | undefined;
  availableMarts: AvailableMart[];
  availableColumnNames?: string[];
}): string | null {
  const xField = params.xField?.toLowerCase() ?? '';
  if (!xField.includes('store')) return null;

  const columns = params.availableColumnNames ?? [];
  const martId = params.martId ?? '';
  const martLower = martId.toLowerCase();

  const hasProductColumns = columns.length > 0 && hasProductLikeField(columns);
  const martLikelyHasProduct =
    martLower.includes('product') || martLower.includes('sku') || martLower.includes('inventory');

  if (hasProductColumns || martLikelyHasProduct) {
    return null;
  }

  const suggested = suggestProductDrillMarts(params.availableMarts);
  if (suggested.length === 0) {
    return 'This mart does not expose product-level fields for drilldown.';
  }
  return `This mart does not expose product-level fields for drilldown. Try: ${suggested.join(', ')}.`;
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
