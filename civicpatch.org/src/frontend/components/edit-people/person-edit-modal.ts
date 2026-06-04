import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import "../basic/modal.js";
import "./person-edit-modal.css";
import {
  type DateParts,
  type DivisionType,
  type Person,
  type Draft,
  DIVISION_AT_LARGE,
  DIVISION_OTHER,
  jurisdictionToDivisionBase,
  buildDivisionOcdid,
  toDraft,
  buildUpdates,
} from "./person-edit-utils.js";

export const SAVE_EVENT = "save";
export const CANCEL_EVENT = "cancel";
const SOURCE_WINDOW_NAME = "civ-source-viewer";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = Array.from({ length: 31 }, (_, i) => String(i + 1).padStart(2, "0"));
const pad = (n: number) => String(n).padStart(2, "0");

type PersonEditModalHost = HTMLElement & { person?: Person; jurisdictionOcdid: string };

const inputValue = (e: Event) => (e.target as HTMLInputElement | HTMLSelectElement).value;
const replaceAt = (arr: string[], i: number, v: string) => arr.map((x, j) => (j === i ? v : x));
const removeAt = (arr: string[], i: number) => arr.filter((_, j) => j !== i);

function openSource(url: string) {
  if (url) window.open(url, SOURCE_WINDOW_NAME, "width=900,height=800");
}

function renderMultiValue(label: string, items: string[], addLabel: string, onChange: (next: string[]) => void) {
  return html`
    <p class="person-edit__section-title">${label}</p>
    <div class="person-edit__rows">
      ${items.map((item, i) => html`
        <div class="person-edit__row">
          <input type="text" .value=${item} @input=${(e: Event) => onChange(replaceAt(items, i, inputValue(e)))} />
          <button class="btn btn-sm person-edit__icon-btn" title="Remove" @click=${() => onChange(removeAt(items, i))}>
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
      `)}
    </div>
    <button class="btn btn-sm person-edit__add" @click=${() => onChange([...items, ""])}>
      <i class="fa-solid fa-plus"></i> ${addLabel}
    </button>
  `;
}

function renderSources(items: string[], onChange: (next: string[]) => void) {
  return html`
    <p class="person-edit__section-title">
      Sources <small style="font-weight:400;text-transform:none;letter-spacing:0;">— open to verify against</small>
    </p>
    <div class="person-edit__rows">
      ${items.map((item, i) => html`
        <div class="person-edit__row">
          <button class="btn btn-sm person-edit__source-open" title="Open source" ?disabled=${!item} @click=${() => openSource(item)}>
            <i class="fa-solid fa-up-right-from-square"></i>
          </button>
          <input type="text" .value=${item} @input=${(e: Event) => onChange(replaceAt(items, i, inputValue(e)))} />
          <button class="btn btn-sm person-edit__icon-btn" title="Remove" @click=${() => onChange(removeAt(items, i))}>
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
      `)}
    </div>
    <button class="btn btn-sm person-edit__add" @click=${() => onChange([...items, ""])}>
      <i class="fa-solid fa-plus"></i> Add source
    </button>
  `;
}

function renderDate(label: string, parts: DateParts, onChange: (next: DateParts) => void) {
  const setPart = (key: keyof DateParts, value: string) => {
    const next = { ...parts, [key]: value };
    if (key === "month" && !value) next.day = ""; // a day with no month is meaningless
    onChange(next);
  };
  return html`
    <div class="person-edit__field">
      ${label}
      <div class="person-edit__date">
        <input class="year" type="number" min="1900" max="2100" placeholder="Year" aria-label="Year"
          .value=${parts.year} @input=${(e: Event) => setPart("year", inputValue(e))} />
        <select class="month" aria-label="Month" @change=${(e: Event) => setPart("month", inputValue(e))}>
          <option value="" ?selected=${!parts.month}>—</option>
          ${MONTHS.map((name, i) => html`<option value=${pad(i + 1)} ?selected=${pad(i + 1) === parts.month}>${name}</option>`)}
        </select>
        <select class="day" aria-label="Day" ?disabled=${!parts.month} @change=${(e: Event) => setPart("day", inputValue(e))}>
          <option value="" ?selected=${!parts.day}>—</option>
          ${DAYS.map((d) => html`<option value=${d} ?selected=${d === parts.day}>${String(Number(d))}</option>`)}
        </select>
      </div>
    </div>
  `;
}

function renderDivision(person: Person, draft: Draft, jurisdictionOcdid: string, patch: (partial: Partial<Draft>) => void) {
  const isOther = draft.divisionType === DIVISION_OTHER;
  const atLarge = draft.divisionType === DIVISION_AT_LARGE;
  const preview = isOther
    ? person.office?.division_ocdid ?? jurisdictionToDivisionBase(jurisdictionOcdid)
    : buildDivisionOcdid(jurisdictionOcdid, draft.divisionType, draft.divisionValue);
  return html`
    <div class="person-edit__field person-edit__field--full">
      Division
      <div class="person-edit__division">
        <select aria-label="Division type"
          @change=${(e: Event) => patch({ divisionType: inputValue(e) as DivisionType, divisionValue: "" })}>
          ${isOther ? html`<option selected disabled>Custom: ${person.office?.division_ocdid}</option>` : ""}
          <option value=${DIVISION_AT_LARGE} ?selected=${atLarge}>At-large (no district)</option>
          <option value="council_district" ?selected=${draft.divisionType === "council_district"}>Council District</option>
          <option value="ward" ?selected=${draft.divisionType === "ward"}>Ward</option>
        </select>
        ${atLarge || isOther ? "" : html`
          <input type="text" placeholder="required" aria-label="Division value" required
            .value=${draft.divisionValue} @input=${(e: Event) => patch({ divisionValue: inputValue(e) })} />
        `}
      </div>
      <small class="person-edit__hint">${preview}</small>
    </div>
  `;
}

function PersonEditModal(host: PersonEditModalHost) {
  const person = host.person;
  const jurisdictionOcdid = host.jurisdictionOcdid;
  const [draft, setDraft] = useState<Draft | null>(person ? toDraft(person) : null);

  useEffect(() => {
    setDraft(person ? toDraft(person) : null);
  }, [person?.id]);

  if (!person || !draft) return html``;

  const patch = (partial: Partial<Draft>) => setDraft({ ...draft, ...partial });

  const handleCancel = () =>
    host.dispatchEvent(new CustomEvent(CANCEL_EVENT, { bubbles: true, composed: true }));
  const handleSave = () =>
    host.dispatchEvent(new CustomEvent(SAVE_EVENT, {
      detail: { id: person.id, updates: buildUpdates(person, draft, jurisdictionOcdid) },
      bubbles: true,
      composed: true,
    }));

  const content = html`
    <div class="person-edit__form">
      <div class="person-edit__grid">
        <label class="person-edit__field">
          Name
          <input type="text" .value=${draft.name} @input=${(e: Event) => patch({ name: inputValue(e) })} />
        </label>
        <label class="person-edit__field">
          Office name
          <input type="text" .value=${draft.officeName} @input=${(e: Event) => patch({ officeName: inputValue(e) })} />
        </label>
        ${renderDate("Start date", draft.startDate, (startDate) => patch({ startDate }))}
        ${renderDate("End date", draft.endDate, (endDate) => patch({ endDate }))}
        ${renderDivision(person, draft, jurisdictionOcdid, patch)}
      </div>

      ${renderMultiValue("Other names", draft.otherNames, "Add name", (otherNames) => patch({ otherNames }))}
      ${renderMultiValue("Phones", draft.phones, "Add phone", (phones) => patch({ phones }))}
      ${renderMultiValue("Emails", draft.emails, "Add email", (emails) => patch({ emails }))}
      ${renderMultiValue("URLs", draft.urls, "Add URL", (urls) => patch({ urls }))}
      ${renderSources(draft.sourceUrls, (sourceUrls) => patch({ sourceUrls }))}
    </div>
  `;

  const footer = html`
    <button class="btn btn-sm secondary" @click=${handleCancel}>Cancel</button>
    <button class="btn btn-sm btn-gradient" @click=${handleSave}>Save</button>
  `;

  return html`
    <civ-modal
      .title=${"Edit person"}
      .content=${content}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleCancel }}
    ></civ-modal>
  `;
}

customElements.define(
  "civ-person-edit-modal",
  component(PersonEditModal as unknown as () => unknown, { useShadowDOM: false }),
);
