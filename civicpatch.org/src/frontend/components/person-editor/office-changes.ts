// What a card's local Office pick means to `memberships.assign`, computed by diffing against
// the person's actually-held post/label — never against an assertion, since none exists.
// Shared by roster-editor.ts and review-session.ts, whose Publish/Save actions both need to
// turn "what a reviewer picked" into the calls that make it real.

import { heldPost, heldMembershipLabel } from "../posts-list/posts-model.js";
import { type PersonCard, personOf } from "../people/person-cards.js";

export interface OfficeChange {
  personId: string;
  postId: string;
  label: string | null;
}

// `undefined` on the record means untouched; `null` means explicitly cleared. Only the
// former counts as "nothing to say" — a cleared label is still a real change.
function officeChangeFor(card: PersonCard): OfficeChange | null {
  const record = personOf(card);
  if (!card.oldRecord || !record) return null; // no prior membership to move
  const held = heldPost(card.oldRecord.memberships);
  const heldLabel = heldMembershipLabel(card.oldRecord.memberships);
  const pickedPostId = record.post_id;
  const pickedLabel = record.membership_label;
  const postChanged = pickedPostId !== undefined && (pickedPostId ?? null) !== (held?.post_id ?? null);
  const labelChanged = pickedLabel !== undefined && (pickedLabel ?? null) !== (heldLabel ?? null);
  if (!postChanged && !labelChanged) return null;
  const postId = postChanged ? pickedPostId : held?.post_id;
  if (!postId) return null; // a label-only edit needs an existing post to attach to
  return {
    personId: card.personId,
    postId,
    label: labelChanged ? (pickedLabel ?? null) : heldLabel,
  };
}

export function officeChangesIn(cards: PersonCard[]): OfficeChange[] {
  return cards.map(officeChangeFor).filter((change): change is OfficeChange => change !== null);
}
