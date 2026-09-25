import {
  visibleFields,
  type FrozenFields,
} from "./frozen-fields.js";
import { type Save } from "../fields/field-controls.js";
import {
  postsFor,
  PersonStatus,
  type PersonCard,
  personOf,
} from "../people/person-cards.js";
import { UNMATCHED_ROLE_ID } from "../../schemas/role-types.js";
import { type PersonMembership } from "../edit-people/person-edit-utils.js";
import { canMerge, mergeCandidates } from "../review/merge-model.js";
import { acceptsByField, type PersonAssertion } from "./field-provenance.js";
import { type PersonEditorProps } from "./person-editor.js";
import {
  heldOffice,
  type DerivedPost,
  type Post,
  type ProposedPost,
  type RoleOption,
} from "../posts-list/posts-model.js";
import { type RosterMembership } from "../../schemas/roster-membership.js";

export type EditorContextBase = Omit<
  EditorContext,
  "isExpanded" | "onToggleExpand"
>;

export interface EditorContext {
  frozen: FrozenFields;
  dirtyIds: Set<string>;
  isReadOnly: boolean;
  jurisdictionOcdid: string | null | undefined;
  posts: Post[];
  organizationId: string;
  roles: RoleOption[];
  canAssignMembership: boolean;
  // The whole jurisdiction's open memberships; each editor takes its own person's out of it.
  rosterMemberships: RosterMembership[];
  assertions: Record<string, PersonAssertion[]>;
  overriddenSourceValues: Record<string, Record<string, unknown>>;
  isExpanded: (personId: string) => boolean;
  onToggleExpand: (personId: string) => void;
  onPersonSave: (id: string, updates: Record<string, unknown>) => void;
  onRemovePerson: (id: string) => void;
  onUnremovePerson: (id: string) => void;
  onRestorePerson: (person: any) => void;
  onResetPerson: (id: string) => void;
  cards: PersonCard[];
  candidatesOpenFor: boolean;
  onToggleCandidates: () => void;
  onPickPartner: (anchorId: string, partnerId: string) => void;
}

/** What the office picker opens on: the office this card's record holds in this body.
 *
 * The record is the proposed one where there is one, so a scrape's detected move defaults the
 * picker the way its own proposal used to. A post the fold names but no `posts` row exists for
 * yet cannot be looked up by id, so it is offered by role and division instead — which is the
 * one thing `DerivedPost`'s `post_id` half cannot express. No recognised role is a vocabulary
 * gap, not an answer to show as one.
 */
function derivedPostFor(
  card: PersonCard,
  organizationId: string,
  posts: Post[],
): DerivedPost | null {
  const held = heldOffice(personOf(card)?.memberships, organizationId);
  if (!held || held.role_id === UNMATCHED_ROLE_ID) return null;
  // An empty list is "not loaded yet", not "the post is not there" — `useJurisdictionPosts`
  // answers empty while it loads and on failure, and reading that as absent would offer every
  // published person's long-standing post as one the scrape is about to mint.
  const known = !posts.length || posts.some((post) => post.id === held.post_id);
  return {
    post_id: known ? held.post_id : null,
    label: held.post_label ?? "",
    membershipLabel: held.label ?? null,
    role_id: held.role_id,
    division_ocdid: held.division_ocdid,
  };
}

/** Every post this card's people would land in that has no `posts` row yet, so the picker can
 * offer one scrape's new post to the next person in the same card. */
function proposedPosts(cards: PersonCard[], posts: Post[]): ProposedPost[] {
  const known = new Set(posts.map((post) => post.id));
  return (cards ?? [])
    .flatMap((card) => personOf(card)?.memberships ?? [])
    .filter(
      (membership: any) =>
        membership.role_id &&
        membership.role_id !== UNMATCHED_ROLE_ID &&
        !known.has(membership.post_id),
    )
    .map((membership: any) => ({
      role_id: membership.role_id,
      role_label: membership.role_label,
      division_ocdid: membership.division_ocdid,
    }));
}

export function personEditorPropsFor(
  card: PersonCard,
  ctx: EditorContext,
): PersonEditorProps {
  const save: Save = (updates) => ctx.onPersonSave(card.personId, updates);
  return {
    personId: card.personId,
    memberships: ctx.rosterMemberships,
    status: card.status,
    oldRecord: card.oldRecord,
    newRecord: card.newRecord,
    surviving: card.surviving,
    frozenReasons: visibleFields(ctx.frozen, card.personId),
    issues: card.issues,
    isReadOnly: ctx.isReadOnly,
    jurisdictionOcdid: ctx.jurisdictionOcdid,
    subtitle: postsFor(card, ctx.posts),
    derivedPost: derivedPostFor(card, ctx.organizationId, ctx.posts),
    proposedPosts: proposedPosts(ctx.cards, ctx.posts),
    accepts: acceptsByField(ctx.assertions[card.personId] ?? []),
    assertions: ctx.assertions[card.personId] ?? [],
    overriddenSourceValues: ctx.overriddenSourceValues[card.personId] ?? {},
    posts: ctx.posts,
    organizationId: ctx.organizationId,
    roles: ctx.roles,
    canAssignMembership: ctx.canAssignMembership,
    isDirty: ctx.dirtyIds.has(card.personId),
    isExpanded: ctx.isExpanded(card.personId),
    onToggleExpand: () => ctx.onToggleExpand(card.personId),
    onSave: save,
    onRemove: () => ctx.onRemovePerson(card.personId),
    onUnremove: () => ctx.onUnremovePerson(card.personId),
    onRestore: () => ctx.onRestorePerson(card.oldRecord),
    onReset:
      ctx.dirtyIds.has(card.personId) && card.status !== PersonStatus.REMOVED
        ? () => ctx.onResetPerson(card.personId)
        : null,
    focusField: null,
    mergeCandidates: canMerge(card) ? mergeCandidates(card, ctx.cards) : [],
    isCandidateListOpen: ctx.candidatesOpenFor,
    onToggleCandidates: () => ctx.onToggleCandidates(),
    onPickPartner: (partnerId: string) =>
      ctx.onPickPartner(card.personId, partnerId),
  };
}
