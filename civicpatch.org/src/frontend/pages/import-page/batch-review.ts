import { html } from "lit-html";
import { component, useState } from "haunted";
import {
  REVIEW_PENDING,
  type BatchReview,
  type ReviewJurisdiction,
  type ReviewPerson,
} from "./import-types.js";
import { selectableOcdids, toggleSelection } from "./batch-selection.js";

const PUBLISH_EVENT = "publish-selection";

type BatchReviewHost = HTMLElement & {
  review: BatchReview | null;
  busy: boolean;
};

function personCard(person: ReviewPerson) {
  return html`
    <li class="review-person">
      ${person.image
        ? html`<img
            class="review-person__image"
            src=${person.image}
            alt=""
            loading="lazy"
          />`
        : html`<span class="review-person__image review-person__image--none">
            ${person.name.slice(0, 1)}
          </span>`}
      <span class="review-person__name">${person.name}</span>
      <span class="review-person__label">${person.label || "—"}</span>
    </li>
  `;
}

function BatchReviewPanel(host: BatchReviewHost) {
  const [selected, setSelected] = useState<string[]>([]);
  const review = host.review;

  if (!review) return html``;

  const selectable = selectableOcdids(review.jurisdictions);

  const toggle = (ocdid: string) =>
    setSelected(toggleSelection(selected, ocdid));

  const handleSelectAll = () => setSelected(selectable);

  const handleClear = () => setSelected([]);

  const handlePublish = () =>
    host.dispatchEvent(
      new CustomEvent(PUBLISH_EVENT, {
        detail: { jurisdiction_ocdids: selected },
        bubbles: true,
        composed: true,
      }),
    );

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
          ? html`<ul class="review-jurisdiction__people">
              ${jurisdiction.people.map(personCard)}
            </ul>`
          : null}
      </section>
    `;
  };

  return html`
    <div class="review-toolbar">
      <button
        type="button"
        class="review-toolbar__link"
        ?disabled=${!selectable.length || host.busy}
        @click=${handleSelectAll}
      >
        Select all
      </button>
      <button
        type="button"
        class="review-toolbar__link"
        ?disabled=${!selected.length || host.busy}
        @click=${handleClear}
      >
        Deselect all
      </button>
      <button
        type="button"
        class="import-action"
        ?disabled=${!selected.length || host.busy}
        @click=${handlePublish}
      >
        Publish ${selected.length}
        town${selected.length === 1 ? "" : "s"}
      </button>
    </div>

    ${review.jurisdictions.map(jurisdictionCard)}
  `;
}

customElements.define(
  "batch-review",
  component(BatchReviewPanel as unknown as () => unknown, {
    useShadowDOM: false,
  }),
);
