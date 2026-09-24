// What a card's local Office pick means, computed by diffing against the office that person
// holds in the body this card is about — never against an assertion, since none exists.
// Shared by roster-editor.ts and review-session.ts, whose Publish/Save actions both need to
// turn "what a reviewer picked" into the edit that makes it real.
//
// Somebody holds one office per body and may hold offices in several, so the body has to be
// named: without it, a person on two bodies diffed against nothing and their pick was lost.
// `organizationOf` is the card's body — one per card today, one per (person, body) at 9b(c).

import { heldPost, heldMembershipLabel } from "../posts-list/posts-model.js";
import { type PersonCard, personOf } from "../people/person-cards.js";

export interface OfficeEdit {
  personId: string;
  postId: string;
  membershipLabel: string | null;
  // Which body this edit is about. A move replaces the office they hold *here*, so the payload
  // cannot key on the post id: the post is the thing that changed.
  organizationId: string | null;
}

function officeEditFor(
  card: PersonCard,
  organizationId: string | null,
): OfficeEdit | null {
  const record = personOf(card);
  if (!card.oldRecord || !record) return null; // no prior membership to move
  const heldPostId = heldPost(record.memberships, organizationId)?.post_id;
  const heldLabel = heldMembershipLabel(record.memberships, organizationId);
  const postId = record.post_id ?? heldPostId;
  // A cleared label is `null`, a real change; only `undefined` means untouched.
  const label = record.membership_label === undefined ? heldLabel : record.membership_label;
  if (!postId) return null; // a label-only edit needs an existing post to attach to
  if (postId === heldPostId && label === heldLabel) return null;
  return { personId: card.personId, postId, membershipLabel: label, organizationId };
}

export function officeEditsIn(
  cards: PersonCard[],
  organizationOf: (card: PersonCard) => string | null = () => null,
): OfficeEdit[] {
  return cards
    .map((card) => officeEditFor(card, organizationOf(card)))
    .filter((edit): edit is OfficeEdit => edit !== null);
}
