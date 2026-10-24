import { html } from "lit-html";
import { CANDIDATE_REASON_LABELS, OUTCOME_LABELS } from "./labels.js";
import { outcomeBar } from "./summary.js";
import { fieldValues, rowRef, warningIcon, warningList } from "./values.js";
import type { JurisdictionRates, PersonComparison } from "./types.js";

export interface JurisdictionsView {
  jurisdictions: JurisdictionRates[];
  open: Record<string, PersonComparison[] | "loading">;
  pageUrl: (jurisdictionOcdid: string) => string;
  onToggle: (jurisdictionOcdid: string) => void;
}

const COLUMNS = 6;

export function jurisdictionsPanel(view: JurisdictionsView) {
  return html`<section class="panel">
    <div class="panel__cap">
      <b>jurisdictions</b><span class="panel__cap-right">most unmatched first</span>
    </div>
    <p class="rc-note">A jurisdiction's name opens its civicpatch page; the rest of the row shows its people here.</p>
    <div class="rc-scroll">
      <table class="rc-table rc-table--wide">
        <thead>
          <tr>
            <th>Jurisdiction</th>
            <th>People</th>
            <th class="rc-number">Matched</th>
            <th class="rc-number">Possible</th>
            <th class="rc-number">Only in uploaded data</th>
            <th class="rc-number">Only in civicpatch</th>
          </tr>
        </thead>
        <tbody>
          ${view.jurisdictions.map((jurisdiction) => jurisdictionRows(jurisdiction, view))}
        </tbody>
      </table>
    </div>
  </section>`;
}

function jurisdictionRows(jurisdiction: JurisdictionRates, view: JurisdictionsView) {
  const ocdid = jurisdiction.jurisdiction_ocdid;
  const outcomes = jurisdiction.rates.outcomes;
  const people = view.open[ocdid];
  const toggle = () => view.onToggle(ocdid);
  const onKey = (e: KeyboardEvent) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    toggle();
  };
  return html`
    <tr
      class="rc-jurisdiction"
      tabindex="0"
      aria-expanded=${people ? "true" : "false"}
      @click=${toggle}
      @keydown=${onKey}
    >
      <td>
        <a href=${view.pageUrl(ocdid)} @click=${(e: Event) => e.stopPropagation()}>${placeName(ocdid)}</a>
        ${jurisdiction.rates.rows_with_warnings
          ? html`<span class="rc-warning-count">${warningIcon} ${jurisdiction.rates.rows_with_warnings}</span>`
          : null}
      </td>
      <td>${outcomeBar(outcomes, placeName(ocdid), true)}</td>
      <td class="rc-number">${outcomes.matched}</td>
      <td class="rc-number">${outcomes.possible_match}</td>
      <td class="rc-number">${outcomes.only_in_uploaded_data}</td>
      <td class="rc-number">${outcomes.only_in_civicpatch}</td>
    </tr>
    ${people
      ? html`<tr class="rc-jurisdiction-detail">
          <td colspan=${COLUMNS}>${people === "loading" ? html`<p class="rc-note">Loading…</p>` : peopleTable(people, view.pageUrl(ocdid))}</td>
        </tr>`
      : null}
  `;
}

function peopleTable(people: PersonComparison[], pageUrl: string) {
  return html`<div class="rc-scroll">
    <table class="rc-table rc-table--wide">
      <thead>
        <tr><th>Uploaded data</th><th>civicpatch</th><th>Outcome</th><th>Role</th><th>Emails</th><th>Phones</th></tr>
      </thead>
      <tbody>
        ${people.map(
          (person) => html`<tr>
            <td>${uploadedSide(person)}</td>
            <td>${civicpatchSide(person, pageUrl)}</td>
            <td>${OUTCOME_LABELS[person.outcome]}</td>
            ${fieldCells(person)}
          </tr>`,
        )}
      </tbody>
    </table>
  </div>`;
}

export function uploadedSide(person: PersonComparison) {
  return html`${person.uploaded
      ? html`${person.uploaded.name}${rowRef(person.uploaded)}`
      : html`<span class="rc-muted">not in uploaded data</span>`}
    ${warningList(person.warnings)}`;
}

export function fieldCells(person: PersonComparison) {
  return html`<td>${fieldValues(person.fields.role, person.post_roles)}</td>
    <td>${fieldValues(person.fields.emails, [])}</td>
    <td>${fieldValues(person.fields.phones, [])}</td>`;
}

export function civicpatchSide(person: PersonComparison, pageUrl: string) {
  if (person.person_name) return html`<a href=${pageUrl}>${person.person_name}</a>`;
  if (!person.candidates.length) return html`<span class="rc-muted">not in civicpatch</span>`;
  return person.candidates.map(
    (candidate) => html`<span class="rc-candidate"
      ><a href=${pageUrl}>${candidate.name}</a>
      <span class="rc-muted">(${CANDIDATE_REASON_LABELS[candidate.reason] ?? candidate.reason})</span></span
    >`,
  );
}

/** "place:barre" → "Barre"; the ocdid is the fallback when it has no place. */
export function placeName(ocdid: string): string {
  const match = ocdid.match(/\/(?:place|county):([^/]+)/);
  if (!match) return ocdid;
  return match[1].replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
