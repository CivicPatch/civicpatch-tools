import { html } from "lit-html";
import { component, useState } from "haunted";
import {
  REVIEW_PENDING,
  type BatchReview,
  type ReviewJurisdiction,
} from "./import-types.js";
import { Pagination } from "../../components/pagination/index.js";
import { renderReviewPerson } from "./review-person.js";
import {
  pageCount,
  pageOf,
  selectableOcdids,
  toggleSelection,
} from "./batch-selection.js";

const PUBLISH_EVENT = "publish-selection";

type BatchReviewHost = HTMLElement & {
  review: BatchReview | null;
  busy: boolean;
};

function BatchReviewPanel(host: BatchReviewHost) {
  const [selected, setSelected] = useState<string[]>([]);
  const [page, setPage] = useState(0);
  const review = host.review;

  if (!review) return html``;

  const pages = pageCount(review.jurisdictions);
  const visible = pageOf(review.jurisdictions, page);
  const everything = selectableOcdids(review.jurisdictions);

  const toggle = (ocdid: string) =>
    setSelected(toggleSelection(selected, ocdid));

  // One control, both directions: ticked means everything selectable is picked, and clicking
  // it again clears the lot. Two separate links for that was a button pretending to be state.
  const allSelected =
    everything.length > 0 &&
    everything.every((ocdid) => selected.includes(ocdid));

  const handleToggleAll = () =>
    setSelected(allSelected ? [] : everything);

  const handlePublish = () =>
    host.dispatchEvent(
      new CustomEvent(PUBLISH_EVENT, {
        detail: { jurisdiction_ocdids: selected },
        bubbles: true,
        composed: true,
      }),
    );

  // Top and bottom: a page of localities is long enough that paging from the bottom should not
  // mean scrolling back up. The shared component is 1-indexed; this state counts from zero.
  const pager =
    pages > 1
      ? Pagination({
          page: page + 1,
          totalPages: pages,
          onPrevious: () => setPage(Math.max(page - 1, 0)),
          onNext: () => setPage(Math.min(page + 1, pages - 1)),
          // No per-page control here: the size is fixed, and the component hides the selector
          // when there is nothing to call.
          perPage: undefined,
          onPerPageChange: undefined,
        })
      : null;

  // Echoed at both ends: with a page of localities between them, whichever end you finish
  // reading at should have the action next to it.
  const publishButton = html`
    <button
      type="button"
      class="import-action"
      ?disabled=${!selected.length || host.busy}
      @click=${handlePublish}
    >
      Publish
    </button>
  `;

  const jurisdictionCard = (jurisdiction: ReviewJurisdiction) => {
    const ocdid = jurisdiction.jurisdiction_ocdid;
    const settled = jurisdiction.review_status !== REVIEW_PENDING;
    return html`
      <section
        class="review-jurisdiction ${settled ? "review-jurisdiction--settled" : ""}"
        data-jurisdiction=${ocdid}
      >
        <header class="review-jurisdiction__header">
          <label class="review-jurisdiction__pick">
            <input
              type="checkbox"
              .checked=${selected.includes(ocdid)}
              ?disabled=${settled || host.busy}
              @change=${() => toggle(ocdid)}
            />
            <span class="review-jurisdiction__name">${jurisdiction.name}</span>
          </label>
          <span class="review-jurisdiction__count">
            ${jurisdiction.people.length}
            ${jurisdiction.people.length === 1 ? "person" : "people"}
          </span>
          ${settled
            ? html`<span class="review-jurisdiction__status"
                >${jurisdiction.review_status}</span
              >`
            : null}
        </header>
        ${jurisdiction.people.length
          ? html`<div class="review-jurisdiction__people">
              ${jurisdiction.people.map(renderReviewPerson)}
            </div>`
          : null}
      </section>
    `;
  };

  // No cards at all: every locality in the sheet said what it said last run. Distinct from the
  // settled case below, where cards exist and have all been decided.
  if (!review.jurisdictions.length) {
    return html`
      <h2 class="import-panel__title">Nothing changed</h2>
      <p class="import-hint">
        Every locality in the sheet reads exactly as it did on the last import,
        so no review cards were raised. Edit the sheet and import again.
      </p>
    `;
  }

  // Nothing left to decide: every locality is published, dismissed or superseded. Offering a
  // disabled tick and two dead Publish buttons reads as broken rather than finished.
  if (!everything.length) {
    return html`
      <h2 class="import-panel__title">Imported localities</h2>
      <p class="import-hint">
        Every locality in this import has been settled, so there is nothing left
        to publish. Each one says below whether it went live or was superseded
        by a later import.
      </p>
      ${pager} ${visible.map(jurisdictionCard)} ${pager}
    `;
  }

  return html`
    <h2 class="import-panel__title">
      Review and publish <span>[${selected.length}]</span>
    </h2>
    <div class="import-toolbar">
      <label class="import-pick">
        <input
          type="checkbox"
          .checked=${allSelected}
          ?disabled=${host.busy}
          @change=${handleToggleAll}
        />
        <span>${allSelected ? "Deselect all" : "Select all"}</span>
      </label>
    </div>

    ${publishButton} ${pager} ${visible.map(jurisdictionCard)} ${pager}

    ${publishButton}
  `;
}

customElements.define(
  "batch-review",
  component(BatchReviewPanel as unknown as () => unknown, {
    useShadowDOM: false,
  }),
);
