// One person, as a rail: a fixed-width identity column and a field body (§5).
//
// Only the frozen visible fields render, plus an expander for the rest. The
// frozen set is passed in rather than computed here — three views have to agree
// on it and a tab switch must not recompute it (§2.1), so the review-session
// page owns it.

import { html, nothing } from "lit-html";
import "../person-image.js";
import "./review-rail.css";
import {
  FIELD_SCHEMA,
  type DiffRecord,
  type FieldReason,
  type Issue,
  type SurvivingField,
} from "../review/field-model.js";
import { withDisplayImage, type Save } from "../review/field-controls.js";
import { divisionOcdidToFriendly } from "../ocdid-utils.js";
import { renderRailField } from "./rail-field.js";
import {
  DEPARTING,
  RailStatus,
  STATUS_LABEL,
  type RailStatusKey,
} from "../review/review-cards.js";

const BANNER: Record<string, { title: string; body: string }> = {
  [RailStatus.REMOVED]: {
    title: "Not found in this scrape.",
    body: "The scraper didn't see them on the source site, so publishing will drop them. Check whether they left office — or whether the scraper missed them.",
  },
  [RailStatus.DELETED]: {
    title: "You removed this person.",
    body: "Publishing will drop their record.",
  },
};

export interface PersonRailProps {
  status: RailStatusKey;
  oldRecord: DiffRecord;
  newRecord: DiffRecord;
  surviving: SurvivingField[];
  frozenReasons: Map<string, FieldReason>;
  issues: Issue[];
  isReadOnly: boolean;
  jurisdictionOcdid: string | null | undefined;
  // Clear-on-edit: once the reviewer touches a card its markers are presumed
  // addressed and drop away. §2.2 refines this to per-field (the *anchored* field
  // being edited); that lands with the checklist in §17 step 8, when ticking
  // gives the other half of the rule somewhere to live.
  isDirty: boolean;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onSave: Save;
  onDelete: () => void;
  onUndelete: () => void;
  onRestore: () => void;
  onReset: (() => void) | null;
  // §21 Interim: until merge exists, an unmatched scraped person can be declared
  // to be one of the people the scrape didn't find. Empty when there is nobody
  // to link to — including people the reviewer is dropping, who are excluded
  // upstream because linking adopts the target's id.
  linkCandidates: LinkCandidate[];
  onLink: (target: any) => void;
}

export interface LinkCandidate {
  id: string;
  name: string;
  office: string;
}

function renderLink(props: PersonRailProps) {
  const { linkCandidates, onLink } = props;
  const choose = (e: Event) => {
    const id = (e.target as HTMLSelectElement).value;
    const target = linkCandidates.find((c) => c.id === id);
    if (target) onLink(target);
  };
  return html`<select
    class="review-rail__link"
    aria-label="Link to an existing person"
    @change=${choose}
  >
    <option value="">Link to person…</option>
    ${linkCandidates.map(
      (c) => html`<option value=${c.id}>
        ${c.name}${c.office ? ` — ${c.office}` : ""}
      </option>`,
    )}
  </select>`;
}

// `size` has to be a property binding: person-image declares no
// observedAttributes, so size="3rem" is silently ignored and it falls back to
// its 2rem default.
const PHOTO_SIZE = "6.5rem";

function renderIdentity(props: PersonRailProps) {
  const { status, oldRecord, newRecord, isReadOnly } = props;
  const record = newRecord ?? oldRecord;
  const name = record?.name || "(unnamed)";
  const office = record?.office?.name ?? "";
  const division = divisionOcdidToFriendly(record?.office?.division_ocdid ?? "") || "";
  const departing = DEPARTING.has(status);

  return html`
    <div class="review-rail__identity">
      <person-image
        .person=${withDisplayImage(record)}
        .size=${PHOTO_SIZE}
      ></person-image>
      <div class="review-rail__name">${name}</div>
      <div class="review-rail__office">
        ${[office, division].filter(Boolean).join(" · ") || nothing}
      </div>
      <div class="review-rail__status">${STATUS_LABEL[status]}</div>
      ${isReadOnly ? nothing : renderActions(props, departing)}
    </div>
  `;
}

function renderActions(props: PersonRailProps, departing: boolean) {
  const { status, onDelete, onUndelete, onRestore, onReset } = props;

  // One button, two operations. A scrape-dropped person has no record to
  // un-flag, so restoring them rebuilds it from the old side; a reviewer-removed
  // one just loses the flag (§12).
  if (departing) {
    const restore = status === RailStatus.REMOVED ? onRestore : onUndelete;
    return html`<div class="review-rail__actions">
      <button class="review-rail__restore-person" @click=${restore}>
        Restore
      </button>
    </div>`;
  }

  return html`<div class="review-rail__actions">
    ${status === RailStatus.ADDED && props.linkCandidates.length
      ? renderLink(props)
      : nothing}
    ${onReset
      ? html`<button class="review-rail__reset" @click=${onReset}>Reset</button>`
      : nothing}
    <button class="review-rail__delete" @click=${onDelete}>Remove</button>
  </div>`;
}

// A departing person is one decision, not eleven fields. Their details stay
// available behind the expander rather than being spent by default.
function renderBanner(props: PersonRailProps) {
  const { status, isExpanded, onToggleExpand } = props;
  const copy = BANNER[status];
  return html`
    <div class="review-rail__banner">
      <span class="review-rail__banner-title">${copy.title}</span>
      <span>${copy.body}</span>
    </div>
    <button class="review-rail__expander" @click=${onToggleExpand}>
      ${isExpanded ? "Hide their details" : "Show their details"}
    </button>
  `;
}

// Issues that anchor to no field belong to the person, so they sit above the
// field list rather than under any row.
function renderRowIssues(props: PersonRailProps) {
  if (props.isDirty) return nothing;
  return props.issues
    .filter((issue) => !issue.field)
    .map(
      (issue) => html`<div class="review-rail__issue review-rail__issue--row">
        <i class="fa-solid fa-circle-exclamation"></i><span>${issue.message}</span>
      </div>`,
    );
}

function renderFields(props: PersonRailProps, keys: Set<string>) {
  const { oldRecord, newRecord, surviving, issues, isReadOnly, jurisdictionOcdid, onSave } = props;
  const survivingByKey = new Map(surviving.map((s) => [s.field.key, s]));

  return FIELD_SCHEMA.filter((field) => keys.has(field.key)).map((field) => {
    const current = survivingByKey.get(field.key);
    return renderRailField({
      field,
      oldRecord,
      newRecord,
      // A field can be frozen visible while no longer surviving on its own — a
      // fixed error is the whole point of the one-directional rule (§2.1).
      state: current?.state ?? "same",
      reason: props.frozenReasons.get(field.key) ?? "diff",
      error: current?.error ?? null,
      issueMessages: props.isDirty
        ? []
        : issues.filter((issue) => issue.field === field.key).map((issue) => issue.message),
      save: onSave,
      isReadOnly,
      jurisdictionOcdid,
    });
  });
}

// Someone with nothing to review is one line, not a card. The collapse rule
// already empties their field body; without this the identity column still sets
// a full block of height, so a 20-person council scrolls past ~15 blocks that
// say nothing to reach the few that changed. §4 already applies the same
// reasoning to Overview's unchanged group ("a face strip … without spending a
// card each"); this is that, in Detail.
//
// It stays in slot order and stays expandable, so §5's one ungrouped list is
// intact — it just stops spending a card on people with nothing to say.
function renderStrip(props: PersonRailProps) {
  const { status, oldRecord, newRecord, onToggleExpand } = props;
  const record = newRecord ?? oldRecord;
  const office = record?.office?.name ?? "";
  const division = divisionOcdidToFriendly(record?.office?.division_ocdid ?? "") || "";
  return html`
    <div class="review-rail review-rail--strip review-rail--${status}">
      <person-image
        .person=${withDisplayImage(record)}
        .size=${"2.75rem"}
      ></person-image>
      <span class="review-rail__name">${record?.name || "(unnamed)"}</span>
      <span class="review-rail__office">
        ${[office, division].filter(Boolean).join(" · ") || nothing}
      </span>
      <span class="review-rail__status">${STATUS_LABEL[status]}</span>
      <button class="review-rail__expander" @click=${onToggleExpand}>Show fields</button>
    </div>
  `;
}

export function renderPersonRail(props: PersonRailProps) {
  const { status, frozenReasons, isExpanded, onToggleExpand } = props;
  const departing = DEPARTING.has(status);

  const visibleKeys = new Set(frozenReasons.keys());
  const hiddenCount = FIELD_SCHEMA.length - visibleKeys.size;
  const keys = isExpanded ? new Set(FIELD_SCHEMA.map((f) => f.key)) : visibleKeys;

  if (!departing && visibleKeys.size === 0 && !isExpanded) return renderStrip(props);

  return html`
    <div class="review-rail review-rail--${status}">
      ${renderIdentity(props)}
      <div class="review-rail__fields">
        ${renderRowIssues(props)}
        ${departing
          ? renderBanner(props)
          : nothing}
        ${departing && !isExpanded ? nothing : renderFields(props, keys)}
        ${!departing && hiddenCount > 0
          ? html`<button class="review-rail__expander" @click=${onToggleExpand}>
              ${isExpanded
                ? "Hide unchanged fields"
                : `+ ${hiddenCount} unchanged field${hiddenCount === 1 ? "" : "s"}`}
            </button>`
          : nothing}
      </div>
    </div>
  `;
}