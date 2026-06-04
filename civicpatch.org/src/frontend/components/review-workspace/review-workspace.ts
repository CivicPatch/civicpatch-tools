import "./review-workspace.css";
import { html, component, useState } from "haunted";
import { getColumns } from "../edit-people/table/columns.js";
import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import { searchPeople } from "../../api.js";
import "../edit-people/people-table.js";
import "../person-image.js";
import "../edit-people/person-edit-modal.js";

interface ReviewWorkspaceProps {
  pullRequest: any[];
  existing: any[];
  selectedPeople: any[];
  isDirty: boolean;
  isTerminal?: boolean;
  resolvedMatches: Record<string, any>;
  jurisdictionOcdid: string | null;
  sourceContentUrls: any[];
  onMerge: (...args: any[]) => unknown;
  onBulkDelete: () => void;
  onReset: () => void;
  onAdd: () => void;
  onPersonSave: (id: string, updates: Record<string, unknown>) => void;
}

type ReviewWorkspaceHost = HTMLElement & ReviewWorkspaceProps;

function ReviewWorkspace(host: ReviewWorkspaceHost) {
  const { pullRequest, selectedPeople, isDirty, resolvedMatches, jurisdictionOcdid, sourceContentUrls, onMerge, onBulkDelete, onReset, onAdd, onPersonSave, isTerminal = false } = host;
  const pullRequestArr = Array.isArray(pullRequest) ? pullRequest : [];
  const selected = Array.isArray(selectedPeople) ? selectedPeople : [];
  const matches = resolvedMatches ?? {};

  const allEditable = pullRequestArr;

  const [editingPerson, setEditingPerson] = useState<any>(null);
  const [editingCandidates, setEditingCandidates] = useState<any[]>([]);

  function closeEdit() {
    setEditingPerson(null);
    setEditingCandidates([]);
  }

  function handlePersonSave(e: CustomEvent) {
    onPersonSave(e.detail.id, e.detail.updates);
    closeEdit();
  }

  // Existing-record candidates to offer for linking: ambiguous auto-matches, or
  // name-search hits for new people. Nothing for confident or no-match people.
  async function openEdit(person) {
    setEditingPerson(person);
    setEditingCandidates([]);
    const resolved = matches[person.id];
    if (resolved?.ambiguous) {
      setEditingCandidates(resolved.person ?? []);
    } else if (person._isNew && person.name && jurisdictionOcdid) {
      try {
        const result = await searchPeople(jurisdictionOcdid, person.name);
        setEditingCandidates(result.data ?? []);
      } catch {
        // non-blocking
      }
    }
  }

  const sourceUrlMap = buildSourceUrlMap(sourceContentUrls ?? []);
  const columns = getColumns(sourceUrlMap, {
    readOnly: true,
    onEdit: isTerminal ? null : openEdit,
  });

  return html`
    <div class="review-workspace">
      <div class="action-buttons">
        <button class="secondary btn-sm" @click=${onAdd} ?disabled=${isTerminal}>Add</button>
        <button class="secondary btn-sm" @click=${onMerge} ?disabled=${isTerminal || selected.length < 2}>
          Merge (${selected.length})
        </button>
        <button class="secondary btn-sm" @click=${onBulkDelete} ?disabled=${isTerminal || selected.length === 0}>
          Delete (${selected.length})
        </button>
        <button class="secondary btn-sm action-buttons__reset" @click=${onReset} ?disabled=${isTerminal || !isDirty}>Reset</button>
      </div>
      <civ-people-table
        .data=${allEditable}
        .columns=${columns}
      ></civ-people-table>
      ${editingPerson ? html`
        <civ-person-edit-modal
          .person=${editingPerson}
          .jurisdictionOcdid=${jurisdictionOcdid}
          .candidates=${editingCandidates}
          @save=${handlePersonSave}
          @cancel=${closeEdit}
        ></civ-person-edit-modal>
      ` : ""}
    </div>
  `;
}

customElements.define("civ-review-workspace", component(ReviewWorkspace, { useShadowDOM: false }));
