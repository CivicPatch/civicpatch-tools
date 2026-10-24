import { html } from "lit-html";
import { component, useEffect, useState } from "haunted";
import {
  fetchRosterComparison,
  fetchRosterComparisonJurisdiction,
  fetchRosterComparisonPeople,
} from "../../api-roster-comparisons.js";
import { formatDateTime } from "../../utils/date-utils.js";
import { fieldList } from "./field-list.js";
import { jurisdictionsPanel } from "./jurisdictions.js";
import { outcomeList } from "./outcome-list.js";
import { fieldsPanel, peoplePanel } from "./summary.js";
import {
  isOutcomeSelection,
  isSameSelection,
  type PeopleSelection,
  type PersonComparison,
  type RosterComparisonRun,
  type RosterComparisonSummary,
  type RunPeoplePage,
} from "./types.js";
import "../../components/panel/panel.css";
import "./roster-comparison-page.css";

const PEOPLE_PAGE_SIZE = 50;
const LOADING = "loading";

const jurisdictionPageUrl = (ocdid: string) => `/${ocdid}`;

interface RosterComparisonPageProps {
  run_id: string;
}

function RosterComparisonPage({ run_id: runId }: RosterComparisonPageProps) {
  const [summary, setSummary] = useState<RosterComparisonSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Record<string, PersonComparison[] | typeof LOADING>>({});
  const [selection, setSelection] = useState<PeopleSelection | null>(null);
  const [peoplePage, setPeoplePage] = useState<RunPeoplePage | null>(null);

  useEffect(() => {
    fetchRosterComparison(runId).then(setSummary, (e) => setError(String(e)));
  }, [runId]);

  const loadPeoplePage = async (next: PeopleSelection, page: number) => {
    setPeoplePage(null);
    try {
      setPeoplePage(await fetchRosterComparisonPeople(runId, next, page, PEOPLE_PAGE_SIZE));
    } catch (e) {
      setError(String(e));
    }
  };

  const handleSelect = (next: PeopleSelection) => {
    const same = isSameSelection(selection, next);
    setSelection(same ? null : next);
    if (!same) loadPeoplePage(next, 1);
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
    ${peoplePanel(run, selection, handleSelect)}
    ${selection && isOutcomeSelection(selection)
      ? outcomeList({
          selection,
          page: peoplePage,
          pageUrl: jurisdictionPageUrl,
          onPage: (page) => loadPeoplePage(selection, page),
        })
      : null}
    ${fieldsPanel(run, selection, handleSelect)}
    ${selection && !isOutcomeSelection(selection)
      ? fieldList({
          selection,
          page: peoplePage,
          pageUrl: jurisdictionPageUrl,
          onPage: (page) => loadPeoplePage(selection, page),
        })
      : null}
    ${jurisdictionsPanel({
      jurisdictions: summary.jurisdictions,
      open,
      pageUrl: jurisdictionPageUrl,
      onToggle: handleToggle,
    })}
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
