import { STATUS_ORDER } from '../../components/progress-dashboard/status-segments.js';

export const STATUS_FILTER_ALL = 'all';

export interface Municipality {
  jurisdiction_ocdid: string;
  name: string;
  status: string;
  officials_count: number;
  last_collected_at: string | null;
  needs_review: boolean;
}

export interface MunicipalityFilter {
  query: string;
  status: string;
  needsReviewOnly: boolean;
}

export type SortKey = 'name' | 'status' | 'officials' | 'last_collected';
export type SortDir = 'asc' | 'desc';

export interface MunicipalitySort {
  key: SortKey;
  dir: SortDir;
}

export function filterMunicipalities(
  municipalities: Municipality[],
  { query, status, needsReviewOnly }: MunicipalityFilter,
): Municipality[] {
  const q = query.trim().toLowerCase();
  return municipalities.filter((m) => {
    if (q && !m.name.toLowerCase().includes(q)) return false;
    if (status !== STATUS_FILTER_ALL && m.status !== status) return false;
    if (needsReviewOnly && !m.needs_review) return false;
    return true;
  });
}

function compareValues(a: string | number, b: string | number): number {
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  return String(a).localeCompare(String(b));
}

export function sortMunicipalities(
  municipalities: Municipality[],
  { key, dir }: MunicipalitySort,
): Municipality[] {
  const factor = dir === 'desc' ? -1 : 1;
  return [...municipalities].sort((a, b) => {
    const valueFor = (m: Municipality): string | number => {
      if (key === 'name') return m.name;
      if (key === 'status') return m.status;
      if (key === 'officials') return m.officials_count;
      return m.last_collected_at ?? '';
    };
    return compareValues(valueFor(a), valueFor(b)) * factor;
  });
}

export function computeStatusPillCounts(
  municipalities: Municipality[],
): Record<'all' | (typeof STATUS_ORDER)[number], number> {
  const counts: Record<string, number> = { all: municipalities.length };
  for (const key of STATUS_ORDER) counts[key] = 0;
  for (const m of municipalities) {
    if (m.status in counts) counts[m.status] += 1;
  }
  return counts as Record<'all' | (typeof STATUS_ORDER)[number], number>;
}

export function countNeedsReview(municipalities: Municipality[]): number {
  return municipalities.filter((m) => m.needs_review).length;
}
