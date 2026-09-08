import { html, type TemplateResult } from "lit-html";

export type SectionNavItem = {
  label: string;
  href: string;
};

// Real links, not client-side tabs: the views are separate URLs and stay bookmarkable.
export function SectionNav(
  label: string,
  items: SectionNavItem[],
  currentPath: string,
): TemplateResult {
  return html`
    <nav class="secnav" aria-label="${label}">
      <span class="secnav__label">${label}</span>
      ${items.map(
        (item) => html`<a
          class="secnav__item ${item.href === currentPath ? "secnav__item--on" : ""}"
          href=${item.href}
          aria-current=${item.href === currentPath ? "page" : "false"}
          >${item.label}</a
        >`,
      )}
    </nav>
  `;
}

export const ACTIVITY_SECTION: SectionNavItem[] = [
  { label: "change log", href: "/activity/changelogs" },
  { label: "changesets", href: "/activity/changesets" },
];
