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
import { municipalitiesUrl, countiesUrl } from "./municipalities-routes.js";
import { SectionNav, type SectionNavItem } from "../../components/section-nav/index.js";
import { stateNameForCode } from "../../components/ocdid-utils.js";
import "../../components/panel/panel.css";
import "./municipalities-page.css";

// Large enough that even the biggest tracked state (MI, ~1,773 municipalities)
// is only ~18 pages — small enough to list every page number, no ellipsis needed.
const PAGE_SIZE = 100;

const COUNTIES_LEVEL = "counties";

interface MunicipalitiesPageProps {
  state?: string;
  level?: string;
}

function MunicipalitiesPage({ state = "", level = "local" }: MunicipalitiesPageProps) {
  const isCounties = level === COUNTIES_LEVEL;
  const sectionLabel = isCounties ? "counties" : "municipalities";
  // Municipalities first — it's the bare state URL, the default section a browse
  // link lands on.
  const sections: SectionNavItem[] = [
    { label: "Municipalities", href: municipalitiesUrl(state) },
    { label: "Counties", href: countiesUrl(state) },
  ];
  const currentPath = isCounties ? countiesUrl(state) : municipalitiesUrl(state);

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
    fetchMunicipalityList(state, level)
      .then((d) => setMunicipalities(d.data ?? []))
      .catch(() => setMunicipalities([]));
    fetchDashboard()
      .then((d) =>
        setCutoff(d.data?.states?.[state]?.civicpatch?.cutoff ?? null),
      )
      .catch(() => {});
  }, [state, level]);

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

  const stateLabel = stateNameForCode(state) || state.toUpperCase();
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
      <div class="page-focal">
        <h1 class="page-focal__title">${stateLabel} ${sectionLabel}</h1>
        ${cutoff
          ? html`<p class="page-focal__end municipalities-page__cutoff">
              Fresh = scraped after ${dateStringToFriendly(cutoff)}
            </p>`
          : ""}
      </div>

      <div class="sectioned">
        ${SectionNav(sectionLabel, sections, currentPath)}
        <div class="secbody">
          ${municipalities === null
            ? html`<p>Loading…</p>`
            : html`
                <section class="panel municipalities-page__panel">
                  <div class="panel__cap">
                    <b>${sectionLabel}</b>
                    <span class="panel__cap-right">
                      ${isUnfiltered
                        ? `${sorted.length}`
                        : `${sorted.length} of ${all.length}`}
                    </span>
                  </div>

                  ${renderControls({
                    query,
                    onQueryChange: handleQueryChange,
                    status,
                    onStatusChange: handleStatusChange,
                    statusPillCounts,
                    needsReviewOnly,
                    onNeedsReviewToggle: handleNeedsReviewToggle,
                    needsReviewCount,
                    sectionLabel,
                  })}

                  ${renderMunicipalitiesTable({
                    municipalities: pageInfo.pageItems,
                    sectionLabel,
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
                </section>
              `}
        </div>
      </div>
    </main>
  `;
}

customElements.define(
  "municipalities-page",
  component(MunicipalitiesPage as any, {
    useShadowDOM: false,
    observedAttributes: ["state", "level"],
  }),
);
