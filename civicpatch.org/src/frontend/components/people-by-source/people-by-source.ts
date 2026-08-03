import "./people-by-source.css";
import { html } from "lit-html";
import { component } from "haunted";
import { baselineColumnLabel, sourceRowClass, type SourceRow } from "./source-model.js";

// Who the baseline had against who this scrape produced. Drawn in the review
// drawer and on the queue page's PR card — one component so the two cannot
// disagree about which direction is a gain.
type PeopleBySourceHost = HTMLElement & {
  rows: SourceRow[];
  originSource: string | null;
};

const checkmark = (value: boolean) =>
  value
    ? html`<i class="fa-solid fa-check" style="color: var(--pico-ins-color);"></i>`
    : html`<i class="fa-solid fa-xmark" style="color: var(--pico-del-color);"></i>`;

function PeopleBySource(host: PeopleBySourceHost) {
  const { rows = [], originSource } = host;

  if (!rows.length) {
    return html`<p class="people-by-source__empty">No source comparison for this card.</p>`;
  }

  return html`
    <table class="people-by-source" role="grid">
      <thead>
        <tr>
          <th>Name</th>
          <th>${baselineColumnLabel(originSource)}</th>
          <th>This scrape</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map(
          (row) => html`
            <tr class=${sourceRowClass(row)}>
              <td>${row.name}</td>
              <td>${checkmark(row.in_research)}</td>
              <td>${checkmark(row.in_data)}</td>
            </tr>
          `,
        )}
      </tbody>
    </table>
  `;
}

customElements.define(
  "civ-people-by-source",
  component(PeopleBySource as unknown as () => unknown, { useShadowDOM: false }),
);
