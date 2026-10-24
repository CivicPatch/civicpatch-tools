import { html } from "lit-html";
import { component, useEffect, useState } from "haunted";
import { fetchRosterComparisons } from "../../api-roster-comparisons.js";
import { Pagination } from "../../components/pagination/index.js";
import { SectionNav, manageSection } from "../../components/section-nav/index.js";
import { useAuth } from "../../hooks/useAuth.js";
import { formatDateTime } from "../../utils/date-utils.js";
import { percent } from "../roster-comparison-page/labels.js";
import { outcomeBar } from "../roster-comparison-page/summary.js";
import { OUTCOMES, type RosterComparisonListItem, type RosterComparisonListPage } from "../roster-comparison-page/types.js";
import "../../components/panel/panel.css";
import "../roster-comparison-page/roster-comparison-page.css";

const PER_PAGE = 20;
const PAGE_PATH = "/roster-comparisons";

function runRow(run: RosterComparisonListItem) {
  const outcomes = run.rates.outcomes;
  const people = OUTCOMES.reduce((sum, outcome) => sum + outcomes[outcome], 0);
  return html`<tr>
    <td>${run.state.toUpperCase()}</td>
    <td><a href=${run.page_url}>${formatDateTime(run.started_at)}</a></td>
    <td><a href=${`/~${run.started_by}`}>${run.started_by}</a></td>
    <td class="rc-number">${run.jurisdictions_named}</td>
    <td>${outcomeBar(outcomes, run.state.toUpperCase(), true)}</td>
    <td class="rc-number">${percent(outcomes.matched, people)}</td>
    <td><a class="btn btn-sm" href=${run.page_url}>Open</a></td>
  </tr>`;
}

function runsTable(page: RosterComparisonListPage, onPage: (page: number) => void) {
  if (!page.data.length) {
    return html`<p class="rc-note">No comparisons yet. An agent starts one by uploading a roster; see "Connect your agent" on Settings → API keys.</p>`;
  }
  return html`<div class="rc-scroll">
      <table class="rc-table rc-table--runs">
        <thead>
          <tr>
            <th>State</th>
            <th>Run</th>
            <th>By</th>
            <th class="rc-number">Jurisdictions</th>
            <th>People</th>
            <th class="rc-number">Matched</th>
            <th></th>
          </tr>
        </thead>
        <tbody>${page.data.map(runRow)}</tbody>
      </table>
    </div>
    ${Pagination({
      page: page.page,
      totalPages: page.total_pages,
      onPrevious: () => onPage(page.page - 1),
      onNext: () => onPage(page.page + 1),
    })}`;
}

function RosterComparisonsPage() {
  const { permissions } = useAuth();
  const [page, setPage] = useState<RosterComparisonListPage | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = (pageNumber: number) =>
    fetchRosterComparisons(pageNumber, PER_PAGE).then(setPage, (e) => setError(String(e)));

  useEffect(() => {
    load(1);
  }, []);

  return html`<main class="page-content rc-page">
    <div class="page-focal">
      <h1 class="page-focal__title">Roster comparisons</h1>
    </div>
    <div class="sectioned">
      ${SectionNav("manage", manageSection(permissions), PAGE_PATH)}
      <div class="secbody">
        <section class="panel">
          <div class="panel__cap"><b>runs</b><span class="panel__cap-right">newest first</span></div>
          ${error ? html`<p class="rc-error">${error}</p>` : null}
          ${page ? runsTable(page, load) : html`<p class="rc-note">Loading…</p>`}
        </section>
      </div>
    </div>
  </main>`;
}

customElements.define("roster-comparisons-page", component(RosterComparisonsPage as any, { useShadowDOM: false }));
