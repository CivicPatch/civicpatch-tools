import { html } from "lit-html";
import { peoplePager } from "./field-list.js";
import { civicpatchSide, fieldCells, placeName, uploadedSide } from "./jurisdictions.js";
import { OUTCOME_LABELS } from "./labels.js";
import type { OutcomeSelection, RunPeoplePage } from "./types.js";

export interface OutcomeListView {
  selection: OutcomeSelection;
  page: RunPeoplePage | null;
  pageUrl: (jurisdictionOcdid: string) => string;
  onPage: (page: number) => void;
}

export function outcomeList(view: OutcomeListView) {
  const { selection, page } = view;
  const title = `${OUTCOME_LABELS[selection.outcome]}, across the state`;
  if (!page) return html`<div class="rc-field-list"><h3>${title}</h3><p class="rc-note">Loading…</p></div>`;
  return html`<div class="rc-field-list">
    <h3>${title}</h3>
    <div class="rc-scroll">
      <table class="rc-table rc-table--wide">
        <thead>
          <tr><th>Jurisdiction</th><th>Uploaded data</th><th>civicpatch</th><th>Role</th><th>Emails</th><th>Phones</th></tr>
        </thead>
        <tbody>
          ${page.data.map(
            ({ jurisdiction_ocdid, person }) => html`<tr>
              <td><a href=${view.pageUrl(jurisdiction_ocdid)}>${placeName(jurisdiction_ocdid)}</a></td>
              <td>${uploadedSide(person)}</td>
              <td>${civicpatchSide(person, view.pageUrl(jurisdiction_ocdid))}</td>
              ${fieldCells(person)}
            </tr>`,
          )}
        </tbody>
      </table>
    </div>
    ${peoplePager(page, view.onPage)}
  </div>`;
}
