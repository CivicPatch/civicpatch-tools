import "./people-diff.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { computePeopleDiff, DiffType } from "../../utils/diff-utils.js";
import { FIELD_SCHEMA, recordsDiffer, foldDeletions, buildLinkUpdates, indexIssuesByPersonId, type Issue } from "./diff-model.js";
import { renderField, copyArrow, DASH, type Save } from "./field-renderers.js";

// "all" = the no-filter chip; "deleted" = a UI-only card status (a deleted
// ghost), not one of computePeopleDiff's DiffType values.
const FILTER_ALL = "all";
const STATUS_DELETED = "deleted";

type FilterKey = typeof FILTER_ALL | (typeof DiffType)[keyof typeof DiffType];

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: FILTER_ALL, label: "All" },
  { key: DiffType.CHANGED, label: "Changed" },
  { key: DiffType.ADDED, label: "New" },
  { key: DiffType.REMOVED, label: "Removed" },
  { key: DiffType.UNCHANGED, label: "Unchanged" },
];

interface PeopleDiffProps {
  existing: any[];
  currentPeople: any[];
  issues?: Issue[];
  onPersonSave: (id: string, updates: Record<string, unknown>) => void;
  onAdd?: () => void;
  onResetPerson?: (id: string) => void;
  onDeletePerson: (id: string) => void;
  onRestorePerson: (id: string) => void;
  jurisdictionOcdid?: string | null;
  isReadOnly?: boolean;
  // Which people the reviewer has edited, and which are being dropped on
  // publish — both derived by usePeopleState from the baseline, so neither
  // lives on the records themselves.
  dirtyIds: Set<string>;
  deletedIds: Set<string>;
}

// "Link to person": an unmatched scraped person is actually one of the removed
// (old-side, no longer scraped) people. Picking one links them — see buildLinkUpdates.
function linkSelect(candidates: any[], onLink: (target: any) => void) {
  const choose = (e: Event) => {
    const target = candidates.find((c) => c.id === (e.target as HTMLSelectElement).value);
    if (target) onLink(target);
  };
  return html`<select class="people-diff__link" aria-label="Link to an existing person" @change=${choose}>
    <option value="">Link to person…</option>
    ${candidates.map((c) => html`<option value=${c.id}>${c.name || "(unnamed)"}${c.office?.name ? ` — ${c.office.name}` : ""}</option>`)}
  </select>`;
}

function renderIssueMarkers(issues: Issue[]) {
  if (!issues.length) return "";
  return html`<div class="people-diff__issues">
    ${issues.map((issue) => html`<div class="people-diff__issue">
      <i class="fa-solid fa-triangle-exclamation people-diff__issue-icon"></i>
      <span>${issue.message}</span>
    </div>`)}
  </div>`;
}

// Everything a row needs that is the same for every row. Grouped because it is
// nine values — passing them positionally made the call site unreadable.
interface RowContext {
  onPersonSave: PeopleDiffProps["onPersonSave"];
  onResetPerson: PeopleDiffProps["onResetPerson"];
  onDeletePerson: PeopleDiffProps["onDeletePerson"];
  onRestorePerson: PeopleDiffProps["onRestorePerson"];
  isReadOnly: boolean;
  jurisdictionOcdid: string | null | undefined;
  linkCandidates: any[];
  dirtyIds: Set<string>;
  deletedIds: Set<string>;
}

function renderRow(
  status: string,
  oldRecord: any,
  newRecord: any,
  issues: Issue[],
  ctx: RowContext,
) {
  const { onPersonSave, onResetPerson, onDeletePerson, onRestorePerson } = ctx;
  const { isReadOnly, jurisdictionOcdid, linkCandidates, dirtyIds, deletedIds } = ctx;
  const name = newRecord?.name || oldRecord?.name || DASH;
  const save: Save = (updates) => onPersonSave(newRecord.id, updates);
  const isDirty = dirtyIds.has(newRecord?.id);
  const isDeleted = deletedIds.has(newRecord?.id);
  // Clear-on-edit: once the reviewer touches (or deletes) a card, its markers
  // are presumed addressed and drop away. Field-less issues render at row level;
  // field-anchored ones render under their field.
  const showMarkers = !isDirty && !isDeleted;
  const rowIssues = showMarkers ? issues.filter((issue) => !issue.field) : [];
  // A deleted person stays in its slot as a struck-through ghost (omitted on
  // publish, so the record is dropped); Undo restores it. Removed people
  // (scrape-dropped, no new-side record) aren't deletable here.
  const canDelete = !isReadOnly && status !== DiffType.REMOVED && !!newRecord && !isDeleted;
  const displayStatus = isDeleted ? STATUS_DELETED : status;
  const handleDelete = () => onDeletePerson(newRecord.id);
  const handleUndo = () => onRestorePerson(newRecord.id);
  const handleLink = (target: any) => save(buildLinkUpdates(newRecord, target));
  const canLink = status === DiffType.ADDED && !isReadOnly && linkCandidates.length > 0;
  // A removed person has no new-side record — render the fields with a null new
  // record so each shows old (struck) → "—", same as every other card's grid.
  const fieldNewRecord = status === DiffType.REMOVED ? null : newRecord;
  return html`
    <div class="people-diff__person people-diff__person--${displayStatus}">
      <div class="people-diff__person-header">
        <div class="people-diff__hdr-main">
          <span class="people-diff__status">${displayStatus}</span>
          <span class="people-diff__name">${name}</span>
        </div>
        <div class="people-diff__gutter">
          ${copyArrow(status === DiffType.CHANGED && !isReadOnly && !isDeleted, () => save({ ...oldRecord, id: newRecord.id }))}
        </div>
        <div class="people-diff__row-actions">
          ${isDeleted
            ? html`<button class="people-diff__undo btn-sm" @click=${handleUndo}>Undo</button>`
            : html`${canLink ? linkSelect(linkCandidates, handleLink) : ""}
              ${isDirty && !isReadOnly && onResetPerson
                ? html`<button class="people-diff__reset btn-sm" @click=${() => onResetPerson(newRecord.id)}>Reset</button>`
                : ""}
              ${canDelete
                ? html`<button class="people-diff__delete btn-ghost" @click=${handleDelete}>Delete</button>`
                : ""}`}
        </div>
      </div>
      ${renderIssueMarkers(rowIssues)}
      <div class="people-diff__fields">
        ${FIELD_SCHEMA.map((field) => html`
          ${renderField(field, oldRecord, fieldNewRecord, save, isReadOnly, jurisdictionOcdid)}
          ${renderIssueMarkers(showMarkers ? issues.filter((issue) => issue.field === field.key) : [])}
        `)}
      </div>
    </div>
  `;
}

function PeopleDiff({ existing, currentPeople, issues = [], onPersonSave, onAdd, onResetPerson, onDeletePerson, onRestorePerson, jurisdictionOcdid, isReadOnly = false, dirtyIds, deletedIds }: PeopleDiffProps) {
  const [activeFilter, setActiveFilter] = useState<FilterKey>(FILTER_ALL);

  const olds = Array.isArray(existing) ? existing : [];
  const news = Array.isArray(currentPeople) ? currentPeople : [];

  const issuesByPersonId = indexIssuesByPersonId(issues);
  // Fold the reviewer's deletions in before counting or filtering — otherwise a
  // deleted-but-otherwise-unchanged person is counted as Unchanged and never
  // appears under the Removed chip.
  const { diffEntries, unchangedEntries } = foldDeletions(
    computePeopleDiff(olds, news, recordsDiffer),
    deletedIds,
  );

  const counts: Record<FilterKey, number> = {
    [FILTER_ALL]: diffEntries.length + unchangedEntries.length,
    [DiffType.CHANGED]: diffEntries.filter((e) => e.type === DiffType.CHANGED).length,
    [DiffType.ADDED]: diffEntries.filter((e) => e.type === DiffType.ADDED).length,
    [DiffType.REMOVED]: diffEntries.filter((e) => e.type === DiffType.REMOVED).length,
    [DiffType.UNCHANGED]: unchangedEntries.length,
  };

  // Candidates for "Link to person" on an added card: the removed (old-side,
  // unmatched) people, whose entry carries the existing record as `person`.
  //
  // Deleted people are excluded even though foldDeletions types them REMOVED.
  // Linking adopts the target's id, so linking to someone the reviewer is
  // dropping would hand the added person an id that is already in deletedIds —
  // silently deleting them too. "Drop this person" and "this person is actually
  // that one" are contradictory answers to the same question; undo the deletion
  // first.
  const linkCandidates = diffEntries
    .filter((e) => e.type === DiffType.REMOVED && !deletedIds.has(e.person?.id))
    .map((e) => e.person);

  // Preserve list order: each card keeps its currentPeople slot, so editing a
  // person never re-sorts the list out from under the reviewer. Newly-added
  // people are prepended to currentPeople, so they land at the top. Removed
  // people (scrape-dropped, not in the list) trail at the end.
  const newsIndex = new Map(news.map((p, i) => [p?.id, i]));
  const matchesFilter = (type: string) => activeFilter === FILTER_ALL || activeFilter === type;
  const ordered = [...diffEntries, ...unchangedEntries].sort((a, b) => {
    const ai = newsIndex.get(a.person?.id);
    const bi = newsIndex.get(b.person?.id);
    if (ai === undefined) return bi === undefined ? 0 : 1;
    if (bi === undefined) return -1;
    return ai - bi;
  });
  const visible = ordered.filter((e) => matchesFilter(e.type));

  const rowContext: RowContext = {
    onPersonSave, onResetPerson, onDeletePerson, onRestorePerson,
    isReadOnly, jurisdictionOcdid, linkCandidates, dirtyIds, deletedIds,
  };

  if (counts.all === 0) {
    return html`<div class="people-diff">
      <div class="people-diff__header"><div class="people-diff__header-title">Officials list diff</div></div>
      <p class="people-diff__empty">No people to review.</p>
    </div>`;
  }

  return html`
    <div class="people-diff">
      <div class="people-diff__header">
        <div class="people-diff__header-title-row">
          <div class="people-diff__header-title">Officials list diff</div>
          ${!isReadOnly && onAdd
            ? html`<button class="people-diff__add-person btn-sm" @click=${onAdd}>+ Add person</button>`
            : ""}
        </div>
        <div class="people-diff__count-chips">
          ${FILTERS.map(
            (f) => html`
              <button
                class="people-diff__chip people-diff__chip--${f.key} ${activeFilter === f.key ? "people-diff__chip--active" : ""}"
                @click=${() => setActiveFilter(f.key)}
              >
                ${f.label}
                ${counts[f.key] > 0 ? html`<span class="people-diff__chip-count">${counts[f.key]}</span>` : ""}
              </button>
            `,
          )}
        </div>
      </div>
      <div class="people-diff__legend">
        <span>Old</span>
        <span>New — editable</span>
      </div>
      <div class="people-diff__rows">
        ${visible.map(({ type, person, from }) =>
          renderRow(type, from, person, issuesByPersonId.get(person?.id) ?? [], rowContext))}
      </div>
    </div>
  `;
}

customElements.define("people-diff", component(PeopleDiff, { useShadowDOM: false }));
