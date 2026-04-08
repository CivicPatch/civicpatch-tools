import { component } from "haunted";
import { html } from "lit-html";

const STATUS_BADGE_CSS = html`
  <style>
    .badge {
      font-weight: 600;
      font-size: var(--badge-font-size, 0.8rem);
      padding: var(--badge-padding, 0.2rem 0.6rem);
      border-radius: 999px;
      display: inline-block;
      background: var(--badge-bg, var(--pico-muted-background));
      color: var(--badge-color, inherit);
    }
  </style>
`;

function StatusBadge({ label, bg, color }) {
  const style = [
    bg ? `background: ${bg}` : "",
    color ? `color: ${color}` : "",
  ]
    .filter(Boolean)
    .join("; ");

  return html`
    ${STATUS_BADGE_CSS}
    <span class="badge" style="${style}">${label}</span>
  `;
}

customElements.define(
  "civ-status-badge",
  component(StatusBadge, {
    useShadowDOM: false,
    observedAttributes: ["label", "bg", "color"],
  })
);