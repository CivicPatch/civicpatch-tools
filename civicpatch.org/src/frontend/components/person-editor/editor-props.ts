
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
import { UNMATCHED_ROLE_ID } from "../../utils/role-types.js";
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
  if (proposal.role_id === UNMATCHED_ROLE_ID) return null;
  return {
    post_id: proposal.post_id ?? null,
    label: proposal.post_label,
    membershipLabel: proposal.label ?? null,
    // Only meaningful when there's no `post_id` for the picker to look up instead (see
    // `DerivedPost`'s own comment) — carried regardless, since it costs nothing unused.
    role_id: proposal.role_id,
    division_ocdid: proposal.division_ocdid,
  };
}

function derivedPostFromHeld(
  memberships: PersonMembership[] | undefined,
): DerivedPost | null {
  const held = heldPost(memberships);
  return held ? { ...held, membershipLabel: heldMembershipLabel(memberships) } : null;
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

// Every role/division this person has proposed, regardless of how many — unlike
// `derivedPostFor` above, which gives up entirely once there's more than one (there's no
// single answer to auto-pick), this hands all of them to the office picker as options, so a
// person proposed for two seats at once is something a reviewer can actually choose between
// rather than a picker showing neither.
function proposedPostsFor(
  card: PersonCard,
  proposals: Map<string, ProposedChange[]>,
): ProposedPost[] {
  return (proposals.get(card.personId) ?? [])
    .filter((proposal) => proposal.role_id !== UNMATCHED_ROLE_ID)
    .map((proposal) => ({
      role_id: proposal.role_id,
      role_label: proposal.role_label,
      division_ocdid: proposal.division_ocdid,
    }));
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
    subtitle: postsFor(card, ctx.proposals, ctx.posts),
    derivedPost: derivedPostFor(card, ctx.proposals),
    proposedPosts: proposedPostsFor(card, ctx.proposals),
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
