import { html } from "lit-html";
import { Pagination } from "../../components/pagination/index.js";
import { FIELD_LABELS } from "./labels.js";
import { placeName } from "./jurisdictions.js";
import { civicpatchChips, rowRef, uploadedChips, valueLegend } from "./values.js";
import { FIELD_FILTER_CONFLICT, type FieldPage } from "./types.js";
import type { FieldSelection } from "./summary.js";

export interface FieldListView {
  selection: FieldSelection;
  page: FieldPage | null;
  pageUrl: (jurisdictionOcdid: string) => string;
  onPage: (page: number) => void;
}

export function fieldList(view: FieldListView) {
  const { selection, page } = view;
  const title = `${FIELD_LABELS[selection.field]}: ${selection.filter === FIELD_FILTER_CONFLICT ? "conflict" : "one side has more"}`;
  if (!page) return html`<div class="rc-field-list"><h3>${title}</h3><p class="rc-note">Loading…</p></div>`;
  return html`<div class="rc-field-list">
    <h3>${title}</h3>
    ${valueLegend()}
    <div class="rc-scroll">
      <table class="rc-table rc-table--wide">
        <thead>
          <tr><th>Jurisdiction</th><th>Uploaded data</th><th>civicpatch</th><th>Uploaded value</th><th>civicpatch value</th></tr>
        </thead>
        <tbody>
          ${page.data.map(({ jurisdiction_ocdid, person }) => {
            const comparison = person.fields[selection.field];
            return html`<tr>
              <td><a href=${view.pageUrl(jurisdiction_ocdid)}>${placeName(jurisdiction_ocdid)}</a></td>
              <td>${person.uploaded ? html`${person.uploaded.name}${rowRef(person.uploaded)}` : null}</td>
              <td><a href=${view.pageUrl(jurisdiction_ocdid)}>${person.person_name}</a></td>
              <td>${comparison ? uploadedChips(comparison) : null}</td>
              <td>${comparison ? civicpatchChips(comparison) : null}</td>
            </tr>`;
          })}
        </tbody>
      </table>
    </div>
    ${Pagination({
      page: page.page,
      totalPages: page.total_pages,
      onPrevious: () => view.onPage(page.page - 1),
      onNext: () => view.onPage(page.page + 1),
    })}
  </div>`;
}
