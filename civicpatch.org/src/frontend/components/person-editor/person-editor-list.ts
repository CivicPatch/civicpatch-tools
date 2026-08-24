// Detail v2 — the list of editors (spec §5).
//
// Ungrouped: one list in slot order. Unlike Overview, this is a surface you work
// top to bottom, so To Review / Unchanged headings would only add scrolling.
//
// The frozen field set is a prop, not state. Three views have to agree on which
// fields a person shows and switching between them must not recompute the set
// (§2.1), so the review-session page owns it.

import { html, nothing } from "lit-html";
import { component, useState } from "haunted";
import "./person-editor.css";
import type { OfficeOption } from "../posts-list/posts-model.js";
import { type FrozenFields } from "../../pages/review-session-page/frozen-fields.js";
import { renderPersonEditor } from "./person-editor.js";
import { type PersonCard } from "../people/person-cards.js";
import { personEditorPropsFor } from "./editor-props.js";

interface PersonEditorListProps {
  cards: PersonCard[];
  frozen: FrozenFields;
  // Expansion is per card, so it resets when the reviewer moves on. §21.4 also
  // wants it invalidated by identity-changing actions — that lands with merge.
  requestId: string | null;
  dirtyIds: Set<string>;
  isReadOnly: boolean;
  jurisdictionOcdid: string | null | undefined;
  officeOptions: OfficeOption[];
  onPersonSave: (id: string, updates: Record<string, unknown>) => void;
  onRemovePerson: (id: string) => void;
  onUnremovePerson: (id: string) => void;
  onRestorePerson: (person: any) => void;
  onResetPerson: (id: string) => void;
  mergeOpenId: string | null;
  onToggleMerge: (personId: string) => void;
  onPickPartner: (anchorId: string, partnerId: string) => void;
  onAdd?: () => void;
}

const NO_EXPANSION = {
  requestId: null as string | null,
  ids: new Set<string>(),
};

function PersonEditorList({
  cards,
  frozen,
  requestId,
  dirtyIds,
  isReadOnly,
  jurisdictionOcdid,
  officeOptions,
  onPersonSave,
  onRemovePerson,
  onUnremovePerson,
  onRestorePerson,
  onResetPerson,
  mergeOpenId,
  onToggleMerge,
  onPickPartner,
  onAdd,
}: PersonEditorListProps) {
  const [expansion, setExpansion] = useState(NO_EXPANSION);

  // Advancing to the next card is a new card load, and this element is not
  // remounted between them — so the id it was opened for has to be checked
  // rather than assumed, or expansion leaks from one reviewer's card to the next.
  const expandedIds =
    expansion.requestId === requestId ? expansion.ids : NO_EXPANSION.ids;

  const toggleExpand = (personId: string) => {
    const ids = new Set(expandedIds);
    if (ids.has(personId)) ids.delete(personId);
    else ids.add(personId);
    setExpansion({ requestId, ids });
  };

  if (!cards.length) {
    return html`<div class="person-editor-list">
      <p class="person-editor__empty">No people to review.</p>
    </div>`;
  }

  return html`
    <div class="person-editor-list">
      ${cards.map((card) =>
        renderPersonEditor(
          personEditorPropsFor(card, {
            frozen,
            dirtyIds,
            isReadOnly,
            jurisdictionOcdid,
            officeOptions,
            isExpanded: (id: string) => expandedIds.has(id),
            onToggleExpand: toggleExpand,
            onPersonSave,
            onRemovePerson,
            onUnremovePerson,
            onRestorePerson,
            onResetPerson,
            cards,
            mergeOpenId,
            onToggleMerge,
            onPickPartner,
          }),
        ),
      )}
      ${!isReadOnly && onAdd
        ? html`<button class="person-editor person-editor--ghost" @click=${onAdd}>
            <span class="person-editor__ghost-mark">+</span>
            <span class="person-editor__ghost-label">Add a person</span>
          </button>`
        : nothing}
    </div>
  `;
}

customElements.define(
  "person-editor-list",
  component(PersonEditorList as unknown as () => unknown, {
    useShadowDOM: false,
  }),
);
