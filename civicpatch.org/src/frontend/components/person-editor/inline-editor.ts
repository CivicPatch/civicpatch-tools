import { html, nothing } from "lit-html";
import { ref } from "lit-html/directives/ref.js";
import { focusOnMount } from "../../utils/focus-on-mount.js";
import {
  renderPersonEditor,
  renderPersonSummary,
  type PersonEditorProps,
} from "./person-editor.js";
import { type PersonCard, cardKey } from "../people/person-cards.js";

export interface InlinePersonEditorProps {
  card: PersonCard;
  openCardKey: string | null;
  editorFor: (card: PersonCard) => PersonEditorProps;
  idPrefix: string;
}

// Shared by review-overview and the jurisdiction roster editor — the row a caller
// renders this under must use the same `idPrefix` as its `controlsId`/`aria-controls`.
export function renderInlinePersonEditor({
  card,
  openCardKey,
  editorFor,
  idPrefix,
}: InlinePersonEditorProps) {
  if (cardKey(card) !== openCardKey) return nothing;
  const editorProps = editorFor(card);
  const focusWrapper = (el?: Element) => {
    if (!editorProps.focusField) focusOnMount(el);
  };
  const id = `${idPrefix}${cardKey(card)}`;
  return html`
    <div
      class="person-editor-inline"
      id=${id}
      tabindex="-1"
      ${ref(focusWrapper)}
    >
      <div class="person-editor-inline__inner person-editor-list">
        <div class="person-editor-inline__summary">
          ${renderPersonSummary(editorProps)}
        </div>
        ${renderPersonEditor(editorProps)}
      </div>
    </div>
  `;
}
