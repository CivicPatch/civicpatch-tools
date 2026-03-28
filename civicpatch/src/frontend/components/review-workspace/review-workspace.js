import { html, component } from "haunted";
import { getColumns } from "../edit-people/table/columns.js";
import "../basic/table/table.js";
import "../person-image.js";

function ReviewWorkspace({ pullRequest, existing, selectedPeople, isDirty, onMerge, onBulkDelete, onReset }) {
  const pullRequestArr = Array.isArray(pullRequest) ? pullRequest : [];
  const existingArr = Array.isArray(existing) ? existing : [];
  const selected = Array.isArray(selectedPeople) ? selectedPeople : [];

  const existingIds = new Set(existingArr.map((p) => p.id));
  const matchedPeople = pullRequestArr.filter((p) => existingIds.has(p.id));
  const newPeople = pullRequestArr.filter((p) => !existingIds.has(p.id));
  const allEditable = [...matchedPeople, ...newPeople];

  const columns = getColumns(null);

  return html`
    <div class="review-workspace">
      <div class="action-buttons">
        <button class="secondary btn-sm" @click=${onMerge} ?disabled=${selected.length < 2}>
          Merge (${selected.length})
        </button>
        <button class="secondary btn-sm" @click=${onBulkDelete} ?disabled=${selected.length === 0}>
          Delete (${selected.length})
        </button>
        <button class="secondary btn-sm" @click=${onReset} ?disabled=${!isDirty}>Reset</button>
      </div>
      ${allEditable.length ? html`
        <civ-table
          .identifier=${"id"}
          .data=${allEditable}
          .columns=${columns}
          .canReorder=${true}
        ></civ-table>
      ` : ""}
    </div>
  `;
}

customElements.define("civ-review-workspace", component(ReviewWorkspace, { useShadowDOM: false }));
