// What the roster editor sends to `POST /api/v1/jurisdictions/roster-edits`: one entry per
// person, carrying the fields they changed and the whole set of posts that person should hold.
//
// Three sources become one list. A patch item is what `buildPeoplePatch` produced. An office
// change is an existing person's pick, diffed against the post they hold. A removed person is
// `offices: []`, which rejects every post they hold — the old patch dropped them and let the
// server infer removal from absence.

import type { OfficeEdit } from "../person-editor/office-edits.js";
import { organizationIn, personIdIn } from "../people/person-cards.js";

// A brand-new person's pick rides in their fields, because `officeEditsIn` only answers for
// somebody who already holds something. These two are posts, not person fields.
const OFFICE_FIELDS = ["post_id", "membership_label"];

export interface OfficeEditPayload {
  id: string;
  membership_label: string | null;
}

// The same, plus the body it is in — carried while the payload is assembled so an edit can
// replace the office somebody holds *there*, and dropped before it goes on the wire.
interface HeldOffice extends OfficeEditPayload {
  organizationId: string | null;
}

export interface PersonEdit {
  id: string;
  fields?: Record<string, unknown>;
  offices?: OfficeEditPayload[];
}

interface PatchItem {
  id: string;
  fields: Record<string, unknown>;
}

function withoutOfficeFields(fields: Record<string, unknown>) {
  const kept = { ...fields };
  for (const field of OFFICE_FIELDS) delete kept[field];
  return kept;
}

function pickInFields(fields: Record<string, unknown>): OfficeEditPayload | null {
  const postId = fields.post_id;
  if (typeof postId !== "string" || !postId) return null;
  const label = fields.membership_label;
  return { id: postId, membership_label: typeof label === "string" ? label : null };
}

export function rosterEditPayload(
  patch: PatchItem[],
  officeEdits: OfficeEdit[],
  removedIds: Iterable<string>,
  heldOffices: Map<string, HeldOffice[]> = new Map(),
): PersonEdit[] {
  const byPerson = new Map<string, PersonEdit>();

  for (const item of patch) {
    const person: PersonEdit = { id: item.id, fields: withoutOfficeFields(item.fields) };
    const pick = pickInFields(item.fields);
    if (pick) person.offices = [pick];
    byPerson.set(item.id, person);
  }

  // `offices` is the whole set somebody should hold, and the editor only reports what a
  // reviewer *changed*. So an edit to one body starts from every office that person holds and
  // overlays the change: sending the changed one alone would tell the server they hold nothing
  // in their other bodies, and it would reject those posts.
  const officesInProgress = new Map<string, HeldOffice[]>();
  for (const change of officeEdits) {
    const person = byPerson.get(change.personId) ?? { id: change.personId };
    const office: HeldOffice = {
      id: change.postId,
      membership_label: change.membershipLabel,
      organizationId: change.organizationId,
    };
    const base =
      officesInProgress.get(change.personId) ?? heldOffices.get(change.personId) ?? [];
    // Replaced by body, not by post: a move changes the post, so keying on it would leave the
    // office they moved out of in the set alongside the one they moved into.
    const kept = base.filter((held) =>
      held.organizationId && office.organizationId
        ? held.organizationId !== office.organizationId
        : held.id !== office.id,
    );
    officesInProgress.set(change.personId, [...kept, office]);
    byPerson.set(change.personId, person);
  }
  for (const [personId, offices] of officesInProgress) {
    const person = byPerson.get(personId)!;
    person.offices = offices.map(({ id, membership_label }) => ({ id, membership_label }));
  }

  // A removal names a row: this person, in this body. So it takes that body's office out of
  // the set and leaves the rest — somebody removed from the council still sits on the school
  // board. `offices: []` is what a person removed from every body ends up with, which is how
  // "off the roster entirely" says itself.
  for (const key of removedIds) {
    const personId = personIdIn(key);
    const organizationId = organizationIn(key);
    const person = byPerson.get(personId) ?? { id: personId };
    const base = person.offices
      ? person.offices.map((office) => ({ ...office, organizationId: null }))
      : (heldOffices.get(personId) ?? []);
    person.offices = base
      .filter((held) =>
        organizationId && held.organizationId
          ? held.organizationId !== organizationId
          : false,
      )
      .map(({ id, membership_label }) => ({ id, membership_label }));
    byPerson.set(personId, person);
  }

  return [...byPerson.values()];
}

/** What each person already holds, so an edit to one body can keep the others. Keyed by person
 * because `offices` is per person on the wire; the body rides along to replace by body. */
export function heldOfficesByPerson(
  cards: { personId: string; oldRecord?: { memberships?: any[] } | null }[],
): Map<string, { id: string; membership_label: string | null; organizationId: string | null }[]> {
  return new Map(
    cards.map((card) => [
      card.personId,
      (card.oldRecord?.memberships ?? [])
        .filter((membership) => !!membership.post_id)
        .map((membership) => ({
          id: membership.post_id,
          membership_label: membership.label ?? null,
          organizationId: membership.organization_id ?? null,
        })),
    ]),
  );
}
