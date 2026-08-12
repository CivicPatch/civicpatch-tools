import { html } from "lit-html";
import { component, useEffect, useState } from "haunted";
import { fetchDashboard, fetchMunicipalityList } from "../../api.js";
import { dateStringToFriendly } from "../../utils/date-utils.js";
import {
  STATUS_FILTER_ALL,
  filterMunicipalities,
  sortMunicipalities,
  computeStatusPillCounts,
  countNeedsReview,
  Municipality,
  SortKey,
  SortDir,
} from "./municipalities-filter.js";
import { renderControls } from "./controls.js";
import { renderMunicipalitiesTable } from "./table.js";
import { paginate } from "./pagination.js";
import { renderPaginationControls } from "./pagination-controls.js";
import {
  parseMunicipalitiesParams,
  buildMunicipalitiesSearch,
} from "./url-params.js";
import "./municipalities-page.css";

// Large enough that even the biggest tracked state (MI, ~1,773 municipalities)
// is only ~18 pages — small enough to list every page number, no ellipsis needed.
const PAGE_SIZE = 100;

interface MunicipalitiesPageProps {
  state?: string;
}

function MunicipalitiesPage({ state = "" }: MunicipalitiesPageProps) {
  const [municipalities, setMunicipalities] = useState<Municipality[] | null>(
    null,
  );
  const [cutoff, setCutoff] = useState<string | null>(null);

  const initial = parseMunicipalitiesParams(window.location.search);
  const [query, setQuery] = useState(initial.q);
  const [status, setStatus] = useState<string>(initial.status);
  const [needsReviewOnly, setNeedsReviewOnly] = useState(initial.needsReview);
  const [sortKey, setSortKey] = useState<SortKey>(initial.sortKey);
  const [sortDir, setSortDir] = useState<SortDir>(initial.sortDir);
  const [page, setPage] = useState(initial.page);

  // One-shot per-state fetch (§8) — search/filter/sort/pagination below all
  // operate on this same in-memory list, no per-interaction network round-trip.
  useEffect(() => {
    if (!state) return;
    fetchMunicipalityList(state)
      .then((d) => setMunicipalities(d.data ?? []))
      .catch(() => setMunicipalities([]));
    fetchDashboard()
      .then((d) =>
        setCutoff(d.data?.states?.[state]?.civicpatch?.cutoff ?? null),
      )
      .catch(() => {});
  }, [state]);

  // Keep the URL in sync with view state (§8.5). replaceState, not pushState —
  // filter/sort/page changes shouldn't spam browser history one entry per click.
  useEffect(() => {
    const search = buildMunicipalitiesSearch({
      q: query,
      status,
      needsReview: needsReviewOnly,
      sortKey,
      sortDir,
      page,
    });
    window.history.replaceState({}, "", `${window.location.pathname}${search}`);
  }, [query, status, needsReviewOnly, sortKey, sortDir, page]);

  // Any filter/sort change resets to page 1 — staying on e.g. page 5 after a
  // filter narrows the results to 2 pages would show an empty/confusing page.
  const withPageReset = (fn: () => void) => {
    fn();
    setPage(1);
  };

  const handleQueryChange = (value: string) =>
    withPageReset(() => setQuery(value));
  const handleStatusChange = (value: string) =>
    withPageReset(() => setStatus(value));
  const handleNeedsReviewToggle = () =>
    withPageReset(() => setNeedsReviewOnly(!needsReviewOnly));
  const handleSortChange = (key: SortKey) =>
    withPageReset(() => {
      if (key === sortKey) {
        setSortDir(sortDir === "asc" ? "desc" : "asc");
      } else {
        setSortKey(key);
        setSortDir("asc");
      }
    });
  const handleClearFilters = () =>
    withPageReset(() => {
      setQuery("");
      setStatus(STATUS_FILTER_ALL);
      setNeedsReviewOnly(false);
    });

  const stateLabel = state.toUpperCase();
  const all = municipalities ?? [];
  const filtered = filterMunicipalities(all, {
    query,
    status,
    needsReviewOnly,
  });
  const sorted = sortMunicipalities(filtered, { key: sortKey, dir: sortDir });
  const pageInfo = paginate(sorted, page, PAGE_SIZE);

  // Each pill/toggle's count reflects every filter dimension EXCEPT itself, so it
  // shows what selecting it *would* produce — not the fully-filtered result, which
  // would collapse every inactive pill to zero.
  const statusPillCounts = computeStatusPillCounts(
    filterMunicipalities(all, {
      query,
      status: STATUS_FILTER_ALL,
      needsReviewOnly,
    }),
  );
  const needsReviewCount = countNeedsReview(
    filterMunicipalities(all, { query, status, needsReviewOnly: false }),
  );

  const isUnfiltered =
    !query && status === STATUS_FILTER_ALL && !needsReviewOnly;

  return html`
    <main class="municipalities-page page-content">
      <div class="municipalities-page__title-row">
        <div>
          <h1 class="municipalities-page__h1">${stateLabel} municipalities</h1>
        </div>
        ${cutoff
          ? html`<p class="municipalities-page__cutoff">
              Fresh = scraped after ${dateStringToFriendly(cutoff)}
            </p>`
          : ""}
      </div>
      <hr class="municipalities-page__hairline" />

      ${municipalities === null
        ? html`<p>Loading…</p>`
        : html`
            ${renderControls({
              query,
              onQueryChange: handleQueryChange,
              status,
              onStatusChange: handleStatusChange,
              statusPillCounts,
              needsReviewOnly,
              onNeedsReviewToggle: handleNeedsReviewToggle,
              needsReviewCount,
            })}

            <p class="municipalities-page__count">
              ${isUnfiltered
                ? `${sorted.length} municipalities`
                : `Showing ${sorted.length} of ${all.length} municipalities`}
            </p>

            ${renderMunicipalitiesTable({
              municipalities: pageInfo.pageItems,
              onClearFilters: handleClearFilters,
              sortKey,
              sortDir,
              onSortChange: handleSortChange,
            })}
            ${renderPaginationControls({
              page,
              pageInfo,
              onPageChange: setPage,
            })}
          `}
    </main>
  `;
}

customElements.define(
  "municipalities-page",
  component(MunicipalitiesPage as any, {
    useShadowDOM: false,
    observedAttributes: ["state"],
  }),
);
