import { html } from "lit-html";
import { component, useEffect, useState } from "haunted";
import {
  CHANGESET_OPEN,
  type BatchReview,
  type ReviewJurisdiction,
} from "./import-types.js";
import { Pagination } from "../../components/pagination/index.js";
import { jurisdictionOcdidToPath } from "../../components/ocdid-utils.js";
import { scrollListTop } from "../../utils/scroll-list-top.js";
import { formatDateTime } from "../../utils/date-utils.js";
import { hostDispatch } from "../../utils/host-dispatch.js";
import "../../components/review-card-body/review-card-body.js";
import { fetchReviewCards } from "../../api.js";
import { useJurisdictionRoles } from "../../hooks/use-jurisdiction-roles.js";
import type { ReviewCard } from "../../schemas/review-card.js";
import {
  REVIEW_FILTER,
  byChangeRank,
  filtered,
  pageCount,
  pageOf,
  selectableChangesetIds,
  changeSummary,
  type ReviewFilter,
} from "./batch-selection.js";
import { toggleSelection } from "../../utils/toggle-selection.js";

const FILTER_LABELS: Record<ReviewFilter, string> = {
  [REVIEW_FILTER.HAS_ABSENT]: "Has absences",
  [REVIEW_FILTER.HAS_ADDED]: "Has new people",
  [REVIEW_FILTER.UNCHANGED]: "Unchanged",
};

const PUBLISH_EVENT = "publish-selection";
const DISMISS_EVENT = "dismiss-selection";

type BatchReviewHost = HTMLElement & {
  review: BatchReview | null;
  importedAt: string | null;
  busy: boolean;
};

function BatchReviewPanel(host: BatchReviewHost) {
  const [selected, setSelected] = useState<string[]>([]);
  const [filters, setFilters] = useState<ReviewFilter[]>([]);
  const [page, setPage] = useState(0);
  const [cards, setCards] = useState<Record<string, ReviewCard>>({});
  const [cardsError, setCardsError] = useState<string | null>(null);
  const roles = useJurisdictionRoles();
  const review = host.review;

  const visibleIds = review
    ? pageOf(filtered(byChangeRank(review.jurisdictions), filters), page).map(
        (jurisdiction) => jurisdiction.changeset_id,
      )
    : [];

  // Per page, and again whenever the review is re-read: a publish changes what each card says.
  useEffect(() => {
    if (!visibleIds.length) return;
    let stopped = false;
    setCardsError(null);
    fetchReviewCards(visibleIds)
      .then(({ data }: { data: ReviewCard[] }) => {
        if (stopped) return;
        setCards(Object.fromEntries(data.map((card) => [card.changeset_id, card])));
      })
      .catch((error: unknown) => {
        if (!stopped) setCardsError(String(error));
      });
    return () => {
      stopped = true;
    };
  }, [visibleIds.join(","), review]);

  if (!review) return html``;

  const importedNote = host.importedAt
    ? html`<p class="import-hint">
        Imported ${formatDateTime(host.importedAt)}
      </p>`
    : null;

  const shown = filtered(byChangeRank(review.jurisdictions), filters);
  const pages = pageCount(shown);
  const visible = pageOf(shown, page);
  const everything = selectableChangesetIds(shown);
  const anythingOpen = selectableChangesetIds(review.jurisdictions).length > 0;

  // Clears the selection: a town ticked and then filtered out would still be published.
  const toggleFilter = (filter: ReviewFilter) => {
    setFilters(toggleSelection(filters, filter));
    setSelected([]);
    setPage(0);
  };

  const toggle = (changesetId: string) =>
    setSelected(toggleSelection(selected, changesetId));

  // One control, both directions: ticked means everything selectable is picked, and clicking
  // it again clears the lot. Two separate links for that was a button pretending to be state.
  const allSelected =
    everything.length > 0 &&
    everything.every((changesetId) => selected.includes(changesetId));

  const handleToggleAll = () =>
    setSelected(allSelected ? [] : everything);

  const handlePublish = () =>
    host.dispatchEvent(
      new CustomEvent(PUBLISH_EVENT, {
        detail: { changeset_ids: selected },
        bubbles: true,
        composed: true,
      }),
    );

  const handleDismiss = () =>
    hostDispatch(host, DISMISS_EVENT, { changeset_ids: selected });

  // Top and bottom: a page of localities is long enough that paging from the bottom should not
  // mean scrolling back up. The shared component is 1-indexed; this state counts from zero.
  const pager =
    pages > 1
      ? Pagination({
          page: page + 1,
          totalPages: pages,
          onPrevious: () => {
            setPage(Math.max(page - 1, 0));
            scrollListTop(host);
          },
          onNext: () => {
            setPage(Math.min(page + 1, pages - 1));
            scrollListTop(host);
          },
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
    <button
      type="button"
      class="import-action"
      ?disabled=${!selected.length || host.busy}
      @click=${handleDismiss}
    >
      Dismiss
    </button>
  `;

  const jurisdictionCard = (jurisdiction: ReviewJurisdiction) => {
    const ocdid = jurisdiction.jurisdiction_ocdid;
    const settled = jurisdiction.changeset_state !== CHANGESET_OPEN;
    return html`
      <section
        class="review-jurisdiction ${settled ? "review-jurisdiction--settled" : ""}"
        data-jurisdiction=${ocdid}
      >
        <header class="review-jurisdiction__header">
          <div class="review-jurisdiction__pick">
            <input
              type="checkbox"
              aria-label=${`Select ${jurisdiction.name}`}
              .checked=${selected.includes(jurisdiction.changeset_id)}
              ?disabled=${settled || host.busy}
              @change=${() => toggle(jurisdiction.changeset_id)}
            />
            <a
              class="review-jurisdiction__name"
              href="/${jurisdictionOcdidToPath(ocdid)}"
              target="_blank"
              rel="noopener"
              >${jurisdiction.name}</a
            >
          </div>
          <span class="review-jurisdiction__count">
            ${jurisdiction.people}
            ${jurisdiction.people === 1 ? "person" : "people"}
          </span>
          <span class="review-jurisdiction__count">
            ${changeSummary(jurisdiction.change_counts) || "Unchanged"}
          </span>
          ${settled
            ? html`<span class="review-jurisdiction__status"
                >${jurisdiction.changeset_state}</span
              >`
            : null}
        </header>
        <civ-review-card-body
          .card=${cards[jurisdiction.changeset_id] ?? null}
          .roles=${roles}
        ></civ-review-card-body>
      </section>
    `;
  };

  // No cards at all: every locality in the sheet said what it said last run. Distinct from the
  // settled case below, where cards exist and have all been decided.
  if (!review.jurisdictions.length) {
    return html`
      <h2 class="import-panel__title">Nothing changed</h2>
      ${importedNote}
      <p class="import-hint">
        Every locality in the sheet reads exactly as it did on the last import,
        so there is nothing to publish. Edit the sheet and import again.
      </p>
    `;
  }

  // Nothing left to decide: every locality is published or dismissed. Offering a disabled tick
  // and dead buttons reads as broken rather than finished.
  if (!anythingOpen) {
    return html`
      <h2 class="import-panel__title">Imported localities</h2>
      ${importedNote}
      <p class="import-hint">
        Every locality in this import has been settled, so there is nothing left
        to publish. Each one says below whether it went live or was dismissed.
      </p>
      ${pager} ${visible.map(jurisdictionCard)} ${pager}
    `;
  }

  return html`
    <h2 class="import-panel__title">
      Review and publish <span>[${selected.length}]</span>
    </h2>
    ${importedNote}
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
      ${Object.values(REVIEW_FILTER).map(
        (filter) => html`
          <label class="import-pick">
            <input
              type="checkbox"
              .checked=${filters.includes(filter)}
              @change=${() => toggleFilter(filter)}
            />
            <span>${FILTER_LABELS[filter]}</span>
          </label>
        `,
      )}
    </div>

    ${shown.length
      ? null
      : html`<p class="import-hint">No localities match these filters.</p>`}
    ${cardsError
      ? html`<p class="import-results__failure">Could not load the cards: ${cardsError}</p>`
      : null}
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
