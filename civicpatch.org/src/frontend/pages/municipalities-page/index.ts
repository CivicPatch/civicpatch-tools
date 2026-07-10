import { html } from 'lit-html';
import { component, useEffect, useState } from 'haunted';
import { fetchDashboard, fetchMunicipalityList } from '../../api.js';
import { dateStringToFriendly } from '../../utils/date-utils.js';
import { jurisdictionOcdidToPath } from '../../components/ocdid-utils.js';
import {
  STATUS_FILTER_ALL,
  filterMunicipalities,
  sortMunicipalities,
  computeStatusPillCounts,
  countNeedsReview,
  Municipality,
  SortKey,
  SortDir,
} from './municipalities-filter.js';
import { renderControls } from './controls.js';
import './municipalities-page.css';

interface MunicipalitiesPageProps {
  state?: string;
}

function MunicipalitiesPage({ state = '' }: MunicipalitiesPageProps) {
  const [municipalities, setMunicipalities] = useState<Municipality[] | null>(null);
  const [cutoff, setCutoff] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<string>(STATUS_FILTER_ALL);
  const [needsReviewOnly, setNeedsReviewOnly] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  // One-shot per-state fetch (§8) — search/filter/sort below all operate on this
  // same in-memory list, no per-interaction network round-trip.
  useEffect(() => {
    if (!state) return;
    fetchMunicipalityList(state)
      .then((d) => setMunicipalities(d.data ?? []))
      .catch(() => setMunicipalities([]));
    fetchDashboard()
      .then((d) => setCutoff(d.data?.states?.[state]?.civicpatch?.cutoff ?? null))
      .catch(() => {});
  }, [state]);

  const handleSortChange = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const stateLabel = state.toUpperCase();
  const all = municipalities ?? [];
  const filtered = filterMunicipalities(all, { query, status, needsReviewOnly });
  const sorted = sortMunicipalities(filtered, { key: sortKey, dir: sortDir });

  // Each pill/toggle's count reflects every filter dimension EXCEPT itself, so it
  // shows what selecting it *would* produce — not the fully-filtered result, which
  // would collapse every inactive pill to zero.
  const statusPillCounts = computeStatusPillCounts(
    filterMunicipalities(all, { query, status: STATUS_FILTER_ALL, needsReviewOnly }),
  );
  const needsReviewCount = countNeedsReview(
    filterMunicipalities(all, { query, status, needsReviewOnly: false }),
  );

  const isUnfiltered = !query && status === STATUS_FILTER_ALL && !needsReviewOnly;

  return html`
    <div class="municipalities-page">
      <div class="municipalities-page__header">
        <a class="municipalities-page__breadcrumb" href="/">← Map</a>
        <span class="municipalities-page__breadcrumb-sep">/</span>
        <span class="municipalities-page__breadcrumb">${stateLabel}</span>
        <span class="municipalities-page__breadcrumb-sep">/</span>
        <span class="municipalities-page__breadcrumb">Local</span>
      </div>
      <div class="municipalities-page__title-row">
        <div>
          <p class="municipalities-page__eyebrow">CIVIC DATA — ${stateLabel}</p>
          <h1 class="municipalities-page__h1">${stateLabel} municipalities</h1>
        </div>
        ${cutoff
          ? html`<p class="municipalities-page__cutoff">
              Data fresh after ${dateStringToFriendly(cutoff)}
            </p>`
          : ''}
      </div>
      <hr class="municipalities-page__hairline" />

      ${municipalities === null
        ? html`<p>Loading…</p>`
        : html`
            ${renderControls({
              query,
              onQueryChange: setQuery,
              status,
              onStatusChange: setStatus,
              statusPillCounts,
              needsReviewOnly,
              onNeedsReviewToggle: () => setNeedsReviewOnly(!needsReviewOnly),
              needsReviewCount,
              sortKey,
              sortDir,
              onSortChange: handleSortChange,
            })}

            <p class="municipalities-page__count">
              ${isUnfiltered
                ? `${sorted.length} municipalities`
                : `Showing ${sorted.length} of ${all.length} municipalities`}
            </p>
            <ul class="municipalities-page__list">
              ${sorted.map(
                (m) => html`<li>
                  <a href="/${jurisdictionOcdidToPath(m.jurisdiction_ocdid)}">${m.name}</a>
                </li>`,
              )}
            </ul>
          `}
    </div>
  `;
}

customElements.define(
  'municipalities-page',
  component(MunicipalitiesPage as any, {
    useShadowDOM: false,
    observedAttributes: ['state'],
  }),
);
