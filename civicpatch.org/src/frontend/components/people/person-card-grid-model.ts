// Role-rank ordering for the officials card grid. `/api/roles` already returns roles in
// canonical priority order (role-reorder.ts writes that order by array position), so rank is
// just an index lookup — no separate priority field to keep in sync.

import { type PersonMembership } from "../edit-people/person-edit-utils.js";

const UNRANKED = Number.POSITIVE_INFINITY;

/** The best (lowest) rank among a person's roles — the one that would read first. */
export function roleRank(
  memberships: PersonMembership[] | undefined,
  roleOrder: string[],
): number {
  let best = UNRANKED;
  for (const membership of memberships ?? []) {
    const index = roleOrder.indexOf(membership.role_id);
    if (index !== -1 && index < best) best = index;
  }
  return best;
}

/** Stable sort by role rank — ties (two Council Members) keep their original order. */
export function sortByRoleRank<T extends { memberships?: PersonMembership[] }>(
  people: T[],
  roleOrder: string[],
): T[] {
  return [...people].sort(
    (a, b) => roleRank(a.memberships, roleOrder) - roleRank(b.memberships, roleOrder),
  );
}

// The role most people on the page hold — the baseline a role has to outrank to earn the
// accent. Without this, a page that's all Council Members would highlight everyone.
function pluralityRoleRank(
  people: { memberships?: PersonMembership[] }[],
  roleOrder: string[],
): number {
  const counts = new Map<string, number>();
  for (const person of people) {
    for (const membership of person.memberships ?? []) {
      counts.set(membership.role_id, (counts.get(membership.role_id) ?? 0) + 1);
    }
  }
  let pluralityRoleId: string | null = null;
  let max = 0;
  for (const [roleId, count] of counts) {
    if (count > max) {
      max = count;
      pluralityRoleId = roleId;
    }
  }
  if (pluralityRoleId === null) return UNRANKED;
  const index = roleOrder.indexOf(pluralityRoleId);
  return index === -1 ? UNRANKED : index;
}

/** Person ids whose best role outranks the page's plurality role. */
export function computeLeadIds<T extends { id: string; memberships?: PersonMembership[] }>(
  people: T[],
  roleOrder: string[],
): Set<string> {
  const baseline = pluralityRoleRank(people, roleOrder);
  const leadIds = new Set<string>();
  for (const person of people) {
    if (roleRank(person.memberships, roleOrder) < baseline) leadIds.add(person.id);
  }
  return leadIds;
}
