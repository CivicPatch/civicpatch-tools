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
} from "../people/person-cards.js";
import { UNMATCHED_ROLE_ID } from "../../schemas/role-types.js";
import { type PersonMembership } from "../edit-people/person-edit-utils.js";
import { canMerge, mergeCandidates } from "../review/merge-model.js";
import { acceptsByField, type PersonAssertion } from "./field-provenance.js";
import { type PersonEditorProps } from "./person-editor.js";
import {
  heldPost,
  heldMembershipLabel,
  type DerivedPost,
  type Post,
  type ProposedPost,
  type RoleOption,
} from "../posts-list/posts-model.js";
import { type ProposedChange } from "../../schemas/membership-proposal.js";
import {
  type MembershipRemoval,
  type RosterMembership,
} from "../../schemas/membership-removal.js";

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
  canCreatePost: boolean;
  // The whole jurisdiction's open memberships; each editor takes its own person's out of it.
  rosterMemberships: RosterMembership[];
  onSetRemoval: ((membershipId: string, assertion: MembershipRemoval) => void) | null;
  onSetNotAMember: (personId: string, claimed: boolean) => void;
  proposals: Map<string, ProposedChange[]>;
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

// A proposal with no recognized role is a vocabulary gap, not an answer to show as one.
function derivedPostFromProposal(proposal: ProposedChange): DerivedPost | null {
  if (proposal.post.role_id === UNMATCHED_ROLE_ID) return null;
  return {
    post_id: proposal.post.id,
    label: proposal.post.label,
    membershipLabel: proposal.membership_label,
    // Only meaningful when there's no `post_id` for the picker to look up instead (see
    // `DerivedPost`'s own comment) — carried regardless, since it costs nothing unused.
    role_id: proposal.post.role_id,
    division_ocdid: proposal.post.division_ocdid,
  };
}

function derivedPostFromHeld(
  memberships: PersonMembership[] | undefined,
): DerivedPost | null {
  const held = heldPost(memberships);
  return held
    ? { ...held, membershipLabel: heldMembershipLabel(memberships) }
    : null;
}

function derivedPostFor(
  card: PersonCard,
  proposals: Map<string, ProposedChange[]>,
): DerivedPost | null {
  const proposed = proposals.get(card.personId) ?? [];
  // Two or more proposals is no single answer — unlike `soleProposalFor`'s other callers,
  // this does not fall through to the held membership below the way "no proposal at all"
  // does: picking either of two would show a decision nobody made.
  if (proposed.length > 1) return null;
  return proposed[0]
    ? derivedPostFromProposal(proposed[0])
    : derivedPostFromHeld(personOf(card)?.memberships);
}

function allProposedPosts(
  proposals: Map<string, ProposedChange[]>,
): ProposedPost[] {
  return Array.from(proposals.values())
    .flat()
    .filter((proposal) => proposal.post.role_id !== UNMATCHED_ROLE_ID)
    .map((proposal) => ({
      role_id: proposal.post.role_id,
      role_label: proposal.post.role_label,
      division_ocdid: proposal.post.division_ocdid,
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
    onSetRemoval: ctx.onSetRemoval,
    status: card.status,
    oldRecord: card.oldRecord,
    newRecord: card.newRecord,
    surviving: card.surviving,
    frozenReasons: visibleFields(ctx.frozen, card.personId),
    issues: card.issues,
    isReadOnly: ctx.isReadOnly,
    jurisdictionOcdid: ctx.jurisdictionOcdid,
    subtitle: postsFor(card, ctx.proposals, ctx.posts),
    derivedPost: derivedPostFor(card, ctx.proposals),
    proposedPosts: allProposedPosts(ctx.proposals),
    accepts: acceptsByField(ctx.assertions[card.personId] ?? []),
    assertions: ctx.assertions[card.personId] ?? [],
    overriddenSourceValues: ctx.overriddenSourceValues[card.personId] ?? {},
    posts: ctx.posts,
    organizationId: ctx.organizationId,
    roles: ctx.roles,
    canAssignMembership: ctx.canAssignMembership,
    canCreatePost: ctx.canCreatePost,
    isDirty: ctx.dirtyIds.has(card.personId),
    isExpanded: ctx.isExpanded(card.personId),
    onToggleExpand: () => ctx.onToggleExpand(card.personId),
    onSave: save,
    // Remove is the person-scoped claim: they are not a member here at all. It was two channels
    // for one act — a card flag publish read, and an assertion nobody filed from the UI — so the
    // button files the claim and putting them back withdraws it.
    onRemove: () => {
      ctx.onRemovePerson(card.personId);
      ctx.onSetNotAMember(card.personId, true);
    },
    onUnremove: () => {
      ctx.onUnremovePerson(card.personId);
      ctx.onSetNotAMember(card.personId, false);
    },
    onRestore: () => {
      ctx.onRestorePerson(card.oldRecord);
      ctx.onSetNotAMember(card.personId, false);
    },
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
