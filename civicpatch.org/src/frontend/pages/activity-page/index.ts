import "../../components/panel/panel.css";
import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { fetchChangeLogs } from "../../api.js";
import { Pagination } from "../../components/pagination/index.js";
import { FIELD_SCHEMA } from "../../components/fields/field-schema.js";
import "./activity-page.css";
import { jurisdictionOcdidToPath } from "../../components/ocdid-utils.js";

const PER_PAGE = 20;

function formatType(type) {
  return type.replace(/_/g, " ");
}

function formatDate(iso) {
  return new Date(iso).toLocaleString();
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

// Person edits get a field-level diff under the summary line; everything else
// relies on the server-rendered `summary` string alone.
function renderChange(entry) {
  if (entry.type !== "edit_person" || !entry.changes?.fields?.length) return null;
  return entry.changes.fields.map(
    (f) => html`
      <div class="activity-row__field">
        <span class="activity-row__field-name">${fieldLabel(f.field)}</span>
        <span class="activity-row__before">${formatValue(f.before)}</span>
        <span class="activity-row__arrow">→</span>
        <span class="activity-row__after">${formatValue(f.after)}</span>
      </div>`,
  );
}

// A row, not a table row: every column but the summary is a fixed width, and the
// field diff needs to sit under the head rather than inside a cell.
function renderRow(entry) {
  return html`
    <div class="activity-row">
      <div class="activity-row__head">
        <span class="activity-row__type">${formatType(entry.type)}</span>
        <span class="activity-row__who">
          ${entry.author_name}
          <span class="activity-row__role">${entry.author_role}</span>
        </span>
        <span class="activity-row__what">
          ${entry.jurisdiction_path
            ? html`<a href="/${jurisdictionOcdidToPath(entry.jurisdiction_path)}" target="_blank" rel="noopener">${entry.jurisdiction_name}</a>`
            : (entry.jurisdiction_name ?? "")}
          <span class="activity-row__summary">${entry.summary}</span>
        </span>
        ${entry.pull_request_url
          ? html`<a class="activity-row__pr" href=${entry.pull_request_url} target="_blank" rel="noopener">PR</a>`
          : html`<span></span>`}
        <!-- Masked in the visual suite: seeded with NOW(), so it renders the day
             the run happens on and would rot the baseline overnight. -->
        <span class="activity-row__at" data-visual-volatile>${formatDate(entry.created_at)}</span>
      </div>
      ${renderChange(entry)}
    </div>
  `;
}

// No header row: with five columns, four of which are self-evident from their own
// formatting, a header costs a line and tells the reader nothing they cannot see.
function renderList(entries, emptyText) {
  return entries.length === 0
    ? html`<p class="activity-page__empty">${emptyText}</p>`
    : entries.map(renderRow);
}

function ActivityPage({ user }) {
  let canViewQuarantine = false;
  try {
    const parsed = user ? JSON.parse(user) : null;
    canViewQuarantine = !!parsed?.permissions?.can_view_quarantine;
  } catch (_e) {
    /* leave false */
  }

  const [quarantine, setQuarantine] = useState([]);
  const [quarantineTotal, setQuarantineTotal] = useState(0);
  const [quarantinePage, setQuarantinePage] = useState(1);
  const [quarantineTotalPages, setQuarantineTotalPages] = useState(1);

  const [activity, setActivity] = useState([]);
  const [activityTotal, setActivityTotal] = useState(0);
  const [activityPage, setActivityPage] = useState(1);
  const [activityTotalPages, setActivityTotalPages] = useState(1);

  useEffect(() => {
    if (!canViewQuarantine) return;
    fetchChangeLogs("quarantine", quarantinePage, PER_PAGE)
      .then((r) => {
        setQuarantine(r.data || []);
        setQuarantineTotal(r.total_items || 0);
        setQuarantineTotalPages(r.total_pages || 1);
      })
      .catch(console.error);
  }, [quarantinePage, canViewQuarantine]);

  useEffect(() => {
    fetchChangeLogs("activity", activityPage, PER_PAGE)
      .then((r) => {
        setActivity(r.data || []);
        setActivityTotal(r.total_items || 0);
        setActivityTotalPages(r.total_pages || 1);
      })
      .catch(console.error);
  }, [activityPage]);

  return html`
    <main class="activity-page page-content">
      <div class="page-focal">
        <h1 class="page-focal__title">Activity</h1>
      </div>

      ${canViewQuarantine
        ? html`<section class="panel activity-page__section">
            <div class="panel__cap">
              <b>quarantine</b>
              <span class="panel__cap-right">${quarantineTotal || ""}</span>
            </div>
            <p class="activity-page__subtitle">Changes from untrusted (default-role) contributors — review for spam or profanity.</p>
            ${renderList(quarantine, "Nothing awaiting review.")}
            ${Pagination({
              page: quarantinePage,
              totalPages: quarantineTotalPages,
              onPrevious: () => setQuarantinePage(quarantinePage - 1),
              onNext: () => setQuarantinePage(quarantinePage + 1),
              perPage: PER_PAGE,
              onPerPageChange: undefined,
            })}
          </section>`
        : ""}

      <section class="panel activity-page__section">
        <div class="panel__cap">
          <b>change log</b>
          <span class="panel__cap-right">${activityTotal || ""}</span>
        </div>
        <p class="activity-page__subtitle">Changes from trusted contributors and up.</p>
        ${renderList(activity, "No changes yet.")}
        ${Pagination({
          page: activityPage,
          totalPages: activityTotalPages,
          onPrevious: () => setActivityPage(activityPage - 1),
          onNext: () => setActivityPage(activityPage + 1),
          perPage: PER_PAGE,
          onPerPageChange: undefined,
        })}
      </section>
    </main>
  `;
}

customElements.define("activity-page", component(ActivityPage, { useShadowDOM: false, observedAttributes: ["user"] }));
