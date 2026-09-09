import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { assignLetters } from "./letters.js";
import "../basic/modal.js";
import "../badge/badge.js";
import "./nav-shortcuts.css";

// `?` opens a menu of every page currently in the nav (already permission-filtered by
// the caller), grouped the same way the nav bar itself is — direct links, manage,
// admin. Each page's letter is assigned once across the full flattened list, so a
// press while the menu is open can never mean two different pages.
const isTyping = (el) => el && /^(input|textarea|select)$/i.test(el.tagName);

function NavShortcuts({ sections }) {
  const [open, setOpen] = useState(false);
  const flat = assignLetters(sections.flatMap((s) => s.items));
  const byHref = new Map(flat.map((f) => [f.href, f]));
  const byLetter = new Map(flat.map((f) => [f.letter, f.href]));

  useEffect(() => {
    const onKeydown = (e) => {
      if (open) {
        if (e.key === "Escape") setOpen(false);
        const href = byLetter.get(e.key.toLowerCase());
        if (href) window.location.href = href;
        return;
      }
      if (isTyping(document.activeElement)) return;
      if (e.key === "?") {
        e.preventDefault();
        setOpen(true);
      }
    };
    document.addEventListener("keydown", onKeydown);
    return () => document.removeEventListener("keydown", onKeydown);
  }, [open, sections]);

  const content = html`
    <div class="nav-shortcuts-list">
      ${sections.map(
        (section) => html`
          <div class="nav-shortcuts-section">
            <div class="nav-shortcuts-section-label">${section.label}</div>
            ${section.items.map((item) => {
              const f = byHref.get(item.href);
              return html`<a class="nav-shortcuts-row" href=${item.href}>
                <civ-badge .label=${f.letter} variant="secondary"></civ-badge>
                <span>${item.label}</span>
              </a>`;
            })}
          </div>
        `,
      )}
    </div>
  `;

  return html`
    <button class="nav-shortcuts-hint" @click=${() => setOpen(true)} aria-label="Keyboard shortcuts">
      <span class="nav-shortcuts-hint-key">?</span> shortcuts
    </button>
    <civ-modal
      .title=${"Jump to a page"}
      .content=${content}
      .modalProps=${{ open, onClose: () => setOpen(false), closeOnBackdropClick: true }}
    ></civ-modal>
  `;
}

customElements.define("civ-nav-shortcuts", component(NavShortcuts, { useShadowDOM: false }));
