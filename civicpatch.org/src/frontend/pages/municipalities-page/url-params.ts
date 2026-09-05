import { STATUS_ORDER } from '../../components/progress-dashboard/status-segments.js';
import { STATUS_FILTER_ALL, SortDir, SortKey } from './municipalities-filter.js';

export interface MunicipalitiesUrlParams {
  q: string;
  status: string;
  needsReview: boolean;
  sortKey: SortKey;
  sortDir: SortDir;
  page: number;
}

const DEFAULTS: MunicipalitiesUrlParams = {
  q: '',
  status: STATUS_FILTER_ALL,
  needsReview: false,
  sortKey: 'name',
  sortDir: 'asc',
  page: 1,
};

const VALID_STATUSES = new Set<string>([STATUS_FILTER_ALL, ...STATUS_ORDER]);
const VALID_SORT_KEYS = new Set<string>(['name', 'status', 'officials', 'last_collected']);

export function parseMunicipalitiesParams(search: string): MunicipalitiesUrlParams {
  const params = new URLSearchParams(search);
  const status = params.get('status');
  const sortKey = params.get('sort');
  const page = parseInt(params.get('page') ?? '', 10);

  return {
    q: params.get('q') ?? DEFAULTS.q,
    status: status && VALID_STATUSES.has(status) ? status : DEFAULTS.status,
    needsReview: params.get('needs_review') === 'true',
    sortKey: sortKey && VALID_SORT_KEYS.has(sortKey) ? (sortKey as SortKey) : DEFAULTS.sortKey,
    sortDir: params.get('dir') === 'desc' ? 'desc' : DEFAULTS.sortDir,
    page: Number.isFinite(page) && page > 0 ? page : DEFAULTS.page,
  };
}

export function buildMunicipalitiesSearch(params: MunicipalitiesUrlParams): string {
  const usp = new URLSearchParams();
  if (params.q) usp.set('q', params.q);
  if (params.status !== DEFAULTS.status) usp.set('status', params.status);
  if (params.needsReview) usp.set('needs_review', 'true');
  if (params.sortKey !== DEFAULTS.sortKey) usp.set('sort', params.sortKey);
  if (params.sortDir !== DEFAULTS.sortDir) usp.set('dir', params.sortDir);
  if (params.page !== DEFAULTS.page) usp.set('page', String(params.page));
  const serialized = usp.toString();
  return serialized ? `?${serialized}` : '';
}
