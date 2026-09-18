// The Queue's page of cards: pick some, then publish or dismiss them together. Each card is the
// same read-only diff a review session shows.

import { html } from "lit-html";
import { component } from "haunted";
import { ref } from "lit/directives/ref.js";
import "../../components/panel/panel.css";
import "../../components/review-card-body/review-card-body.js";
import { Pagination } from "../../components/pagination/index.js";
import { jurisdictionOcdidToPath } from "../../components/ocdid-utils.js";
import { usePagerRef } from "../../hooks/use-pager-ref.js";
import { useJurisdictionRoles } from "../../hooks/use-jurisdiction-roles.js";
import { hostDispatch } from "../../utils/host-dispatch.js";
import { toggleSelection } from "../../utils/toggle-selection.js";
import type { ReviewCard } from "../../schemas/review-card.js";

const SELECTION_EVENT = "selection-change";
const PUBLISH_EVENT = "publish-selection";
const DISMISS_EVENT = "dismiss-selection";

// Mirrors `review_pool.list_open_changesets`' row, which `with-data` merges with the card.
export type QueueRow = ReviewCard & {
  created_at: string;
  issue_count: number;
  jurisdiction: { ocdid: string; name: string | null; path: string };
  pr: { url: string | null; status: string };
};

type BulkReviewListHost = HTMLElement & {
  rows: QueueRow[];
  selected: string[];
  busy: boolean;
  loading: boolean;
  error: string | null;
  page: number;
  perPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onPerPageChange: (e: Event) => void;
};

function BulkReviewList(host: BulkReviewListHost) {
  const { listRef, scrollToTop } = usePagerRef();
  const roles = useJurisdictionRoles();

  if (host.loading) return html`<div>Loading...</div>`;
  if (host.error) return html`<div>Error: ${host.error}</div>`;

  const everything = host.rows.map((row) => row.changeset_id);
  const allSelected =
    everything.length > 0 && everything.every((id) => host.selected.includes(id));

  const select = (selected: string[]) => hostDispatch(host, SELECTION_EVENT, { selected });
  const handleToggleAll = () => select(allSelected ? [] : everything);
  const handlePublish = () =>
    hostDispatch(host, PUBLISH_EVENT, { changeset_ids: host.selected });
  const handleDismiss = () =>
    hostDispatch(host, DISMISS_EVENT, { changeset_ids: host.selected });

  // Built once so Next/Previous re-orients to the top of the section either way — clicking
  // the bottom pager most often leaves the reader below what just changed above them.
  const pager = Pagination({
    page: host.page,
    totalPages: host.totalPages,
    onPrevious: () => {
      host.onPageChange(host.page - 1);
      scrollToTop();
    },
    onNext: () => {
      host.onPageChange(host.page + 1);
      scrollToTop();
    },
    perPage: host.perPage,
    onPerPageChange: host.onPerPageChange,
  });

  const actions = html`
    <div class="bulk-review__actions">
      <label class="bulk-review__pick">
        <input
          type="checkbox"
          .checked=${allSelected}
          ?disabled=${host.busy || !everything.length}
          @change=${handleToggleAll}
        />
        <span>${allSelected ? "Deselect all" : "Select all"}</span>
      </label>
      <button
        type="button"
        class="btn-sm"
        ?disabled=${!host.selected.length || host.busy}
        @click=${handlePublish}
      >
        Publish
      </button>
      <button
        type="button"
        class="btn-sm destructive"
        ?disabled=${!host.selected.length || host.busy}
        @click=${handleDismiss}
      >
        Dismiss
      </button>
    </div>
  `;

  const card = (row: QueueRow) => html`
    <section class="bulk-review__card">
      <header class="bulk-review__card-header">
        <label class="bulk-review__pick">
          <input
            type="checkbox"
            aria-label=${`Select ${row.jurisdiction.name ?? row.jurisdiction.ocdid}`}
            .checked=${host.selected.includes(row.changeset_id)}
            ?disabled=${host.busy}
            @change=${() => select(toggleSelection(host.selected, row.changeset_id))}
          />
        </label>
        <a
          href="/${jurisdictionOcdidToPath(row.jurisdiction.path)}"
          target="_blank"
          rel="noopener"
          >${row.jurisdiction.name ?? row.jurisdiction.ocdid}</a
        >
        ${row.pr.url
          ? html`<a href=${row.pr.url} target="_blank" rel="noopener">published data</a>`
          : null}
        ${row.issue_count
          ? html`<span class="bulk-review__issues">
              ${row.issue_count} ${row.issue_count === 1 ? "issue" : "issues"}
            </span>`
          : null}
      </header>
      <civ-review-card-body .card=${row} .roles=${roles}></civ-review-card-body>
    </section>
  `;

  return html`
    <section class="panel" ${ref(listRef)}>
      <div class="panel__cap">
        <b>awaiting review</b>
        <span class="panel__cap-right">${host.rows.length} on this page</span>
      </div>
      ${actions}
      <div class="bulk-review__pager-top">${pager}</div>
      ${host.rows.length === 0
        ? html`<p>Nothing awaiting review.</p>`
        : html`<div class="bulk-review__cards">${host.rows.map(card)}</div>`}
      ${pager} ${actions}
    </section>
  `;
}

customElements.define(
  "bulk-review-list",
  component(BulkReviewList as unknown as () => unknown, { useShadowDOM: false }),
);
