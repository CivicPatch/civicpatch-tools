import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { fetchChangeLogs } from "../../api.js";
import { Pagination } from "../../components/pagination/index.js";
import "./activity-page.css";

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

function renderChange(changes) {
  if (!changes) return html`<span class="activity-page__muted">—</span>`;
  return html`
    <div class="activity-page__change">
      <strong>${changes.person_name}</strong>
      <ul class="activity-page__fields">
        ${changes.fields.map(
          (f) => html`<li>
            <span class="activity-page__field-name">${f.field}</span>:
            <span class="activity-page__before">${formatValue(f.before)}</span> →
            <span class="activity-page__after">${formatValue(f.after)}</span>
          </li>`,
        )}
      </ul>
    </div>
  `;
}

function renderRow(entry) {
  return html`
    <tr>
      <td><span class="activity-page__type">${formatType(entry.type)}</span></td>
      <td>${entry.author_name} <span class="activity-page__muted">(${entry.author_role})</span></td>
      <td>${entry.jurisdiction_path
        ? html`<a href="/${entry.jurisdiction_path}" target="_blank" rel="noopener">${entry.jurisdiction_name}</a>`
        : (entry.jurisdiction_name ?? "—")}</td>
      <td>${renderChange(entry.changes)}</td>
      <td class="activity-page__date">${formatDate(entry.created_at)}</td>
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
          <th>Date</th>
        </tr>
      </thead>
      <tbody>
        ${entries.length === 0
          ? html`<tr><td colspan="5" class="activity-page__empty">${emptyText}</td></tr>`
          : entries.map(renderRow)}
      </tbody>
    </table>
  `;
}

function ActivityPage() {
  const [quarantine, setQuarantine] = useState([]);
  const [quarantineTotal, setQuarantineTotal] = useState(0);
  const [quarantinePage, setQuarantinePage] = useState(1);
  const [quarantineTotalPages, setQuarantineTotalPages] = useState(1);

  const [activity, setActivity] = useState([]);
  const [activityTotal, setActivityTotal] = useState(0);
  const [activityPage, setActivityPage] = useState(1);
  const [activityTotalPages, setActivityTotalPages] = useState(1);

  useEffect(() => {
    fetchChangeLogs("quarantine", quarantinePage, PER_PAGE)
      .then((r) => {
        setQuarantine(r.data || []);
        setQuarantineTotal(r.total_items || 0);
        setQuarantineTotalPages(r.total_pages || 1);
      })
      .catch(console.error);
  }, [quarantinePage]);

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
      <section class="activity-page__section">
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
      </section>

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

customElements.define("activity-page", component(ActivityPage, { useShadowDOM: false }));
