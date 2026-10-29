import { html } from "lit-html";
import { component, useState } from "haunted";
import {
  fetchRosterComparison,
  fetchRosterComparisonJurisdiction,
  fetchRosterComparisonJurisdictions,
  fetchRosterComparisonPeople,
} from "../../api-roster-comparisons.js";
import { useAsyncData } from "../../hooks/use-async-data.js";
import { formatDateTime } from "../../utils/date-utils.js";
import { fieldList } from "./field-list.js";
import { jurisdictionsPanel } from "./jurisdictions.js";
import { organizationsPanel } from "./organizations.js";
import { outcomeList } from "./outcome-list.js";
import { fieldsPanel, peoplePanel } from "./summary.js";
import {
  isOutcomeSelection,
  isSameSelection,
  type PeopleSelection,
  type PersonComparison,
  type RosterComparisonRun,
  type RunJurisdiction,
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
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Record<string, PersonComparison[] | typeof LOADING>>({});
  const [selection, setSelection] = useState<PeopleSelection | null>(null);
  const [peoplePage, setPeoplePage] = useState<RunPeoplePage | null>(null);
  // null leaves the choice to the server until a box is ticked.
  const [compared, setCompared] = useState<string[] | null>(null);
  // The selection the counts are for: unticking every box hides them instead of asking for none.
  const [counted, setCounted] = useState<string[] | null>(null);
  const { data: summary, error: summaryError } = useAsyncData(
    () => fetchRosterComparison(runId, counted),
    [runId, counted],
  );
  const nothingTicked = compared !== null && !compared.length;
  const [notCompared, setNotCompared] = useState<RunJurisdiction[] | typeof LOADING | null>(null);

  const handleNotComparedToggle = async (e: Event) => {
    if (!(e.target as HTMLDetailsElement).open || notCompared !== null) return;
    setNotCompared(LOADING);
    try {
      setNotCompared(await fetchRosterComparisonJurisdictions(runId, false));
    } catch (e) {
      setError(String(e));
    }
  };

  const loadPeoplePage = async (next: PeopleSelection, page: number, organizations = compared) => {
    setPeoplePage(null);
    try {
      setPeoplePage(await fetchRosterComparisonPeople(runId, next, organizations, page, PEOPLE_PAGE_SIZE));
    } catch (e) {
      setError(String(e));
    }
  };

  const handleCompare = (next: string[]) => {
    setCompared(next);
    setOpen({});
    if (!next.length) return;
    setCounted(next);
    if (selection) loadPeoplePage(selection, 1, next);
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
      const people = await fetchRosterComparisonJurisdiction(runId, ocdid, compared);
      setOpen((current) => ({ ...current, [ocdid]: people }));
    } catch (e) {
      setError(String(e));
    }
  };

  const shownError = error ?? summaryError;
  if (shownError) return html`<main class="page-content rc-page"><p class="rc-error">${shownError}</p></main>`;
  if (!summary) return html`<main class="page-content rc-page"><p class="rc-note">Loading…</p></main>`;
  const { run } = summary;
  const comparisonPanels = nothingTicked
    ? null
    : html`${peoplePanel(run, selection, handleSelect)}
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
        })}`;

  return html`<main class="page-content rc-page">
    <div class="page-focal">
      <h1 class="page-focal__title">${run.state.toUpperCase()} roster comparison</h1>
    </div>
    <p class="rc-meta">${metaLine(run, summary.jurisdictions.length)}</p>
    ${notComparedLine(run.jurisdictions_not_named, notCompared, handleNotComparedToggle)}
    ${organizationsPanel({
      organizations: summary.organizations,
      compared: compared ?? summary.compared_organizations,
      onChange: handleCompare,
    })}
    ${comparisonPanels}
    ${correctionsPanel(run)}
  </main>`;
}

function metaLine(run: RosterComparisonRun, jurisdictionCount: number): string {
  return [
    `Run of ${formatDateTime(run.started_at)}`,
    `${count(jurisdictionCount, "jurisdiction")} in the uploaded data`,
  ].join(". ") + ".";
}

/** Closed until asked: the names load when it is opened. */
function notComparedLine(
  total: number,
  notCompared: RunJurisdiction[] | typeof LOADING | null,
  onToggle: (e: Event) => void,
) {
  const summary = `${count(total, "civicpatch jurisdiction")} in this state not in it, and not compared`;
  if (!total) return html`<p class="rc-meta">${summary}.</p>`;
  return html`<details class="rc-meta rc-not-compared" @toggle=${onToggle}>
    <summary>${summary}</summary>
    ${Array.isArray(notCompared)
      ? html`<ul class="rc-not-compared__list">
          ${notCompared.map(
            (jurisdiction) => html`<li><a href=${jurisdictionPageUrl(jurisdiction.jurisdiction_ocdid)}>${jurisdiction.name}</a></li>`,
          )}
        </ul>`
      : html`<p class="rc-note">Loading…</p>`}
  </details>`;
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
