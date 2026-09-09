
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

const CHOICE_ICON: Record<string, string> = {
  [MergeChoice.KEEP]: "fa-solid fa-arrow-left",
  [MergeChoice.REPLACE]: "fa-solid fa-arrow-right",
  [MergeChoice.BOTH]: "fa-regular fa-copy",
};

function valueFor(entry: MergeFieldPlan, choice: MergeChoiceKey): unknown {
  if (choice === MergeChoice.REPLACE) return entry.candidateValue;
  if (choice === MergeChoice.BOTH) return [entry.survivorValue, entry.candidateValue];
  return entry.survivorValue;
}

interface MergePickerHost extends HTMLElement {
  anchor: PersonCard | null;
  survivor: PersonCard | null;
  absorbed: PersonCard | null;
  plan: MergePlan | null;
  onChoose: (fieldKey: string, choice: MergeChoiceKey) => void;
  onBack: () => void;
}

const displayValue = (value: unknown): string => {
  if (Array.isArray(value)) return value.join(", ");
  const text = String(value ?? "").trim();
  return text || "—";
};

function renderFixedRow(entry: MergeFieldPlan) {
  const value = valueFor(entry, entry.choice);
  return html`
    <div class="merge-grid__label">${entry.field.label}</div>
    <div class="merge-grid__fixed-value">
      ${displayValue(Array.isArray(value) ? value.flat() : value)}
      <span class="merge-grid__fixed">kept</span>
    </div>
  `;
}

function renderFieldRow(
  entry: MergeFieldPlan,
  names: { survivor: string; absorbed: string },
  choose: (fieldKey: string, choice: MergeChoiceKey) => void,
) {
  if (entry.choices.length <= 1) return renderFixedRow(entry);
  // A multi field never offers Replace — the survivor's list always stands, and the
  // only question is whether to fold the absorbed side's items in too (Both).
  const canReplace = entry.choices.includes(MergeChoice.REPLACE);
  const absorbedChoice = canReplace ? MergeChoice.REPLACE : MergeChoice.BOTH;
  const combining = entry.choice === MergeChoice.BOTH;
  return html`
    <div class="merge-grid__label">${entry.field.label}</div>
    <div
      class="merge-grid__side"
      aria-pressed=${entry.choice === MergeChoice.KEEP}
    >
      <span class="merge-grid__side-value"
        >${displayValue(entry.survivorValue)}</span
      >
      <button
        class="merge-grid__pick"
        aria-pressed=${entry.choice === MergeChoice.KEEP}
        aria-label="Keep ${names.survivor}'s ${entry.field.label}"
        @click=${() => choose(entry.field.key, MergeChoice.KEEP)}
      >
        <i class=${CHOICE_ICON[MergeChoice.KEEP]} aria-hidden="true"></i>
      </button>
    </div>
    <div
      class="merge-grid__side merge-grid__side--absorbed"
      aria-pressed=${entry.choice === absorbedChoice}
    >
      <button
        class="merge-grid__pick"
        aria-pressed=${entry.choice === absorbedChoice}
        aria-label=${canReplace
          ? `Use ${names.absorbed}'s ${entry.field.label}`
          : `Also include ${names.absorbed}'s ${entry.field.label}`}
        @click=${() => choose(entry.field.key, absorbedChoice)}
      >
        <i class=${CHOICE_ICON[absorbedChoice]} aria-hidden="true"></i>
      </button>
      <span class="merge-grid__side-value"
        >${displayValue(entry.candidateValue)}</span
      >
    </div>
    ${combining
      ? html`<div class="merge-grid__combined">
          combined: ${displayValue(
            (valueFor(entry, MergeChoice.BOTH) as unknown[]).flat(),
          )}
        </div>`
      : nothing}
  `;
}

function MergePicker(host: MergePickerHost) {
  const { anchor, survivor, absorbed, plan, onChoose, onBack } = host;
  if (!anchor || !survivor || !absorbed || !plan) return nothing;
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
            <div class="merge-grid__head">${survivorName}</div>
            <div class="merge-grid__head">${absorbedName}</div>
            ${contested.map((entry) =>
              renderFieldRow(
                entry,
                { survivor: survivorName, absorbed: absorbedName },
                onChoose,
              ),
            )}
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
