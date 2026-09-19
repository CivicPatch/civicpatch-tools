// One review card, read-only: the same diff view a review session shows, for a page that lists
// many cards and decides them in bulk. Opening a person edits the card on the review page, in a
// new tab so the list keeps its place. Everything it needs arrives on the card.

import { html } from "lit-html";
import { component } from "haunted";
import "../review-overview/review-overview.js";
import {
  buildPersonCards,
  proposalsByPersonId,
  type PersonCard,
} from "../people/person-cards.js";
import type { PersonEditorProps } from "../person-editor/person-editor.js";
import type { Post, RoleOption } from "../posts-list/posts-model.js";
import type { ReviewCard } from "../../schemas/review-card.js";
import { reviewSessionUrl } from "../../pages/review-routes.js";
import { jurisdictionOcdidToState } from "../ocdid-utils.js";

type ReviewCardBodyHost = HTMLElement & {
  card: ReviewCard | null;
  roles: RoleOption[];
};

const NOBODY_REMOVED = new Set<string>();
const NOBODY_OPEN = null;

// Nothing opens in place (`openPersonId` is always null), so the editor is never asked for.
function noEditor(): PersonEditorProps {
  throw new Error("a read-only review card has no editor");
}

function editOnReviewPage(card: ReviewCard) {
  const url = reviewSessionUrl(
    jurisdictionOcdidToState(card.jurisdiction_ocdid),
    card.changeset_id,
  );
  window.open(url, "_blank", "noopener");
}

function postsOf(card: ReviewCard): Post[] {
  return card.organizations
    .flatMap((organization) => organization.posts)
    .sort((a, b) => a.label.localeCompare(b.label));
}

function ReviewCardBody(host: ReviewCardBodyHost) {
  const card = host.card;
  if (!card) return html``;

  const cards: PersonCard[] = buildPersonCards({
    existing: card.existing,
    currentPeople: card.proposed,
    removedIds: NOBODY_REMOVED,
    restoredIds: NOBODY_REMOVED,
    issues: card.review.issues,
    proposals: proposalsByPersonId(card.changes),
  });

  return html`
    <review-overview
      .cards=${cards}
      .changes=${card.changes}
      .isReadOnly=${true}
      .onOpenPerson=${() => editOnReviewPage(card)}
      .openPersonId=${NOBODY_OPEN}
      .editorFor=${noEditor}
      .posts=${postsOf(card)}
      .roles=${host.roles}
      .assertions=${card.assertions}
      .overriddenSourceValues=${card.overridden_source_values}
      .organizations=${card.organizations}
    ></review-overview>
  `;
}

customElements.define(
  "civ-review-card-body",
  component(ReviewCardBody as unknown as () => unknown, { useShadowDOM: false }),
);
