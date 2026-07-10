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

// At PAGE_SIZE=100, even the largest tracked state (MI, ~1,773 municipalities)
// is only ~18 pages — small enough to render every page number directly, no
// windowing/ellipsis needed.
export function pageNumbers(totalPages: number): number[] {
  return Array.from({ length: totalPages }, (_, i) => i + 1);
}
