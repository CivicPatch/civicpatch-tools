
import { html, nothing } from "lit-html";
import { component } from "haunted";
import "../person-image.js";
import "./review-preview.css";
import {
  renderPersonGrid,
  type PersonRowProps,
} from "../people/person-row.js";
import { renderValues, sourceMapFor, type SourceMap } from "./preview-values.js";
import { divisionOcdidToFriendly } from "../ocdid-utils.js";
import {
  blockingErrors,
  byDivision,
  postsFor,
  proposalsByPersonId,
  type ProposedChange,
  publishSet,
  PersonStatus,
  type PersonCard,
} from "../people/person-cards.js";
import { type Post } from "../posts-list/posts-model.js";

interface ReviewPreviewProps {
  cards: PersonCard[];
  changes?: ProposedChange[];
  jurisdictionOcdid: string | null | undefined;
  posts: Post[];
}

function rowFor(
  card: PersonCard,
  sources: SourceMap,
  proposals: Map<string, ProposedChange[]>,
  posts: Post[],
): PersonRowProps {
  const record = card.newRecord;
  return {
    record,
    name: record?.name || "(unnamed)",
    subtitle: postsFor(card, proposals, posts),
    modifier: card.status,
    meta: renderValues(record, sources),
  };
}

function ReviewPreview(props: ReviewPreviewProps) {
  const { cards, jurisdictionOcdid, changes, posts } = props;
  const publishing = publishSet(cards ?? []);
  const ordered = byDivision(publishing, jurisdictionOcdid);
  const blockers = blockingErrors(cards ?? []);
  const sources = sourceMapFor(publishing.map((card) => card.newRecord));
  const proposals = proposalsByPersonId(changes ?? []);
  const added = publishing.filter((c) => c.status === PersonStatus.ADDED).length;
  const dropped = (cards ?? []).length - publishing.length;
  return html`
    <div class="review-preview">
      <div class="review-preview__bar">
        <span class="review-preview__count">
          ${ordered.length} official${ordered.length === 1 ? "" : "s"} will be published
        </span>
        <span class="review-preview__sub">
          ${added} new, ${dropped} dropped
        </span>
      </div>
      ${blockers.length
        ? html`<div class="review-preview__blockers">
            <span class="review-preview__blockers-title">
              ${blockers.length} thing${blockers.length === 1 ? "" : "s"} to fix before publishing
            </span>
            <ul>
              ${blockers.map(
                (blocker) => html`<li>
                  ${blocker.name} — ${blocker.fieldLabel}: ${blocker.message}
                </li>`,
              )}
            </ul>
          </div>`
        : nothing}
      ${ordered.length
        ? renderPersonGrid(
            ordered.map((card) => rowFor(card, sources, proposals, posts)),
          )
        : html`<p class="review-preview__empty">
            This card would publish an empty roster.
          </p>`}
    </div>
  `;
}

customElements.define(
  "review-preview",
  component(ReviewPreview as unknown as () => unknown, { useShadowDOM: false }),
);
