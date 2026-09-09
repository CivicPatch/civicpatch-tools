
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
  posts: Post[];
  proposals: Map<string, ProposedChange[]>;
  assertions: Record<string, PersonAssertion[]>;
  overriddenSourceValues: Record<string, Record<string, unknown>>;
  isExpanded: (personId: string) => boolean;
  onToggleExpand: (personId: string) => void;
  onPersonSave: (id: string, updates: Record<string, unknown>) => void;
  onAddPost: (personId: string) => void;
  onRemovePerson: (id: string) => void;
  onUnremovePerson: (id: string) => void;
  onRestorePerson: (person: any) => void;
  onResetPerson: (id: string) => void;
  cards: PersonCard[];
  candidatesOpenFor: boolean;
  onToggleCandidates: () => void;
  onPickPartner: (anchorId: string, partnerId: string) => void;
}

function derivedPostFor(
  card: PersonCard,
  proposals: Map<string, ProposedChange[]>,
): DerivedPost | null {
  const proposed = proposals.get(card.personId) ?? [];
  if (proposed.length) {
    if (proposed.length > 1) return null;
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
    subtitle: postsFor(card, ctx.proposals, ctx.posts),
    derivedPost: derivedPostFor(card, ctx.proposals),
    accepts: acceptsByField(ctx.assertions[card.personId] ?? []),
    overriddenSourceValues: ctx.overriddenSourceValues[card.personId] ?? {},
    posts: ctx.posts,
    onAddPost: () => ctx.onAddPost(card.personId),
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
