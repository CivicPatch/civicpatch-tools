import { html } from "lit-html";
import { component, useEffect, useState } from "haunted";
import {
  fetchRosterComparison,
  fetchRosterComparisonField,
  fetchRosterComparisonJurisdiction,
} from "../../api-roster-comparisons.js";
import { formatDateTime } from "../../utils/date-utils.js";
import { fieldList } from "./field-list.js";
import { jurisdictionsPanel, placeName } from "./jurisdictions.js";
import { fieldsPanel, peoplePanel, type FieldSelection } from "./summary.js";
import type { FieldPage, PersonComparison, RosterComparisonRun, RosterComparisonSummary } from "./types.js";
import "../../components/panel/panel.css";
import "./roster-comparison-page.css";

const FIELD_PAGE_SIZE = 50;
const LOADING = "loading";

const jurisdictionPageUrl = (ocdid: string) => `/${ocdid}`;

interface RosterComparisonPageProps {
  run_id: string;
}

function RosterComparisonPage({ run_id: runId }: RosterComparisonPageProps) {
  const [summary, setSummary] = useState<RosterComparisonSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Record<string, PersonComparison[] | typeof LOADING>>({});
  const [selection, setSelection] = useState<FieldSelection | null>(null);
  const [fieldPage, setFieldPage] = useState<FieldPage | null>(null);

  useEffect(() => {
    fetchRosterComparison(runId).then(setSummary, (e) => setError(String(e)));
  }, [runId]);

  const loadFieldPage = async (next: FieldSelection, page: number) => {
    setFieldPage(null);
    try {
      setFieldPage(await fetchRosterComparisonField(runId, next.field, next.filter, page, FIELD_PAGE_SIZE));
    } catch (e) {
      setError(String(e));
    }
  };

  const handleSelect = (next: FieldSelection) => {
    const same = selection?.field === next.field && selection.filter === next.filter;
    setSelection(same ? null : next);
    if (!same) loadFieldPage(next, 1);
  };

  const handleToggle = async (ocdid: string) => {
    if (open[ocdid]) {
      const { [ocdid]: _closed, ...rest } = open;
      setOpen(rest);
      return;
    }
    setOpen({ ...open, [ocdid]: LOADING });
    try {
      const people = await fetchRosterComparisonJurisdiction(runId, ocdid);
      setOpen((current) => ({ ...current, [ocdid]: people }));
    } catch (e) {
      setError(String(e));
    }
  };

  if (error) return html`<main class="page-content rc-page"><p class="rc-error">${error}</p></main>`;
  if (!summary) return html`<main class="page-content rc-page"><p class="rc-note">Loading…</p></main>`;
  const { run } = summary;

  return html`<main class="page-content rc-page">
    <div class="page-focal">
      <h1 class="page-focal__title">${run.state.toUpperCase()} roster comparison</h1>
    </div>
    <p class="rc-meta">${metaLine(run, summary.jurisdictions.length)}</p>
    ${peoplePanel(run)}
    ${fieldsPanel(run, selection, handleSelect)}
    ${selection
      ? fieldList({
          selection,
          page: fieldPage,
          pageUrl: jurisdictionPageUrl,
          onPage: (page) => loadFieldPage(selection, page),
        })
      : null}
    ${jurisdictionsPanel({
      jurisdictions: summary.jurisdictions,
      open,
      pageUrl: jurisdictionPageUrl,
      onToggle: handleToggle,
    })}
    ${rejectedPanel(run)}
    ${correctionsPanel(run)}
  </main>`;
}

function metaLine(run: RosterComparisonRun, jurisdictionCount: number): string {
  return [
    `Run of ${formatDateTime(run.started_at)}`,
    `${count(jurisdictionCount, "jurisdiction")} in the uploaded data`,
    `${count(run.jurisdictions_not_named, "civicpatch jurisdiction")} in this state not in it, and not compared`,
  ].join(". ") + ".";
}

function count(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}

function rejectedPanel(run: RosterComparisonRun) {
  if (!run.rejected.length) return null;
  return html`<section class="panel">
    <div class="panel__cap"><b>rows not compared</b><span class="panel__cap-right">${run.rejected.length}</span></div>
    <ul class="rc-list">
      ${run.rejected.map(
        (row) => html`<li>Row ${row.source_row}: ${placeName(row.jurisdiction_ocdid)}. ${row.reason}</li>`,
      )}
    </ul>
  </section>`;
}

function correctionsPanel(run: RosterComparisonRun) {
  return html`<section class="panel">
    <div class="panel__cap"><b>corrections, reported by the agent</b></div>
    ${run.corrections.length
      ? html`<ul class="rc-list">${run.corrections.map((line) => html`<li>${line}</li>`)}</ul>`
      : html`<p class="rc-note">The agent reported no corrections.</p>`}
    <p class="rc-note">civicpatch never sees the original file, so this list is the agent's own account.</p>
  </section>`;
}

customElements.define(
  "roster-comparison-page",
  component(RosterComparisonPage as any, { useShadowDOM: false, observedAttributes: ["run_id"] }),
);
export default RosterComparisonPage;
