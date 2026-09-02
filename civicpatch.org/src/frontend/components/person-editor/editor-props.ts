// Building one person's editor props, in one place.
//
// Detail renders a list of editors and the modal renders exactly one, and they
// must agree about what a person's row is — the modal is the editor mounted with a
// one-person list, not a second one (§6). Extracted here so neither has to
// reproduce the other's rules.

import {
  visibleFields,
  type FrozenFields,
} from "../../pages/review-session-page/frozen-fields.js";
import { type Save } from "../fields/field-controls.js";
import {
  postsFor,
  PersonStatus,
  type PersonCard,
  personOf,
  type ProposedChange,
} from "../people/person-cards.js";
import { canMerge, mergeCandidates } from "../review/merge-model.js";
import { acceptsByField, type PersonAssertion } from "./field-provenance.js";
import { type PersonEditorProps } from "./person-editor.js";

// Mirrors `UNMATCHED_ROLE_ID` in core/post_derivation.py — the seeded role a label
// resolving to nothing falls back to.
const UNMATCHED_ROLE_ID = "unmatched";
import {
  heldPost,
  type DerivedPost,
  type Post,
} from "../posts-list/posts-model.js";

export type EditorContextBase = Omit<
  EditorContext,
  "isExpanded" | "onToggleExpand"
>;

export interface EditorContext {
  frozen: FrozenFields;
  dirtyIds: Set<string>;
  isReadOnly: boolean;
  jurisdictionOcdid: string | null | undefined;
  // Every post in the jurisdiction, for the Post field to pick from. Roster-wide, hence
  // context rather than per-card.
  posts: Post[];
  // Also roster-wide: a person proposed onto a post holds no membership to read it off.
  proposals: Map<string, ProposedChange[]>;
  // Every person's assertions, keyed by person id, as the review read returns them.
  assertions: Record<string, PersonAssertion[]>;
  // A predicate, not a set: a page whose default is "expanded" has no set to
  // keep in sync with the roster, so a person it has never seen cannot arrive
  // collapsed.
  isExpanded: (personId: string) => boolean;
  onToggleExpand: (personId: string) => void;
  onPersonSave: (id: string, updates: Record<string, unknown>) => void;
  // The page opens the add-post form and, once it saves, picks the result for this person.
  onAddPost: (personId: string) => void;
  onRemovePerson: (id: string) => void;
  onUnremovePerson: (id: string) => void;
  onRestorePerson: (person: any) => void;
  onResetPerson: (id: string) => void;
  // Step 1 of a merge, in place on the editor: which person's strip is open, and
  // what to do when one of its candidates is picked.
  cards: PersonCard[];
  candidatesOpenFor: string | null;
  onToggleCandidates: (personId: string) => void;
  onPickPartner: (anchorId: string, partnerId: string) => void;
}

/** The post this person is in — the proposal, else the one held membership (the same two
 * `postsFor` reads). Only when exactly one: two posts is no single answer. Shown, never saved.
 *
 * Carries the label as well as the id, because a proposal names a post that may have no row:
 * ingest stopped minting posts, so `post_id` is null until someone publishes. An id alone left
 * the picker with nothing to show and the derivation's answer disappeared. */
function derivedPostFor(
  card: PersonCard,
  proposals: Map<string, ProposedChange[]>,
): DerivedPost | null {
  const proposed = proposals.get(card.personId) ?? [];
  if (proposed.length) {
    if (proposed.length > 1) return null;
    // `unmatched` is a vocabulary gap, not an answer.
    if (proposed[0].role_id === UNMATCHED_ROLE_ID) return null;
    return {
      post_id: proposed[0].post_id ?? null,
      label: proposed[0].post_label,
    };
  }
  return heldPost(personOf(card)?.memberships);
}

export function personEditorPropsFor(
  card: PersonCard,
  ctx: EditorContext,
): PersonEditorProps {
  const save: Save = (updates) => ctx.onPersonSave(card.personId, updates);
  return {
    status: card.status,
    oldRecord: card.oldRecord,
    newRecord: card.newRecord,
    surviving: card.surviving,
    frozenReasons: visibleFields(ctx.frozen, card.personId),
    issues: card.issues,
    isReadOnly: ctx.isReadOnly,
    jurisdictionOcdid: ctx.jurisdictionOcdid,
    subtitle: postsFor(card, ctx.proposals),
    derivedPost: derivedPostFor(card, ctx.proposals),
    accepts: acceptsByField(ctx.assertions[card.personId] ?? []),
    posts: ctx.posts,
    onAddPost: () => ctx.onAddPost(card.personId),
    isDirty: ctx.dirtyIds.has(card.personId),
    isExpanded: ctx.isExpanded(card.personId),
    onToggleExpand: () => ctx.onToggleExpand(card.personId),
    onSave: save,
    onRemove: () => ctx.onRemovePerson(card.personId),
    onUnremove: () => ctx.onUnremovePerson(card.personId),
    // Rebuilding the record needs the old side, which only the card has.
    onRestore: () => ctx.onRestorePerson(card.oldRecord),
    // Reset is offered only to someone with edits to discard. A card the
    // reviewer has not touched has nothing to reset to.
    onReset:
      ctx.dirtyIds.has(card.personId) && card.status !== PersonStatus.REMOVED
        ? () => ctx.onResetPerson(card.personId)
        : null,
    // Only the modal opens on a field; it sets this over the props it is handed.
    focusField: null,
    mergeCandidates: canMerge(card) ? mergeCandidates(card, ctx.cards) : [],
    isCandidateListOpen: ctx.candidatesOpenFor === card.personId,
    onToggleCandidates: () => ctx.onToggleCandidates(card.personId),
    onPickPartner: (partnerId: string) =>
      ctx.onPickPartner(card.personId, partnerId),
  };
}
