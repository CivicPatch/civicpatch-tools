// Role-rank ordering for the officials card grid. `/api/roles` already returns roles in
// canonical priority order (role-reorder.ts writes that order by array position), so rank is
// just an index lookup — no separate priority field to keep in sync.

// The only fields this module reads off a membership — a real `PersonMembership` (a
// published seat) satisfies this, and so does a proposal's role, which has no post yet.
// Keeping the constraint this narrow is what lets review-session group by proposed role
// through the same functions the jurisdiction grid groups published people with.
export type PostRole = {
  role_id: string;
  role_label: string;
  post_label: string;
  membership_label: string | null;
};

const UNRANKED = Number.POSITIVE_INFINITY;

/** The best (lowest) rank among a person's roles — the one that would read first. */
export function roleRank(
  memberships: PostRole[] | undefined,
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
export function sortByRoleRank<T extends { memberships?: PostRole[] }>(
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
  people: { memberships?: PostRole[] }[],
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
export function computeLeadIds<T extends { id: string; memberships?: PostRole[] }>(
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

/** The membership that gives a person their best (lowest) rank, and that rank itself — one
 * pass over their memberships rather than the separate rank-then-membership scans
 * `groupByRole` used to run (once to sort, again per person to find the group). */
function bestMembershipAndRank(
  memberships: PostRole[] | undefined,
  roleOrder: string[],
): { membership: PostRole | null; rank: number } {
  let best: PostRole | null = null;
  let bestRank = UNRANKED;
  for (const membership of memberships ?? []) {
    const index = roleOrder.indexOf(membership.role_id);
    if (index !== -1 && index < bestRank) {
      bestRank = index;
      best = membership;
    }
  }
  return { membership: best, rank: bestRank };
}

// Numeric-aware, so "District 2" reads before "District 10".
function compareLabels(a: string | null | undefined, b: string | null | undefined): number {
  return (a ?? "").localeCompare(b ?? "", undefined, { numeric: true });
}

export interface RoleGroup<T> {
  roleId: string | null;
  roleLabel: string;
  people: T[];
}

/** People bucketed by their best-ranked role, in rank order — the .rgroup/.rperson pattern:
 * one heading per role, rather than a role line repeated on every card. A person with no
 * ranked role (unmatched labels) lands in one trailing "Other" group. */
export function groupByRole<T extends { id: string; memberships?: PostRole[] }>(
  people: T[],
  roleOrder: string[],
): RoleGroup<T>[] {
  // Decorate-sort-undecorate: each person's rank and best membership are computed once here,
  // rather than once per sort comparison (`sortByRoleRank` re-scans on both sides of every
  // comparison) and again afterward to find which group they belong to.
  const decorated = people.map((person) => ({
    person,
    ...bestMembershipAndRank(person.memberships, roleOrder),
  }));
  decorated.sort(
    (a, b) =>
      a.rank - b.rank ||
      compareLabels(a.membership?.post_label, b.membership?.post_label) ||
      compareLabels(a.membership?.membership_label, b.membership?.membership_label),
  );

  const groups = new Map<string, RoleGroup<T>>();
  const order: string[] = [];
  for (const { person, membership } of decorated) {
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
