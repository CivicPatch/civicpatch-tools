// Presentation metadata for the role chips in the admin roster.
// `key` matches schemas/common.py:Role values. Adding a new role is appending here.

export type RolePower = "low" | "high";

export type RoleMeta = {
  key: "contributors" | "maintainers" | "admins";
  label: string;
  glyph: string;
  power: RolePower;
  blurb: string;
  powers: string[];
};

export const ROLES_META: ReadonlyArray<RoleMeta> = [
  {
    key: "contributors",
    label: "Contributor",
    glyph: "●",
    power: "low",
    blurb: "Can submit edits and file PRs.",
    powers: ["Submit edits and file PRs", "Comment on existing reviews"],
  },
  {
    key: "maintainers",
    label: "Maintainer",
    glyph: "★",
    power: "high",
    blurb: "Can publish reviewed data and moderate the queue.",
    powers: [
      "Publish reviewed data to production",
      "Lock or close PRs and issues",
      "Pin policy notices to the queue",
    ],
  },
  {
    key: "admins",
    label: "Admin",
    glyph: "⚙",
    power: "high",
    blurb: "Can manage people and roles.",
    powers: ["Invite and remove people", "Assign and revoke roles", "Access the audit log"],
  },
];

export type RoleKey = (typeof ROLES_META)[number]["key"];

export function getRoleMeta(key: string): RoleMeta | undefined {
  return ROLES_META.find((r) => r.key === key);
}
