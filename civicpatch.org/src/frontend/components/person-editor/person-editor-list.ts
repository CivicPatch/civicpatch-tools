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
import type { Post } from "../posts-list/posts-model.js";
import { type FrozenFields } from "../../pages/review-session-page/frozen-fields.js";
import { renderPersonEditor } from "./person-editor.js";
import type { PersonAssertion } from "./field-provenance.js";
import {
  proposalsByPersonId,
  type PersonCard,
  type ProposedChange,
} from "../people/person-cards.js";
import {
  personEditorPropsFor,
  type EditorContextBase,
} from "./editor-props.js";

interface PersonEditorListProps {
  // One object, not ~20 restated properties — see `EditorContextBase`. `cards` rides along
  // in it, because the page decides who is on the roster.
  editorContext: EditorContextBase;
  // Expansion is per card, so it resets when the reviewer moves on. §21.4 also
  // wants it invalidated by identity-changing actions — that lands with merge.
  changesetId: string | null;
  onAdd?: () => void;
}

const NO_EXPANSION = {
  changesetId: null as string | null,
  ids: new Set<string>(),
};

function PersonEditorList({
  editorContext,
  changesetId,
  onAdd,
}: PersonEditorListProps) {
  const cards = editorContext.cards;
  const [expansion, setExpansion] = useState(NO_EXPANSION);

  // Advancing to the next card is a new card load, and this element is not
  // remounted between them — so the id it was opened for has to be checked
  // rather than assumed, or expansion leaks from one reviewer's card to the next.
  const expandedIds =
    expansion.changesetId === changesetId ? expansion.ids : NO_EXPANSION.ids;

  const toggleExpand = (personId: string) => {
    const ids = new Set(expandedIds);
    if (ids.has(personId)) ids.delete(personId);
    else ids.add(personId);
    setExpansion({ changesetId, ids });
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
            ...editorContext,
            isExpanded: (id: string) => expandedIds.has(id),
            onToggleExpand: toggleExpand,
          }),
        ),
      )}
      ${!editorContext.isReadOnly && onAdd
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
