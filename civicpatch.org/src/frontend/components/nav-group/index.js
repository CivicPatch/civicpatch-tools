import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import "./nav-group.css";

// A nav link that also leads to a group of other pages (the sidebar you land on
// shows the rest). The label always navigates straight to the group's default page
// in one click; the caret is a separate target that reveals the rest without
// leaving the bar. On a mouse, the menu also opens on hover (see nav-group.css) —
// no click needed there, so reaching any page in the group is still one click. On
// touch, where hover doesn't exist, the caret is the only way to reach it and takes
// its own tap, same as any other disclosure control.
function NavGroup(host) {
  const { label, href, active, items } = host;
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const closeOnOutsideClick = (e) => {
      if (!host.contains(e.target)) setOpen(false);
    };
    const closeOnEscape = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("click", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("click", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return html`
    <span class="nav-group">
      <a href=${href} class="${active ? "nav-link nav-link--active" : "nav-link"}">${label}</a>
      <button
        class="nav-group__caret"
        aria-expanded=${open}
        aria-haspopup="true"
        aria-label="Show ${href} pages"
        @click=${() => setOpen(!open)}
      >
        <i class="fa-solid fa-chevron-down"></i>
      </button>
      <div class="nav-group__menu ${open ? "nav-group__menu--open" : ""}">
        ${items.map(
          (item) => html`<a href=${item.href} class="nav-group__menu-item">${item.label}</a>`,
        )}
      </div>
    </span>
  `;
}

customElements.define("civ-nav-group", component(NavGroup, { useShadowDOM: false }));
