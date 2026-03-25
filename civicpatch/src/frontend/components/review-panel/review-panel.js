import { component } from "haunted";
import { html } from "lit-html";
import "../edit-people/review-table.js";
import "../diff-panel/diff-panel.js";

const ReviewPanel = ({ reviewData, existing, pullRequest }) => html`
  <civ-review-table
    .reviewData=${reviewData}
  ></civ-review-table>
  <civ-diff-panel
    .data=${{ existing: existing ?? [], pull_request: pullRequest ?? [] }}
  ></civ-diff-panel>
`;

customElements.define(
  "civ-review-panel",
  component(ReviewPanel, { useShadowDOM: false }),
);
