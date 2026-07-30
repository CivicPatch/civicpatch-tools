// Step 2 of a merge: what does the merged record contain?
//
// Step 1 — which record is the same person — happens inline on the rail, so this
// only ever opens with a pair already chosen. Merging drops the absorbed row and
// there is no undo short of Reset all, so nothing commits until this screen has
// named the survivor.
//
// Content, not a dialog: this is one of the two screens the review modal shows, so
// merging never stacks a second modal over the person you opened.

import { html, nothing } from "lit-html";
import { component, useState } from "haunted";
import "./merge-picker.css";
import {
  applyMergePlan,
  chooseSurvivor,
  planMerge,
  setChoice,
  MergeChoice,
  type MergeChoiceKey,
  type MergeFieldPlan,
  type MergePlan,
} from "./merge-model.js";
import { personOf, STATUS_LABEL, type ReviewCard } from "./review-cards.js";

const CHOICE_LABEL: Record<string, string> = {
  [MergeChoice.KEEP]: "Keep",
  [MergeChoice.REPLACE]: "Replace",
  [MergeChoice.BOTH]: "Keep both",
};

interface MergePickerHost extends HTMLElement {
  anchor: ReviewCard | null;
  partner: ReviewCard | null;
  onMerge: (survivorId: string, absorbedId: string, merged: Record<string, unknown>) => void;
  // Back to the person this merge started from — never a close, because the modal
  // stays open on them.
  onBack: () => void;
}

const displayValue = (value: unknown): string => {
  if (Array.isArray(value)) return value.join(", ");
  const text = String(value ?? "").trim();
  return text || "—";
};

function renderFieldRow(
  entry: MergeFieldPlan,
  choose: (fieldKey: string, choice: MergeChoiceKey) => void,
) {
  const result =
    entry.choice === MergeChoice.KEEP
      ? entry.survivorValue
      : entry.choice === MergeChoice.REPLACE
        ? entry.candidateValue
        : [entry.survivorValue, entry.candidateValue];

  return html`
    <div class="merge-grid__label">${entry.field.label}</div>
    <div class="merge-grid__candidate">${displayValue(entry.candidateValue)}</div>
    <div class="merge-grid__choices">
      ${entry.choices.length > 1
        ? entry.choices.map(
            (choice) => html`<button
              class="merge-grid__choice btn-ghost"
              aria-pressed=${entry.choice === choice}
              @click=${() => choose(entry.field.key, choice)}
            >
              ${CHOICE_LABEL[choice] ?? choice}
            </button>`,
          )
        : html`<span class="merge-grid__fixed">kept</span>`}
    </div>
    <div class="merge-grid__result">
      ${displayValue(Array.isArray(result) ? result.flat() : result)}
    </div>
  `;
}

function MergePicker(host: MergePickerHost) {
  const { anchor, partner, onMerge, onBack } = host;
  const [edited, setEdited] = useState<MergePlan | null>(null);

  if (!anchor || !partner) return nothing;

  // The survivor is computed, never chosen: the reviewer is asserting that two
  // records are one human, not deciding which id outlives the other.
  const survivor = chooseSurvivor(anchor, partner);
  const absorbed = survivor.personId === anchor.personId ? partner : anchor;

  // The plan is derived until the reviewer touches it, so reopening on a
  // different pair cannot show a stale one.
  const plan = edited ?? planMerge(survivor, absorbed);

  const choose = (fieldKey: string, choice: MergeChoiceKey) =>
    setEdited(setChoice(plan, fieldKey, choice));

  const commit = () =>
    onMerge(
      survivor.personId,
      absorbed.personId,
      applyMergePlan(plan, survivor, absorbed) as Record<string, unknown>,
    );

  // Fields the two records already agree on are not decisions; they collapse to
  // a count so the screen only shows what the reviewer has to look at.
  const contested = plan.fields.filter((entry) => !entry.same);
  const agreed = plan.fields.length - contested.length;

  const survivorName = personOf(survivor)?.name || "this record";
  const absorbedName = personOf(absorbed)?.name || "the other record";
  return html`
    <div class="merge-picker">
      <button class="merge-picker__back" @click=${onBack}>
        <i class="fa-solid fa-arrow-left" aria-hidden="true"></i>
        Back to ${survivorName}
      </button>
      <h2 class="merge-picker__title">What survives</h2>
      <p class="merge-picker__survivor">
        <strong>${survivorName}</strong> survives and keeps their record.
        <span class="merge-picker__absorbed">${absorbedName} is dropped from the list.</span>
      </p>
      ${contested.length
        ? html`<div class="merge-grid">
            <div class="merge-grid__head">Field</div>
            <div class="merge-grid__head">${absorbedName}</div>
            <div class="merge-grid__head merge-grid__head--centre">Take it?</div>
            <div class="merge-grid__head">Result</div>
            ${contested.map((entry) => renderFieldRow(entry, choose))}
          </div>`
        : html`<p class="merge-picker__empty">
            These two records agree on every field.
          </p>`}
      ${agreed
        ? html`<p class="merge-picker__agreed">${agreed} fields already agree.</p>`
        : nothing}
      <div class="merge-picker__actions">
        <button class="btn-sm secondary" @click=${onBack}>Cancel</button>
        <button class="btn-sm" @click=${commit}>Merge into ${survivorName}</button>
      </div>
    </div>
  `;
}

customElements.define(
  "merge-picker",
  component(MergePicker as unknown as () => unknown, { useShadowDOM: false }),
);
