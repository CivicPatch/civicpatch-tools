// Step 2 of a merge: what does the merged record contain?
//
// Step 1 — which record is the same person — happens inline on the editor, so this
// only ever opens with a pair already chosen. Merging drops the absorbed row and
// there is no undo short of Reset all, so nothing commits until this screen has
// named the survivor.
//
// Body only, and props-driven. It is one of the two screens the review modal
// shows, so merging never stacks a second modal — and its actions live in the
// dialog's own footer, where they cannot scroll out of reach. That means the plan
// has to be owned above this component, not in it.

import { html, nothing } from "lit-html";
import { component } from "haunted";
import "./merge-picker.css";
import {
  MergeChoice,
  type MergeChoiceKey,
  type MergeFieldPlan,
  type MergePlan,
} from "./merge-model.js";
import { personOf, type PersonCard } from "../people/person-cards.js";

const CHOICE_LABEL: Record<string, string> = {
  [MergeChoice.KEEP]: "Keep",
  [MergeChoice.REPLACE]: "Replace",
  [MergeChoice.BOTH]: "Keep both",
};

interface MergePickerHost extends HTMLElement {
  anchor: PersonCard | null;
  survivor: PersonCard | null;
  absorbed: PersonCard | null;
  plan: MergePlan | null;
  onChoose: (fieldKey: string, choice: MergeChoiceKey) => void;
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
  const { anchor, survivor, absorbed, plan, onChoose, onBack } = host;

  if (!anchor || !survivor || !absorbed || !plan) return nothing;

  // Fields the two records already agree on are not decisions; they collapse to
  // a count so the screen only shows what the reviewer has to look at.
  const contested = plan.fields.filter((entry) => !entry.same);
  const agreed = plan.fields.length - contested.length;

  const survivorName = personOf(survivor)?.name || "this record";
  const anchorName = personOf(anchor)?.name || "the person";
  const absorbedName = personOf(absorbed)?.name || "the other record";

  return html`
    <div class="merge-picker">
      <button class="merge-picker__back" @click=${onBack}>
        <i class="fa-solid fa-arrow-left" aria-hidden="true"></i>
        Back to ${anchorName}
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
            ${contested.map((entry) => renderFieldRow(entry, onChoose))}
          </div>`
        : html`<p class="merge-picker__empty">
            These two records agree on every field.
          </p>`}
      ${agreed
        ? html`<p class="merge-picker__agreed">${agreed} fields already agree.</p>`
        : nothing}
    </div>
  `;
}

customElements.define(
  "merge-picker",
  component(MergePicker as unknown as () => unknown, { useShadowDOM: false }),
);
