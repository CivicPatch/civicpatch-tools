import { html, nothing } from "lit-html";
import { ref } from "lit-html/directives/ref.js";
import { focusOnMount } from "../../utils/focus-on-mount.js";
import {
  renderPersonEditor,
  renderPersonSummary,
  type PersonEditorProps,
} from "./person-editor.js";
import { type PersonCard } from "../people/person-cards.js";

export interface InlinePersonEditorProps {
  card: PersonCard;
  openPersonId: string | null;
  editorFor: (card: PersonCard) => PersonEditorProps;
  idPrefix: string;
}

// Shared by review-overview and the jurisdiction roster editor — the row a caller
// renders this under must use the same `idPrefix` as its `controlsId`/`aria-controls`.
export function renderInlinePersonEditor({
  card,
  openPersonId,
  editorFor,
  idPrefix,
}: InlinePersonEditorProps) {
  if (card.personId !== openPersonId) return nothing;
  const editorProps = editorFor(card);
  const focusWrapper = (el?: Element) => {
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
    if (!editorProps.focusField) focusOnMount(el);
  };
  const id = `${idPrefix}${card.personId}`;
  return html`
    <div class="person-editor-inline" id=${id} tabindex="-1" ${ref(focusWrapper)}>
      <div class="person-editor-inline__inner person-editor-list">
        <div class="person-editor-inline__summary">
          ${renderPersonSummary(editorProps)}
        </div>
        ${renderPersonEditor(editorProps)}
      </div>
    </div>
  `;
}
