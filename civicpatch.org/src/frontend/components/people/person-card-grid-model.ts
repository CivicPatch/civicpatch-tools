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

const UNRANKED_GROUP_LABEL = "Other";

/** The membership that gives a person their best (lowest) rank — same tie-break as
 * roleRank, just returning the membership itself instead of its position. */
function bestMembership(
  memberships: PersonMembership[] | undefined,
  roleOrder: string[],
): PersonMembership | null {
  let best: PersonMembership | null = null;
  let bestRank = UNRANKED;
  for (const membership of memberships ?? []) {
    const index = roleOrder.indexOf(membership.role_id);
    if (index !== -1 && index < bestRank) {
      bestRank = index;
      best = membership;
    }
  }
  return best;
}

export interface RoleGroup<T> {
  roleId: string | null;
  roleLabel: string;
  people: T[];
}

/** People bucketed by their best-ranked role, in rank order — the .rgroup/.rperson pattern:
 * one heading per role, rather than a role line repeated on every card. A person with no
 * ranked role (unmatched labels) lands in one trailing "Other" group. */
export function groupByRole<T extends { id: string; memberships?: PersonMembership[] }>(
  people: T[],
  roleOrder: string[],
): RoleGroup<T>[] {
  const ranked = sortByRoleRank(people, roleOrder);
  const groups = new Map<string, RoleGroup<T>>();
  const order: string[] = [];
  for (const person of ranked) {
    const membership = bestMembership(person.memberships, roleOrder);
    const key = membership?.role_id ?? UNRANKED_GROUP_LABEL;
    if (!groups.has(key)) {
      groups.set(key, {
        roleId: membership?.role_id ?? null,
        roleLabel: membership?.role_label ?? UNRANKED_GROUP_LABEL,
        people: [],
      });
      order.push(key);
    }
    groups.get(key)!.people.push(person);
  }
  return order.map((key) => groups.get(key)!);
}
