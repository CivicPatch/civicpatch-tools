// Presentation metadata for the role chips in the admin roster.
// `key` matches schemas/common.py:Role values. Adding a new role is appending here.

export type RolePower = "low" | "high";

export type RoleMeta = {
  key: "contributors" | "maintainers" | "admins";
  label: string;
  power: RolePower;
  blurb: string;
  powers: string[];
};

// Powers listed here are cross-checked against `build_permissions()` in
// routers/frontend.py and the `require_route_access` gates across routers/api/*.
// Anything described here must correspond to a real, enforced backend route.
export const ROLES_META: ReadonlyArray<RoleMeta> = [
  {
    key: "contributors",
    label: "Contributor",
    power: "low",
    blurb: "Can submit data edits via PRs and manage directory people.",
    powers: [
      "Edit jurisdiction details via PRs",
      "Add, update, or delete directory people",
    ],
  },
  {
    key: "maintainers",
    label: "Maintainer",
    power: "high",
    blurb: "Can trigger the pipeline and edit role configs.",
    powers: [
      "Trigger pipeline runs (single and batch)",
      "Edit role configs for states and localities",
      "Read pipeline run errors and events",
    ],
  },
  {
    key: "admins",
    label: "Admin",
    power: "high",
    blurb: "Can manage users, moderate issues, and edit global config.",
    powers: [
      "Manage other users' trust levels",
      "View and moderate the Issues page (flag, dismiss, resolve)",
      "Cancel pipeline runs and edit global role config",
    ],
  },
];

export type RoleKey = (typeof ROLES_META)[number]["key"];

export function getRoleMeta(key: string): RoleMeta | undefined {
  return ROLES_META.find((r) => r.key === key);
}
