import { html } from "lit-html";
import { component, useEffect, useState } from "haunted";
import {
  CHANGESET_OPEN,
  type BatchReview,
  type ReviewJurisdiction,
  type RowError,
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
  filterCounts,
  filtered,
  localities,
  pageCount,
  pageOf,
  selectableChangesetIds,
  changeBadges,
  type Locality,
  type ReviewFilter,
} from "./batch-selection.js";
import { toggleSelection } from "../../utils/toggle-selection.js";
import { loadingLine } from "./loading-line.js";

const FILTER_LABELS: Record<ReviewFilter, string> = {
  [REVIEW_FILTER.ERRORS]: "Errors",
  [REVIEW_FILTER.HAS_ABSENT]: "Has absences",
  [REVIEW_FILTER.HAS_ADDED]: "Has new people",
  [REVIEW_FILTER.HAS_CHANGED]: "Has edits",
  [REVIEW_FILTER.UNCHANGED]: "Unchanged",
  [REVIEW_FILTER.OPEN]: "Still open",
};

const PUBLISH_EVENT = "publish-selection";
const DISMISS_EVENT = "dismiss-selection";

type BatchReviewHost = HTMLElement & {
  review: BatchReview | null;
  errors: RowError[];
  importedAt: string | null;
  busy: boolean;
};

// Counting at import failed; the card itself still loads.
const UNCOUNTED = "—";

function peopleLabel(people: number | null) {
  if (people == null) return UNCOUNTED;
  return `${people} ${people === 1 ? "person" : "people"}`;
}

function errorLine(error: RowError) {
  const where =
    error.line == null
      ? ""
      : `Line ${error.line}${error.column ? `, ${error.column}` : ""}: `;
  return html`<li>${where}${error.message}</li>`;
}

function errorList(errors: RowError[]) {
  if (!errors.length) return null;
  return html`<ul class="review-jurisdiction__errors">
    ${errors.map(errorLine)}
  </ul>`;
}

function BatchReviewPanel(host: BatchReviewHost) {
  const [selected, setSelected] = useState<string[]>([]);
  // One at a time; null shows every locality.
  const [filter, setFilter] = useState<ReviewFilter | null>(null);
  const [page, setPage] = useState(0);
  const [cards, setCards] = useState<Record<string, ReviewCard>>({});
  const [cardsError, setCardsError] = useState<string | null>(null);
  const [cardsLoading, setCardsLoading] = useState(false);
  const roles = useJurisdictionRoles();
  const review = host.review;
  const items = review
    ? byChangeRank(localities(review.jurisdictions, host.errors))
    : [];
  // Errors sit in their own block above the pager; the paged list is the cards.
  const errored = items.filter((locality) => locality.errors.length);
  const shown = filtered(
    items.filter((locality) => locality.review),
    filter,
  );
  const visibleCards = pageOf(shown, page).flatMap((locality) =>
    locality.review ? [locality.review] : [],
  );
  const visibleIds = visibleCards.map(
    (jurisdiction) => jurisdiction.changeset_id,
  );

  // Per page, and again whenever the review is re-read: a publish changes what each card says.
  useEffect(() => {
    if (!visibleIds.length) return;
    let stopped = false;
    setCardsError(null);
    setCardsLoading(true);
    fetchReviewCards(visibleIds)
      .then(({ data }: { data: ReviewCard[] }) => {
        if (stopped) return;
        setCards(
          Object.fromEntries(data.map((card) => [card.changeset_id, card])),
        );
      })
      .catch((error: unknown) => {
        if (!stopped) setCardsError(String(error));
      })
      .finally(() => {
        if (!stopped) setCardsLoading(false);
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

  const pages = pageCount(shown);
  const showErrors =
    errored.length > 0 &&
    (filter === null || filter === REVIEW_FILTER.ERRORS);
  const everything = selectableChangesetIds(shown);
  const anythingOpen = selectableChangesetIds(items).length > 0;
  const counts = filterCounts(items);
  // Several batches can be open at once; a shared name would make them one radio group.
  const filterGroup = `review-filter-${review.batch_id}`;

  // Clears the selection: a town ticked and then filtered out would still be published.
  const pickFilter = (picked: ReviewFilter | null) => {
    setFilter(picked);
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

  const handleToggleAll = () => setSelected(allSelected ? [] : everything);

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

  const erroredLocality = (locality: Locality) => {
    // A row with no jurisdiction_ocdid names no page to link to.
    const path = jurisdictionOcdidToPath(locality.jurisdiction_ocdid);
    return html`
      <li>
        ${path
          ? html`<a href="/${path}" target="_blank" rel="noopener"
              >${locality.name}</a
            >`
          : locality.name}
        ${errorList(locality.errors)}
      </li>
    `;
  };

  const errorBlock = showErrors
    ? html`
        <section class="import-section">
          <h3 class="import-section__title">
            Errors <span>[${errored.length}]</span>
          </h3>
          <ul class="import-errored">
            ${errored.map(erroredLocality)}
          </ul>
        </section>
      `
    : null;

  const jurisdictionCard = (jurisdiction: ReviewJurisdiction) => {
    const ocdid = jurisdiction.jurisdiction_ocdid;
    const settled = jurisdiction.changeset_state !== CHANGESET_OPEN;
    return html`
      <section
        class="review-jurisdiction ${settled
          ? "review-jurisdiction--settled"
          : ""}"
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
            ${peopleLabel(jurisdiction.people)}
          </span>
          <span class="review-jurisdiction__count review-jurisdiction__changes">
            ${jurisdiction.change_counts
              ? changeBadges(jurisdiction.change_counts).map(
                  (badge) =>
                    html`<span class="review-row__badge review-row__badge--${badge.status}"
                      >${badge.label}</span
                    >`,
                )
              : UNCOUNTED}
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
  if (!items.length) {
    return html`
      <h2 class="import-panel__title">Nothing changed</h2>
      ${importedNote}
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
      ${errorBlock} ${cardsLoading ? loadingLine("Loading cards…") : null}
      ${pager} ${visibleCards.map(jurisdictionCard)} ${pager}
    `;
  }

  return html`
    <h2 class="import-panel__title">
      Review and publish <span>[${selected.length}]</span>
    </h2>
    ${importedNote}
    ${errorBlock}
    <div class="import-toolbar">
      <label class="import-pick">
        <input
          type="radio"
          name=${filterGroup}
          .checked=${filter === null}
          @change=${() => pickFilter(null)}
        />
        <span>All ${items.length}</span>
      </label>
      ${Object.values(REVIEW_FILTER).map(
        (option) => html`
          <label class="import-pick">
            <input
              type="radio"
              name=${filterGroup}
              .checked=${filter === option}
              @change=${() => pickFilter(option)}
            />
            <span
              >${FILTER_LABELS[option]} ${counts[option]}/${items.length}</span
            >
          </label>
        `,
      )}
    </div>
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

    ${shown.length || showErrors
      ? null
      : html`<p class="import-hint">No localities match this filter.</p>`}
    ${cardsError
      ? html`<p class="import-results__failure">
          Could not load the cards: ${cardsError}
        </p>`
      : null}
    ${cardsLoading ? loadingLine("Loading cards…") : null}
    ${publishButton} ${pager} ${visibleCards.map(jurisdictionCard)} ${pager}
    ${publishButton}
  `;
}

customElements.define(
  "batch-review",
  component(BatchReviewPanel as unknown as () => unknown, {
    useShadowDOM: false,
  }),
);
