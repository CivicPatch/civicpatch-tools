import { html, component, useState } from "haunted";
import { getColumns } from "../edit-people/table/columns.js";
import "../basic/table/table.js";
import "../person-image.js";
import "../edit-people/profile-modal.js";

function ReviewWorkspace({ pullRequest, existing, selectedPeople, isDirty, onMerge, onBulkDelete, onReset, onAdd, onLinkPerson }) {
  const pullRequestArr = Array.isArray(pullRequest) ? pullRequest : [];
  const existingArr = Array.isArray(existing) ? existing : [];
  const selected = Array.isArray(selectedPeople) ? selectedPeople : [];

  const existingIds = new Set(existingArr.map((p) => p.id));
  const matchedPeople = pullRequestArr.filter((p) => existingIds.has(p.id));
  const newPeople = pullRequestArr.filter((p) => !existingIds.has(p.id));
  const allEditable = [...matchedPeople, ...newPeople];

  const [profileModal, setProfileModal] = useState({ open: false, person: null, existingPerson: null });

  function openProfileModal(person) {
    const existingPerson = existingArr.find(p => p.id === person.id) ?? null;
    setProfileModal({ open: true, person, existingPerson });
  }

  function handleLinkPerson(e) {
    const { personId } = e.detail;
    if (onLinkPerson) onLinkPerson(profileModal.person, personId, existingArr);
    setProfileModal(prev => ({ ...prev, open: false }));
  }

  const columns = getColumns(openProfileModal);

  return html`
    <div class="review-workspace">
      <div class="action-buttons">
        <button class="secondary btn-sm" @click=${onAdd}>Add</button>
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
      <profile-modal
        .open=${profileModal.open}
        .person=${profileModal.person}
        .existingPerson=${profileModal.existingPerson}
        .nameMatches=${[]}
        .searchSuggestions=${[]}
        @link-person=${handleLinkPerson}
        @close=${() => setProfileModal({ open: false, person: null, existingPerson: null })}
      ></profile-modal>
    </div>
  `;
}

customElements.define("civ-review-workspace", component(ReviewWorkspace, { useShadowDOM: false }));
