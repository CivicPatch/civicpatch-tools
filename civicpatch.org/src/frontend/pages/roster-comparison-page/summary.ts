import { html, type TemplateResult } from "lit-html";
import { FIELD_LABELS, OUTCOME_LABELS, percent } from "./labels.js";
import { columnNote, warningIcon } from "./values.js";
import {
  COMPARED_FIELDS,
  FIELD_FILTER_CONFLICT,
  FIELD_FILTER_ONE_SIDE_HAS_MORE,
  OUTCOMES,
  isSameSelection,
  type ComparedField,
  type FieldFilter,
  type Outcome,
  type OutcomeCounts,
  type PeopleSelection,
  type RosterComparisonRun,
} from "./types.js";

/** One stacked bar: matched, possible, only in uploaded data, only in civicpatch. */
export function outcomeBar(outcomes: OutcomeCounts, label: string, small = false) {
  const whole = OUTCOMES.reduce((sum, outcome) => sum + outcomes[outcome], 0);
  return html`<div
    class="rc-bar ${small ? "rc-bar--small" : ""}"
    role="img"
    aria-label=${`${label}: ${OUTCOMES.map((o) => `${OUTCOME_LABELS[o]} ${outcomes[o]}`).join(", ")}`}
  >
    ${OUTCOMES.filter((outcome) => outcomes[outcome] > 0).map(
      (outcome) => html`<span
        class="rc-bar__segment rc-outcome--${outcome}"
        style="flex-grow: ${outcomes[outcome]}"
        title=${`${OUTCOME_LABELS[outcome]}: ${outcomes[outcome]} (${percent(outcomes[outcome], whole)})`}
      ></span>`,
    )}
  </div>`;
}

export function peoplePanel(
  run: RosterComparisonRun,
  selected: PeopleSelection | null,
  onSelect: (selection: PeopleSelection) => void,
) {
  const outcomes = run.rates.outcomes;
  const whole = OUTCOMES.reduce((sum, outcome) => sum + outcomes[outcome], 0);
  const count = (outcome: Outcome) => {
    const text = `${outcomes[outcome]} (${percent(outcomes[outcome], whole)})`;
    if (outcomes[outcome] === 0) return html`<span class="rc-legend__count">${text}</span>`;
    const pressed = isSameSelection(selected, { outcome });
    return html`<button
      type="button"
      class="rc-count rc-legend__count"
      aria-pressed=${pressed ? "true" : "false"}
      @click=${() => onSelect({ outcome })}
    >${text}</button>`;
  };
  return html`<section class="panel">
    <div class="panel__cap"><b>people</b><span class="panel__cap-right">${whole}</span></div>
    ${outcomeBar(outcomes, "People")}
    <ul class="rc-legend">
      ${OUTCOMES.map(
        (outcome) => html`<li>
          <span class="rc-legend__swatch rc-outcome--${outcome}"></span>${OUTCOME_LABELS[outcome]} ${count(outcome)}
        </li>`,
      )}
    </ul>
    <p class="rc-note">Possible match: linked only by a nickname, or a name that fits several people. Click a count to list those people across the state.</p>
  </section>`;
}

export function fieldsPanel(
  run: RosterComparisonRun,
  selected: PeopleSelection | null,
  onSelect: (selection: PeopleSelection) => void,
) {
  const matched = run.rates.outcomes.matched;
  const count = (field: ComparedField, filter: FieldFilter, value: number, text: string | TemplateResult) => {
    if (value === 0) return text;
    const pressed = isSameSelection(selected, { field, filter });
    return html`<button
      type="button"
      class="rc-count"
      aria-pressed=${pressed ? "true" : "false"}
      title=${`${value} people`}
      @click=${() => onSelect({ field, filter })}
    >${text}</button>`;
  };
  return html`<section class="panel">
    <div class="panel__cap"><b>fields</b><span class="panel__cap-right">over ${matched} matched people</span></div>
    <div class="rc-scroll">
      <table class="rc-table rc-table--wide">
        <thead>
          <tr>
            <th>Field</th>
            <th class="rc-number">Agree</th>
            <th class="rc-number">One side has more</th>
            <th class="rc-number">Conflict</th>
            <th class="rc-number">Uploaded data has it</th>
            <th class="rc-number">civicpatch has it</th>
          </tr>
        </thead>
        <tbody>
          ${COMPARED_FIELDS.map((field) => {
            const counts = run.rates.fields[field];
            if (!counts) return null;
            return html`<tr>
              <td>${FIELD_LABELS[field]}${columnNote(field, run.source_columns)}</td>
              <td class="rc-number">${percent(counts.agreement, matched)}</td>
              <td class="rc-number">${count(field, FIELD_FILTER_ONE_SIDE_HAS_MORE, counts.one_side_has_more, html`${warningIcon} ${percent(counts.one_side_has_more, matched)}`)}</td>
              <td class="rc-number">${count(field, FIELD_FILTER_CONFLICT, counts.conflict, percent(counts.conflict, matched))}</td>
              <td class="rc-number">${percent(counts.uploaded_data_has_it, matched)}</td>
              <td class="rc-number">${percent(counts.civicpatch_has_it, matched)}</td>
            </tr>`;
          })}
        </tbody>
      </table>
    </div>
    <p class="rc-note">Agree includes one side having more. "Has it" counts people with any value. Click a count to list those people.</p>
  </section>`;
}
