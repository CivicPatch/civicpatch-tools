import { html } from "lit-html";
import { component } from "haunted";
import { getRoleMeta } from "./roles-meta.js";

type RoleChipHost = HTMLElement & {
  role: string;
  assigned: boolean;
  disabled: boolean;
  disabledTooltip?: string;
};

function RoleChip(host: RoleChipHost) {
  const meta = getRoleMeta(host.role);
  if (!meta) return html``;

  const assigned = host.assigned;
  const disabled = host.disabled;
  const action = assigned ? "Remove" : "Add";
  const tooltip = disabled
    ? host.disabledTooltip ?? ""
    : `Click to ${action.toLowerCase()} ${meta.label}`;

  const classes = [
    "role-chip",
    `role-chip--${meta.key}`,
    assigned ? "role-chip--assigned" : "role-chip--unassigned",
  ].join(" ");

  const onClick = (e: Event) => {
    if (disabled) return;
    host.dispatchEvent(
      new CustomEvent("role-chip-click", {
        detail: { role: meta.key, assigned },
        bubbles: true,
        composed: true,
      }),
    );
    e.stopPropagation();
  };

  return html`
    <button
      type="button"
      class=${classes}
      aria-pressed=${assigned ? "true" : "false"}
      ?disabled=${disabled}
      title=${tooltip}
      @click=${onClick}
    >
      <span class="role-chip__glyph" aria-hidden="true">${assigned ? meta.glyph : "+"}</span>
      <span class="role-chip__label">${meta.label}</span>
    </button>
  `;
}

customElements.define(
  "role-chip",
  component(RoleChip as unknown as () => unknown, {
    useShadowDOM: false,
    observedAttributes: [],
  }),
);
