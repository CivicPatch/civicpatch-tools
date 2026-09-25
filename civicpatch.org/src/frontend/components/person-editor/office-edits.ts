// What a card's local Office pick means, computed by diffing against the office that person
// holds in the body this card is about — never against an claim, since none exists.
// Shared by roster-editor.ts and review-session.ts, whose Publish/Save actions both need to
// turn "what a reviewer picked" into the edit that makes it real.
//
// Somebody holds one office per body and may hold offices in several, so the body has to be
// named: without it, a person on two bodies diffed against nothing and their pick was lost.
// `organizationOf` is the card's body — one per card today, one per (person, body) at 9b(c).

import { heldOffice } from "../posts-list/posts-model.js";
import { type PersonCard, personOf } from "../people/person-cards.js";

export interface OfficeEdit {
  personId: string;
  postId: string;
  membershipLabel: string | null;
  // The term, per membership. Omitted from an edit when it matches what they hold here.
  startDate?: string | null;
  endDate?: string | null;
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
  const held = heldOffice(record.memberships, organizationId);
  const was = {
    postId: held?.post_id ?? null,
    label: held?.label ?? null,
    startDate: held?.start_date ?? null,
    endDate: held?.end_date ?? null,
  };
  const now = {
    postId: record.post_id ?? was.postId,
    label: edited(record.membership_label, was.label),
    startDate: edited(record.start_date, was.startDate),
    endDate: edited(record.end_date, was.endDate),
  };
  if (!now.postId) return null; // a label-only edit needs an existing post to attach to

  const officeChanged = now.postId !== was.postId || now.label !== was.label;
  const datesChanged = now.startDate !== was.startDate || now.endDate !== was.endDate;
  if (!officeChanged && !datesChanged) return null;

  const edit: OfficeEdit = {
    personId: card.personId,
    postId: now.postId,
    membershipLabel: now.label,
    organizationId,
  };
  if (datesChanged) {
    edit.startDate = now.startDate;
    edit.endDate = now.endDate;
  }
  return edit;
}

// Untouched (`undefined`) keeps what they hold; emptied (`""` or `null`) is cleared.
function edited(value: unknown, held: string | null): string | null {
  if (value === undefined) return held;
  return typeof value === "string" && value ? value : null;
}

export function officeEditsIn(
  cards: PersonCard[],
  organizationOf: (card: PersonCard) => string | null = () => null,
): OfficeEdit[] {
  return cards
    .map((card) => officeEditFor(card, organizationOf(card)))
    .filter((edit): edit is OfficeEdit => edit !== null);
}
