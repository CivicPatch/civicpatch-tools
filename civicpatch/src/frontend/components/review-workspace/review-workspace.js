import { html, component, useState } from "haunted";
import { getColumns } from "../edit-people/table/columns.js";
import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import { searchPeople } from "../../api.js";
import "../edit-people/people-table.js";
import "../person-image.js";
import "../edit-people/profile-modal.js";

function ReviewWorkspace({ pullRequest, existing, selectedPeople, isDirty, resolvedMatches, jurisdictionOcdid, sourceContentUrls, onMerge, onBulkDelete, onReset, onAdd }) {
  const pullRequestArr = Array.isArray(pullRequest) ? pullRequest : [];
  const existingArr = Array.isArray(existing) ? existing : [];
  const selected = Array.isArray(selectedPeople) ? selectedPeople : [];
  const matches = resolvedMatches ?? {};

  const allEditable = pullRequestArr;

  const [profileModal, setProfileModal] = useState({ open: false, person: null, existingPerson: null, nameMatches: [], searchSuggestions: [] });

  async function openProfileModal(person) {
    const resolved = matches[person.id];
    let existingPerson = existingArr.find(p => p.id === person.id) ?? resolved?.person ?? null;
    let nameMatches = [];

    if (resolved && resolved.id !== person.id) {
      if (resolved.ambiguous) {
        nameMatches = resolved.person;
      } else {
        existingPerson = resolved.person;
        nameMatches = [resolved.person];
      }
    }

    setProfileModal({ open: true, person, existingPerson, nameMatches, searchSuggestions: [] });

    if (person._isNew && person.name && jurisdictionOcdid) {
      try {
        const result = await searchPeople(jurisdictionOcdid, person.name);
        setProfileModal(prev => ({ ...prev, searchSuggestions: result.data ?? [] }));
      } catch {
        // non-blocking
      }
    }
  }

  function handleLinkPerson(e) {
    const { personId } = e.detail;
    setProfileModal(prev => ({ ...prev, open: false }));
    e.target.dispatchEvent(new CustomEvent("link-person", {
      detail: { personId, proposedPerson: profileModal.person, existingPeople: existingArr },
      bubbles: true,
    }));
  }

  const sourceUrlMap = buildSourceUrlMap(sourceContentUrls ?? []);
  const columns = getColumns(openProfileModal, sourceUrlMap);

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
      <civ-people-table
        .data=${allEditable}
        .columns=${columns}
      ></civ-people-table>
      <profile-modal
        .open=${profileModal.open}
        .person=${profileModal.person}
        .existingPerson=${profileModal.existingPerson}
        .nameMatches=${profileModal.nameMatches ?? []}
        .searchSuggestions=${profileModal.searchSuggestions ?? []}
        .jurisdictionOcdid=${jurisdictionOcdid}
        @link-person=${handleLinkPerson}
        @close=${() => setProfileModal({ open: false, person: null, existingPerson: null, nameMatches: [], searchSuggestions: [] })}
      ></profile-modal>
    </div>
  `;
}

customElements.define("civ-review-workspace", component(ReviewWorkspace, { useShadowDOM: false }));
