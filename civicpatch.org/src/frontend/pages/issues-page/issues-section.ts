import "../../components/panel/panel.css";
import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { ref } from "lit/directives/ref.js";
import { fetchJobIssues, fetchIssueCounts, flagIssue, dismissIssues } from "../../api.js";
import { Pagination } from "../../components/pagination/index.js";
import { usePagerRef } from "../../hooks/use-pager-ref.js";
import { KNOWN_ISSUE_TYPES } from "../../utils/issue-types.js";
import { DANGER_VARIANT } from "../../components/confirm-modal/confirm-modal.js";
import { IssueRow, PENDING, type Issue } from "./issue-row.js";
import { SECTIONS } from "./issue-sections.js";
import "./dismiss-modal.js";
import "./resolve-modal.js";

const SECTION_TOGGLE_EVENT = "section-toggle";
const DEFAULT_PER_PAGE = 20;
const PER_PAGE_OPTIONS = [10, 20, 50, 100];

// Each section prefixes its own, so one link can carry both sections' state.
const PAGE = "page";
const PER_PAGE = "per_page";
const TAGS = "tags";
const SORT = "sort";

type SectionHost = HTMLElement & { kind: string; stateCode: string; open: boolean };

function readParam(name: string, fallback = "") {
  return new URLSearchParams(window.location.search).get(name) ?? fallback;
}

function setParams(entries: Record<string, string | null>) {
  const params = new URLSearchParams(window.location.search);
  for (const [key, value] of Object.entries(entries)) {
    if (value === null) params.delete(key);
    else params.set(key, value);
  }
  window.history.pushState({}, "", `${window.location.pathname}?${params}`);
}

function IssuesSection(host: SectionHost) {
  const { kind, stateCode, open } = host;
  const config = SECTIONS[kind];
  const key = (name: string) => `${config.urlPrefix}_${name}`;

  const [issues, setIssues] = useState<Issue[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(() => Math.max(1, parseInt(readParam(key(PAGE), "1"), 10) || 1));
  const [perPage, setPerPage] = useState(() => {
    const stored = parseInt(readParam(key(PER_PAGE)), 10);
    return PER_PAGE_OPTIONS.includes(stored) ? stored : DEFAULT_PER_PAGE;
  });
  const [tagFilter, setTagFilter] = useState<string[]>(
    () => readParam(key(TAGS)).split(",").filter(Boolean),
  );
  const [sortDesc, setSortDesc] = useState(() => readParam(key(SORT)) !== "asc");
  const [showArchived, setShowArchived] = useState(false);
  const [loading, setLoading] = useState(false);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [selected, setSelected] = useState<string[]>([]);
  const [bulkPending, setBulkPending] = useState(false);
  const [confirmingBulk, setConfirmingBulk] = useState(false);
  const [detailsIssue, setDetailsIssue] = useState<Issue | null>(null);
  const [dismissIssue, setDismissIssue] = useState<Issue | null>(null);
  const { listRef: sectionRef, scrollToTop } = usePagerRef<HTMLElement>();

  useEffect(() => {
    if (!config.typeFilters) return;
    fetchIssueCounts(stateCode, kind).then((r) => setCounts(r.data || {})).catch(() => {});
  }, [stateCode]);

  const load = () => {
    setLoading(true);
    // Selection is page-scoped: whatever the list becomes, nothing invisible stays checked.
    setSelected([]);
    fetchJobIssues(tagFilter, page, perPage, sortDesc ? "desc" : "asc", stateCode, showArchived, kind)
      .then((r) => { setIssues(r.data || []); setTotal(r.total || 0); })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!open) return;
    load();
  }, [open, page, perPage, tagFilter, sortDesc, stateCode, showArchived]);

  const selectable = issues.filter((i) => i.status === PENDING);
  const allSelected = selectable.length > 0 && selected.length === selectable.length;

  const rowHandlers = {
    cells: config.cells,
    isSelected: (issue: Issue) => selected.includes(issue.id),
    onSelect: (issue: Issue) =>
      setSelected(
        selected.includes(issue.id)
          ? selected.filter((s) => s !== issue.id)
          : [...selected, issue.id],
      ),
    onFlag: (issue: Issue, is_flagged: boolean) => {
      setIssues(issues.map((i) => (i.id === issue.id ? { ...i, is_flagged } : i)));
      flagIssue(issue.id, is_flagged).catch(() => {
        setIssues(issues.map((i) => (i.id === issue.id ? { ...i, is_flagged: !is_flagged } : i)));
      });
    },
    onDetails: setDetailsIssue,
    onDismiss: setDismissIssue,
  };

  const handleDismissed = (e: CustomEvent) => {
    setDismissIssue(null);
    setIssues(issues.filter((i) => i.id !== e.detail.issue_id));
    setTotal(total - 1);
  };

  const handleBulkDismiss = async () => {
    setBulkPending(true);
    try {
      await dismissIssues(selected);
      setConfirmingBulk(false);
      // Reload rather than splice, so the page refills from what is left.
      load();
    } catch (err) {
      console.error("Failed to dismiss issues:", err);
    } finally {
      setBulkPending(false);
    }
  };

  const goToPage = (next: number) => {
    setPage(next);
    setParams({ [key(PAGE)]: String(next) });
    scrollToTop();
  };

  const applyFilters = (next: { tags?: string[]; sort?: boolean; perPage?: number }) => {
    const tags = next.tags ?? tagFilter;
    const sort = next.sort ?? sortDesc;
    const size = next.perPage ?? perPage;
    setTagFilter(tags);
    setSortDesc(sort);
    setPerPage(size);
    setPage(1);
    setParams({
      [key(PAGE)]: "1",
      [key(PER_PAGE)]: String(size),
      [key(TAGS)]: tags.length ? tags.join(",") : null,
      [key(SORT)]: sort ? "desc" : "asc",
    });
  };

  const tagChips = KNOWN_ISSUE_TYPES.map(({ value, label }) => {
    const active = tagFilter.includes(value);
    const next = active ? tagFilter.filter((t) => t !== value) : [...tagFilter, value];
    return html`
      <button
        class="issues-page__issue-tag${active ? " issues-page__issue-tag--active" : ""}"
        @click=${() => applyFilters({ tags: next })}
      >${label}${counts[value] ? html` <span class="issues-page__issue-tag-count">${counts[value]}</span>` : ""}${active ? html` <span class="issues-page__issue-tag-x">×</span>` : ""}</button>
    `;
  });

  const filters = html`
    <div class="issues-page__issues-filters">
      ${config.typeFilters ? html`<div class="issues-page__issue-tags">${tagChips}</div>` : null}
      <button class="btn btn-sm issues-page__sort-btn" @click=${() => applyFilters({ sort: !sortDesc })}>${sortDesc ? "Newest ↓" : "Oldest ↑"}</button>
      <button class="btn btn-sm" @click=${() => { setShowArchived(!showArchived); setPage(1); }}>${showArchived ? "← Active" : "Archived"}</button>
    </div>
    ${selected.length
      ? html`
        <div class="issues-page__bulk-bar">
          <span>${selected.length} selected on this page</span>
          <button class="btn btn-sm destructive" @click=${() => setConfirmingBulk(true)}>
            Dismiss ${selected.length} selected
          </button>
        </div>
      `
      : null}
  `;

  // Built once so Next/Previous re-orients to the top of the table either way — clicking
  // the bottom pager most often leaves the reader below what just changed above them.
  const pagerControls = html`
    <div class="issues-page__top-controls">
      <div class="issues-page__pagination">
        ${Pagination({
          page,
          totalPages: Math.ceil(total / perPage),
          onPrevious: () => goToPage(page - 1),
          onNext: () => goToPage(page + 1),
        })}
      </div>
      <label class="issues-page__per-page">
        Per page
        <select @change=${(e: Event) => applyFilters({ perPage: parseInt((e.target as HTMLSelectElement).value, 10) })}>
          ${PER_PAGE_OPTIONS.map((n) => html`<option value=${n} ?selected=${n === perPage}>${n}</option>`)}
        </select>
      </label>
    </div>
  `;

  const table = html`
    ${pagerControls}
    <table class="issues-page__issues-table">
      <thead>
        <tr>
          <th class="issues-page__issue-select">
            <input
              type="checkbox"
              .checked=${allSelected}
              ?disabled=${selectable.length === 0}
              @change=${() => setSelected(allSelected ? [] : selectable.map((i) => i.id))}
              aria-label="Select every issue on this page"
            />
          </th>
          ${config.columns.map((c) => html`<th>${c}</th>`)}
          <th>Jurisdiction</th>
          <th class="issues-page__issue-flag">Flagged</th>
          <th>Date</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${issues.length === 0
          ? html`<tr><td colspan=${config.columns.length + 5}>${config.empty}</td></tr>`
          : issues.map((issue) => IssueRow(issue, rowHandlers))}
      </tbody>
    </table>
    <div class="issues-page__top-controls">
      <div class="issues-page__pagination">
        ${Pagination({
          page,
          totalPages: Math.ceil(total / perPage),
          onPrevious: () => goToPage(page - 1),
          onNext: () => goToPage(page + 1),
        })}
      </div>
      <label class="issues-page__per-page">
        Per page
        <select @change=${(e: Event) => applyFilters({ perPage: parseInt((e.target as HTMLSelectElement).value, 10) })}>
          ${PER_PAGE_OPTIONS.map((n) => html`<option value=${n} ?selected=${n === perPage}>${n}</option>`)}
        </select>
      </label>
    </div>
  `;

  const modals = html`
    ${detailsIssue
      ? html`<issues-resolve-modal
          .issue=${detailsIssue}
          ?details-only=${true}
          @modal-close=${() => setDetailsIssue(null)}
        ></issues-resolve-modal>`
      : null}
    ${dismissIssue
      ? html`<issues-dismiss-modal
          .issue=${dismissIssue}
          @modal-close=${() => setDismissIssue(null)}
          @issue-dismissed=${handleDismissed}
        ></issues-dismiss-modal>`
      : null}
    ${confirmingBulk
      ? html`<civ-confirm-modal
          .title=${`Dismiss ${selected.length} issues`}
          .message=${`${config.consequence} This cannot be undone from here.`}
          .confirmLabel=${bulkPending ? "Dismissing…" : `Dismiss ${selected.length}`}
          .variant=${DANGER_VARIANT}
          @confirm=${handleBulkDismiss}
          @cancel=${() => setConfirmingBulk(false)}
        ></civ-confirm-modal>`
      : null}
  `;

  return html`
    <section class="panel issues-page__section" ${ref(sectionRef)}>
      <div class="panel__cap issues-page__cap" @click=${() => host.dispatchEvent(new CustomEvent(SECTION_TOGGLE_EVENT, { bubbles: true, composed: true }))}>
        <b>${showArchived ? config.archivedTitle : config.title}</b>
        <span>${total || ""}</span>
        <i class="panel__cap-right fa-solid fa-chevron-down btn-icon${open ? " btn-icon--rotated" : ""}"></i>
      </div>
      ${open ? html`${filters}${loading ? html`<div>Loading…</div>` : table}` : null}
    </section>
    ${modals}
  `;
}

customElements.define(
  "issues-section",
  component(IssuesSection as unknown as () => unknown, { useShadowDOM: false }),
);
