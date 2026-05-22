import { html } from "lit-html";
import { component } from "haunted";
import { getRoleMeta, ROLES_META, type RoleKey } from "./roles-meta.js";
import "../../components/basic/modal.js";

export type ConfirmRoleContext = {
  userId: string;
  userLabel: string;
  fromRole: string;
  toRole: string;
};

type ConfirmRoleModalHost = HTMLElement & {
  context: ConfirmRoleContext | null;
};

const DEFAULT_ROLE = "default";
const LADDER: readonly RoleKey[] = ROLES_META.map((m) => m.key);

function rolePos(role: string): number {
  if (role === DEFAULT_ROLE) return 0;
  const idx = LADDER.indexOf(role as RoleKey);
  return idx === -1 ? 0 : idx + 1;
}

function roleLabel(role: string): string {
  return getRoleMeta(role)?.label ?? "Default";
}

function ConfirmRoleModal(host: ConfirmRoleModalHost) {
  const ctx = host.context;
  if (!ctx) return html``;

  const dispatch = (name: string, detail?: unknown) =>
    host.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));

  const handleCancel = () => dispatch("modal-close");
  const handleConfirm = () => dispatch("role-confirmed", { ...ctx });

  const isPromote = rolePos(ctx.toRole) > rolePos(ctx.fromRole);
  // The target role's meta drives the copy when promoting (powers gained).
  // When demoting, the meta of the role being left drives it (powers lost).
  const focusRole = isPromote ? ctx.toRole : ctx.fromRole;
  const focusMeta = getRoleMeta(focusRole);

  const title = isPromote
    ? `Promote ${ctx.userLabel} to ${roleLabel(ctx.toRole)}?`
    : `Demote ${ctx.userLabel} from ${roleLabel(ctx.fromRole)} to ${roleLabel(ctx.toRole)}?`;

  const confirmLabel = isPromote ? "Promote" : "Demote";
  const confirmClass = isPromote ? "btn btn-sm" : "btn btn-sm destructive";

  const blurb = focusMeta?.blurb ?? "";
  const powersLabel = isPromote ? "Powers granted" : "Powers being removed";
  const powers = focusMeta?.powers ?? [];

  const content = html`
    ${blurb ? html`<p class="confirm-role-modal__blurb">${blurb}</p>` : null}
    ${powers.length
      ? html`
          <div class="confirm-role-modal__powers-label">${powersLabel}</div>
          <ul class="confirm-role-modal__powers">
            ${powers.map((p) => html`<li>${p}</li>`)}
          </ul>
        `
      : null}
  `;

  const footer = html`
    <button class="btn btn-sm secondary" @click=${handleCancel}>Cancel</button>
    <button class=${confirmClass} @click=${handleConfirm}>${confirmLabel}</button>
  `;

  return html`
    <civ-modal
      .title=${title}
      .content=${content}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleCancel }}
    ></civ-modal>
  `;
}

customElements.define(
  "confirm-role-modal",
  component(ConfirmRoleModal as unknown as () => unknown, { useShadowDOM: false }),
);
