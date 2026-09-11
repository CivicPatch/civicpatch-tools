import { html, type TemplateResult } from "lit-html";

export type SectionNavItem = {
  label: string;
  href: string;
  count?: number;
};

// Real links, not client-side tabs: the views are separate URLs and stay bookmarkable.
export function SectionNav(
  label: string,
  items: SectionNavItem[],
  currentPath: string,
): TemplateResult {
  return html`
    <nav class="secnav" aria-label="${label}">
      ${items.map(
        (item) => html`<a
          class="secnav__item ${item.href === currentPath ? "secnav__item--on" : ""}"
          href=${item.href}
          aria-current=${item.href === currentPath ? "page" : "false"}
          >${item.label}${item.count != null
            ? html`<span class="secnav__count">${item.count}</span>`
            : ""}</a
        >`,
      )}
    </nav>
  `;
}

export const ACTIVITY_SECTION: SectionNavItem[] = [
  { label: "change log", href: "/activity/changelogs" },
  { label: "changesets", href: "/activity/changesets" },
];

// useAuth() is plain JS with no return type, so TS infers its `permissions` as the
// literal type of DENY_ALL ({}) — real, populated permission objects still flow
// through at runtime, so the cast here is just working around the missing types
// upstream, not widening what this function actually expects.
function perm(permissions: object, key: string): boolean {
  return Boolean((permissions as Record<string, boolean>)?.[key]);
}

// Same items, and the same permission gates, the navbar's "Manage"/"Admin" dropdowns
// used to show — the dropdown is gone, replaced by landing on the group's first page
// and moving between siblings via this sidebar instead. Takes `permissions` straight
// from useAuth(), same as every page that calls this already destructures it.
export function manageSection(permissions: object, openPrCount?: number): SectionNavItem[] {
  const items: SectionNavItem[] = [
    { label: "Bulk review", href: "/bulk-review", ...(openPrCount != null ? { count: openPrCount } : {}) },
  ];
  if (perm(permissions, "can_write_config")) {
    items.push({ label: "Roles", href: "/roles" });
    items.push({ label: "Sheet import", href: "/imports" });
  }
  return items;
}

export function userSection(username: string): SectionNavItem[] {
  return [
    { label: "Profile", href: `/~${username}` },
    { label: "History", href: `/~${username}/history` },
  ];
}

export function adminSection(permissions: object): SectionNavItem[] {
  const items: SectionNavItem[] = [{ label: "Users", href: "/admin" }];
  if (perm(permissions, "can_edit_spend")) items.push({ label: "Spend", href: "/spend" });
  if (perm(permissions, "can_batch_scrape")) items.push({ label: "Pipelines", href: "/pipelines" });
  if (perm(permissions, "can_view_issues_page")) items.push({ label: "Issues", href: "/issues" });
  if (perm(permissions, "can_view_gallery_page")) items.push({ label: "Components", href: "/gallery" });
  return items;
}
