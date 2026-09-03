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

// Person edits get a field-level diff expander; everything else relies on the
// server-rendered `summary` string.
function renderChange(entry) {
  if (entry.type === "edit_person" && entry.changes?.fields?.length) {
    return html`
      <div class="activity-page__change">
        <ul class="activity-page__fields">
          ${entry.changes.fields.map(
            (f) => html`<li>
              <span class="activity-page__field-name">${fieldLabel(f.field)}</span>:
              <span class="activity-page__before">${formatValue(f.before)}</span> →
              <span class="activity-page__after">${formatValue(f.after)}</span>
            </li>`,
          )}
        </ul>
      </div>
    `;
  }
  return html`<span class="activity-page__muted">—</span>`;
}

function renderRow(entry) {
  return html`
    <tr>
      <td><span class="activity-page__type">${formatType(entry.type)}</span></td>
      <td>${entry.author_name} <span class="activity-page__muted">(${entry.author_role})</span></td>
      <td>${entry.jurisdiction_path
        ? html`<a href="/${jurisdictionOcdidToPath(entry.jurisdiction_path)}" target="_blank" rel="noopener">${entry.jurisdiction_name}</a>`
        : (entry.jurisdiction_name ?? "—")}</td>
      <td>
        <div class="activity-page__summary">${entry.summary}</div>
        ${renderChange(entry)}
      </td>
      <td>${entry.pull_request_url
        ? html`<a href=${entry.pull_request_url} target="_blank" rel="noopener">PR</a>`
        : html`<span class="activity-page__muted">—</span>`}</td>
      <!-- Masked in the visual suite: seeded with NOW(), so it renders the day
           the run happens on and would rot the baseline overnight. -->
      <td class="activity-page__date" data-visual-volatile>${formatDate(entry.created_at)}</td>
    </tr>
  `;
}

function renderTable(entries, emptyText) {
  return html`
    <table class="activity-page__table">
      <thead>
        <tr>
          <th>Type</th>
          <th>Author</th>
          <th>Jurisdiction</th>
          <th>Change</th>
          <th>PR</th>
          <th>Date</th>
        </tr>
      </thead>
      <tbody>
        ${entries.length === 0
          ? html`<tr><td colspan="6" class="activity-page__empty">${emptyText}</td></tr>`
          : entries.map(renderRow)}
      </tbody>
    </table>
  `;
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
      ${canViewQuarantine
        ? html`<section class="activity-page__section">
            <div class="section-header">
              <h2 class="section-title section-title--warning">
                Quarantine <span class="section-count">${quarantineTotal || ""}</span>
              </h2>
            </div>
            <p class="activity-page__subtitle">Changes from untrusted (default-role) contributors — review for spam or profanity.</p>
            ${renderTable(quarantine, "Nothing awaiting review.")}
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

      <section class="activity-page__section">
        <div class="section-header">
          <h2 class="section-title section-title--info">
            Change log <span class="section-count">${activityTotal || ""}</span>
          </h2>
        </div>
        <p class="activity-page__subtitle">Changes from trusted contributors and up.</p>
        ${renderTable(activity, "No changes yet.")}
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
