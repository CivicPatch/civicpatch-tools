
import { html, nothing } from "lit-html";
import "../person-image.js";
import "./person-editor.css";
import type { DerivedPost, Post } from "../posts-list/posts-model.js";
import {
  announcementFor,
  fieldLock,
  type PersonAssertion,
} from "./field-provenance.js";
import {
  FIELD_SCHEMA,
  diffValue,
  isContextField,
  type DiffRecord,
  type FieldReason,
  type Issue,
  type SurvivingField,
} from "../fields/field-model.js";
import { focusedKey } from "./editor-focus.js";
import { withDisplayImage, type FieldFocus, type Save } from "../fields/field-controls.js";
import { renderEditorField } from "./editor-field.js";
import {
  DEPARTING,
  PersonStatus,
  STATUS_LABEL,
  type PersonStatusKey,
  type PersonCard,
} from "../people/person-cards.js";
import { renderPersonFace } from "../review/person-face.js";
import { editorSummary } from "./editor-summary.js";

const BANNER: Record<string, { title: string; body: string }> = {
  [PersonStatus.REMOVED]: {
    title: "Not found in this scrape.",
    body: "The scraper didn't see them on the source site, so publishing will drop them. Check whether they left office — or whether the scraper missed them.",
  },
  [PersonStatus.DELETED]: {
    title: "You removed this person.",
    body: "Publishing will drop their record.",
  },
};

export interface PersonEditorProps {
  status: PersonStatusKey;
  oldRecord: DiffRecord;
  newRecord: DiffRecord;
  surviving: SurvivingField[];
  frozenReasons: Map<string, FieldReason>;
  issues: Issue[];
  isReadOnly: boolean;
  jurisdictionOcdid: string | null | undefined;
  subtitle: string;
  accepts: Map<string, PersonAssertion[]>;
  assertions: PersonAssertion[];
  overriddenSourceValues: Record<string, unknown>;
  posts: Post[];
  derivedPost: DerivedPost | null;
  onAddPost: () => void;
  isDirty: boolean;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onSave: Save;
  onRemove: () => void;
  onUnremove: () => void;
  onRestore: () => void;
  onReset: (() => void) | null;
  mergeCandidates: PersonCard[];
  isCandidateListOpen: boolean;
  onToggleCandidates: () => void;
  onPickPartner: (partnerId: string) => void;
  focusField: FieldFocus | null;
  navHint?: { hasPrev: boolean; hasNext: boolean };
}

const PHOTO_SIZE = "7.5rem";

function renderIdentity(props: PersonEditorProps) {
  const { status, oldRecord, newRecord, subtitle } = props;
  const record = newRecord ?? oldRecord;
  const name = record?.name || "(unnamed)";
  return html`
    <div class="person-editor__identity">
      <person-image
        .person=${withDisplayImage(record)}
        .size=${PHOTO_SIZE}
      ></person-image>
      <div class="person-editor__name">${name}</div>
      <div class="person-editor__office">${subtitle || nothing}</div>
    </div>
  `;
}

export function renderPersonSummary(props: PersonEditorProps) {
  const { status, surviving, issues, isDirty, isReadOnly } = props;
  return html`
    <span class="editor-summary"
      >${editorSummary({ status, surviving, issues, isDirty })}</span
    >
    ${isReadOnly ? nothing : renderActions(props, DEPARTING.has(status))}
  `;
}

function renderMergeCandidates(props: PersonEditorProps) {
  if (props.isReadOnly || !props.isCandidateListOpen || !props.mergeCandidates.length) return nothing;
  return html`
    <div class="person-editor__merge-with">
      <span class="person-editor__merge-lede">Which record is the same person?</span>
      <div class="person-editor__merge-faces">
        ${props.mergeCandidates.map((card) => renderPersonFace(card, props.onPickPartner))}
      </div>
    </div>
  `;
}

function renderActions(props: PersonEditorProps, departing: boolean) {
  const { status, onRemove, onUnremove, onRestore, onReset } = props;
  if (departing) {
    const restore = status === PersonStatus.REMOVED ? onRestore : onUnremove;
    return html`<div class="person-editor__actions">
      <button class="person-editor__action-btn person-editor__restore-person" @click=${restore}>
        Restore
      </button>
    </div>`;
  }
  return html`<div class="person-editor__actions">
    ${onReset
      ? html`<button class="person-editor__action-btn person-editor__reset" @click=${onReset}>Reset</button>`
      : nothing}
    <button class="person-editor__action-btn person-editor__delete" @click=${onRemove}>Remove</button>
    ${props.mergeCandidates.length
      ? html`<button
          class="person-editor__action-btn person-editor__merge"
          aria-expanded=${props.isCandidateListOpen}
          @click=${props.onToggleCandidates}
        >
          Merge with…
        </button>`
      : nothing}
  </div>`;
}

function renderBanner(props: PersonEditorProps) {
  const { status, isExpanded, onToggleExpand } = props;
  const copy = BANNER[status];
  return html`
    <div class="person-editor__banner">
      <span class="person-editor__banner-title">${copy.title}</span>
      <span>${copy.body}</span>
    </div>
    <button class="person-editor__expander" @click=${onToggleExpand}>
      ${isExpanded ? "Hide their details" : "Show their details"}
    </button>
  `;
}

function renderRowIssues(props: PersonEditorProps) {
  if (props.isDirty) return nothing;
  return props.issues
    .filter((issue) => !issue.field)
    .map(
      (issue) => html`<div class="person-editor__issue person-editor__issue--row">
        <i class="fa-solid fa-circle-exclamation"></i><span>${issue.message}</span>
      </div>`,
    );
}

function renderFields(props: PersonEditorProps, keys: Set<string>) {
  const {
    oldRecord,
    newRecord,
    surviving,
    issues,
    isReadOnly,
    jurisdictionOcdid,
    posts,
    derivedPost,
    onAddPost,
    onSave,
  } = props;
  const survivingByKey = new Map(surviving.map((s) => [s.field.key, s]));
  const fields = FIELD_SCHEMA.filter((field) => keys.has(field.key));
  const focus = props.focusField;
  const focusKey = focusedKey(fields, focus);
  return fields.map((field) => {
    const current = survivingByKey.get(field.key);
    return renderEditorField({
      field,
      oldRecord,
      newRecord,
      state: current?.state ?? "same",
      reason: props.frozenReasons.get(field.key) ?? "diff",
      error: current?.error ?? null,
      issueMessages: props.isDirty
        ? []
        : issues.filter((issue) => issue.field === field.key).map((issue) => issue.message),
      save: onSave,
      lock: fieldLock(
        props.accepts.get(field.key),
        props.overriddenSourceValues[field.key],
        diffValue(newRecord ?? oldRecord, field),
      ),
      announcement: announcementFor(
        props.assertions,
        field.key,
        diffValue(newRecord ?? oldRecord, field),
      ),
      isReadOnly,
      jurisdictionOcdid,
      posts,
      derivedPost,
      onAddPost,
      focusRef: focus && field.key === focusKey ? focus.attach : null,
    });
  });
}

function renderStrip(props: PersonEditorProps) {
  const { status, oldRecord, newRecord, onToggleExpand, subtitle } = props;
  const record = newRecord ?? oldRecord;
  return html`
    <div class="person-editor person-editor--strip person-editor--${status}">
      <person-image
        .person=${withDisplayImage(record)}
        .size=${"2.75rem"}
      ></person-image>
      <span class="person-editor__name">${record?.name || "(unnamed)"}</span>
      <span class="person-editor__office">${subtitle || nothing}</span>
      <span class="person-editor__status">${STATUS_LABEL[status]}</span>
      <button class="person-editor__expander" @click=${onToggleExpand}>Show fields</button>
    </div>
    ${renderMergeCandidates(props)}
  `;
}

function renderNavHint(props: PersonEditorProps) {
  const hint = props.navHint;
  if (!hint || (!hint.hasPrev && !hint.hasNext)) return nothing;
  return html`
    <div class="person-editor__nav-hint">
      ${hint.hasPrev
        ? html`<span class="person-editor__nav-chip"
            ><kbd>Alt</kbd><kbd
              ><i class="fa-solid fa-arrow-left" aria-hidden="true"></i></kbd
            >
            previous</span
          >`
        : nothing}
      ${hint.hasNext
        ? html`<span class="person-editor__nav-chip"
            >next <kbd>Alt</kbd
            ><kbd><i class="fa-solid fa-arrow-right" aria-hidden="true"></i></kbd
          ></span>`
        : nothing}
    </div>
  `;
}

export function renderPersonEditor(props: PersonEditorProps) {
  const { status, frozenReasons, isExpanded, onToggleExpand } = props;
  const departing = DEPARTING.has(status);
  const visibleKeys = new Set(frozenReasons.keys());
  const hiddenCount = FIELD_SCHEMA.length - visibleKeys.size;
  const keys = isExpanded ? new Set(FIELD_SCHEMA.map((f) => f.key)) : visibleKeys;
  const hasReviewableField = FIELD_SCHEMA.some(
    (field) =>
      visibleKeys.has(field.key) &&
      (!isContextField(field) || frozenReasons.get(field.key) === "error"),
  );
  if (!departing && !hasReviewableField && !isExpanded) return renderStrip(props);
  return html`
    <div class="person-editor person-editor--${status}">
      ${renderMergeCandidates(props)} ${renderIdentity(props)}
      <div class="person-editor__fields">
        ${renderRowIssues(props)}
        ${departing
          ? renderBanner(props)
          : nothing}
        ${departing && !isExpanded ? nothing : renderFields(props, keys)}
        ${!departing && hiddenCount > 0
          ? html`<button class="person-editor__expander" @click=${onToggleExpand}>
              ${isExpanded
                ? "Hide unchanged fields"
                : `+ ${hiddenCount} unchanged field${hiddenCount === 1 ? "" : "s"}`}
            </button>`
          : nothing}
        ${renderNavHint(props)}
      </div>
    </div>
  `;
}