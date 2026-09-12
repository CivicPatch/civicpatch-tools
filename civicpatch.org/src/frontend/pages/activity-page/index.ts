import "../../components/panel/panel.css";
import { html, nothing } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { ref } from "lit/directives/ref.js";
import { fetchChangeLogs } from "../../api.js";
import { Pagination } from "../../components/pagination/index.js";
import { usePagerRef } from "../../hooks/use-pager-ref.js";
import {
  SectionNav,
  ACTIVITY_SECTION,
} from "../../components/section-nav/index.js";
import { FIELD_SCHEMA } from "../../components/fields/field-schema.js";
import "./activity-page.css";
import { jurisdictionOcdidToPath } from "../../components/ocdid-utils.js";
import { useAuth } from "../../hooks/useAuth.js";
import { authorDisplayMode } from "../home-page/recent-activity.js";
import { formatDateTime } from "../../utils/date-utils.js";

const PER_PAGE = 50;

// Mirrors ActivityAuthors on the API.
const AUTHORS_ALL = "all";
const AUTHORS_QUARANTINED = "quarantined";

// The author role whose changes are unreviewed. `author_role` is already on every entry, so the
// feed can mark them in place instead of asking for a second list.
const QUARANTINED_ROLE = "default";

function formatType(type) {
  return type.replace(/_/g, " ");
}

function formatValue(value) {
  if (value == null) return "∅";
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}

// The editor's own label, so the feed says "Post" where the editor said "Post". Falls back to
// the key for anything the schema does not name — a field can be logged without being editable.
const fieldLabel = (key: string) =>
  FIELD_SCHEMA.find((field) => field.key === key)?.label ?? key;

// GitHub's label/assignee events, applied to list fields: only the items that actually moved
// render, as removed/added chips — never the whole list twice, so an unrelated unchanged
// member (most of `emails`, say) never has to be read to find the one that changed.
function diffListItems(before, after) {
  const beforeList = Array.isArray(before) ? before : [];
  const afterList = Array.isArray(after) ? after : [];
  return {
    removed: beforeList.filter((v) => !afterList.includes(v)),
    added: afterList.filter((v) => !beforeList.includes(v)),
  };
}

// A scalar field, GitHub's own edit-history phrasing: the whole old value struck through next
// to the whole new one — always visible, nothing hidden regardless of how much changed.
function renderScalarDiff(f) {
  return html`
    <span class="activity-row__diff">
      <span class="activity-row__before">${formatValue(f.before)}</span>
      <span class="activity-row__arrow"
        ><i class="fa-solid fa-arrow-right" aria-hidden="true"></i
      ></span>
      <span class="activity-row__after">${formatValue(f.after)}</span>
    </span>
  `;
}

function renderListDiff(f) {
  const { removed, added } = diffListItems(f.before, f.after);
  return html`
    <span class="activity-row__diff">
      ${removed.map(
        (v) =>
          html`<span class="chip activity-row__chip--removed">${v}</span>`,
      )}
      ${added.map(
        (v) => html`<span class="chip activity-row__chip--added">${v}</span>`,
      )}
    </span>
  `;
}

// Person edits get a field-level diff under the summary line; everything else
// relies on the server-rendered `summary` string alone. A publish_review row carries one too
// when it's a hand edit's own publish (see roster_edits.edit_published) rather than a plain
// scrape-review approval, which never has a payload.
const FIELD_DIFF_TYPES = new Set(["edit_person", "publish_review"]);

function renderChange(entry) {
  if (!FIELD_DIFF_TYPES.has(entry.type) || !entry.changes?.fields?.length)
    return nothing;
  return entry.changes.fields.map((f) => {
    const isList = Array.isArray(f.before) || Array.isArray(f.after);
    return html` <div class="activity-row__field">
      <span class="activity-row__field-name">${fieldLabel(f.field)}</span>
      ${isList ? renderListDiff(f) : renderScalarDiff(f)}
    </div>`;
  });
}

// A row, not a table row: every column but the summary is a fixed width, and the
// field diff needs to sit under the head rather than inside a cell.
function renderRow(entry, markQuarantined: boolean, canViewProfiles: boolean) {
  const quarantined = markQuarantined && entry.author_role === QUARANTINED_ROLE;
  const authorMode = authorDisplayMode(entry.is_system, canViewProfiles);
  return html`
    <div class="activity-row ${quarantined ? "activity-row--quarantined" : ""}">
      <div class="activity-row__head">
        <span class="activity-row__type">${formatType(entry.type)}</span>
        <span class="activity-row__who">
          ${authorMode === "link"
            ? html`<a href="/~${entry.author_name}">${entry.author_name}</a>`
            : authorMode === "text"
              ? entry.author_name
              : ""}
          <span class="activity-row__role">${entry.author_role}</span>
        </span>
        <span class="activity-row__what">
          ${entry.jurisdiction_path
            ? html`<a
                href="/${jurisdictionOcdidToPath(entry.jurisdiction_path)}"
                target="_blank"
                rel="noopener"
                >${entry.jurisdiction_name}</a
              >`
            : (entry.jurisdiction_name ?? "")}
          <span class="activity-row__summary">${entry.summary}</span>
        </span>
        ${entry.pull_request_url
          ? html`<a
              class="activity-row__pr"
              href=${entry.pull_request_url}
              target="_blank"
              rel="noopener"
              >commit</a
            >`
          : html`<span></span>`}
        <!-- Masked in the visual suite: seeded with NOW(), so it renders the day
             the run happens on and would rot the baseline overnight. -->
        <span class="activity-row__at" data-visual-volatile
          >${formatDateTime(entry.created_at)}</span
        >
      </div>
      ${renderChange(entry)}
    </div>
  `;
}

// A sibling of the row list, not its first child: `.activity-row:nth-child(even)` stripes
// by position within `.activity-row-list`, so a header sharing that parent would shift every
// row's parity and flip the stripe.
function renderHeader() {
  return html`
    <div class="activity-row-list__head">
      <span>type</span><span>who</span><span>what</span><span></span
      ><span>at</span>
    </div>
  `;
}

function renderList(
  entries,
  markQuarantined: boolean,
  canViewProfiles: boolean,
) {
  // A wrapper of its own — not just mapped siblings — so `.activity-row:last-child` in CSS
  // actually lands on the last row: Pagination sits after this in the DOM, and without a
  // wrapper it would be the true last child instead, so no row's own border ever cleared.
  return entries.length === 0
    ? html`<p class="activity-page__empty">No changes yet.</p>`
    : html`<div class="activity-row-list">
        ${entries.map((entry) =>
          renderRow(entry, markQuarantined, canViewProfiles),
        )}
      </div>`;
}

function ActivityPage() {
  const { permissions } = useAuth();
  const canViewProfiles = !!permissions?.can_manage_roles;
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [quarantinedOnly, setQuarantinedOnly] = useState(false);
  const { listRef, scrollToTop } = usePagerRef<HTMLElement>();

  useEffect(() => {
    fetchChangeLogs(
      quarantinedOnly ? AUTHORS_QUARANTINED : AUTHORS_ALL,
      page,
      PER_PAGE,
    )
      .then((r) => {
        setEntries(r.data || []);
        setTotal(r.total_items || 0);
        setTotalPages(r.total_pages || 1);
      })
      .catch(console.error);
  }, [page, quarantinedOnly]);

  const toggleQuarantinedOnly = () => {
    setQuarantinedOnly(!quarantinedOnly);
    setPage(1);
  };

  // Built once so Next/Previous re-orients to the top of the panel either way — clicking
  // the bottom pager most often leaves the reader below what just changed above them.
  const pager = Pagination({
    page,
    totalPages,
    onPrevious: () => {
      setPage(page - 1);
      scrollToTop();
    },
    onNext: () => {
      setPage(page + 1);
      scrollToTop();
    },
    perPage: PER_PAGE,
    onPerPageChange: undefined,
  });

  return html`
    <main class="activity-page page-content">
      <div class="page-focal">
        <h1 class="page-focal__title">All activity</h1>
      </div>

      <div class="sectioned">
        ${SectionNav("activity", ACTIVITY_SECTION, "/activity/all-activity")}
        <div class="secbody">
          <section class="panel activity-page__section" ${ref(listRef)}>
            <div class="panel__cap">
              <span class="panel__cap-right">
                <label class="activity-page__filter">
                  <input
                    type="checkbox"
                    .checked=${quarantinedOnly}
                    @change=${toggleQuarantinedOnly}
                  />
                  quarantined only
                </label>
                ${total || ""}
              </span>
            </div>
            ${pager}
            ${entries.length > 0 ? renderHeader() : ""}
            ${renderList(entries, !quarantinedOnly, canViewProfiles)}
            ${pager}
          </section>
        </div>
      </div>
    </main>
  `;
}

customElements.define(
  "activity-page",
  component(ActivityPage, { useShadowDOM: false }),
);
