export interface PageResult<T> {
  pageItems: T[];
  start: number;
  end: number;
  total: number;
  totalPages: number;
}

export function paginate<T>(items: T[], page: number, pageSize: number): PageResult<T> {
  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const clampedPage = Math.min(Math.max(1, page), totalPages);
  const startIndex = (clampedPage - 1) * pageSize;
  const pageItems = items.slice(startIndex, startIndex + pageSize);

  return {
    pageItems,
    start: pageItems.length === 0 ? 0 : startIndex + 1,
    end: pageItems.length === 0 ? 0 : startIndex + pageItems.length,
    total,
    totalPages,
  };
}

export type PageWindowItem = number | 'ellipsis';

function range(start: number, end: number): number[] {
  if (end < start) return [];
  return Array.from({ length: end - start + 1 }, (_, i) => start + i);
}

// Always show pages 1-2 and the last 2 pages, plus a small window around the
// current page — "1 2 … 8 9" rather than a plain sliding window, so it's always
// clear how far the current page is from either end (matters at ~89 pages, MI).
export function computePageWindow(page: number, totalPages: number): PageWindowItem[] {
  if (totalPages <= 7) return range(1, totalPages);

  const middleStart = Math.max(3, page - 1);
  const middleEnd = Math.min(totalPages - 2, page + 1);

  const items: PageWindowItem[] = [1, 2];
  if (middleStart > 3) items.push('ellipsis');
  items.push(...range(middleStart, middleEnd));
  if (middleEnd < totalPages - 2) items.push('ellipsis');
  items.push(totalPages - 1, totalPages);
  return items;
}
