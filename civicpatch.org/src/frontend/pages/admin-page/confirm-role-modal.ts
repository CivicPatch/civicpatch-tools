import { html } from "lit-html";
import { component } from "haunted";
import { getRoleMeta } from "./roles-meta.js";
import "../../components/basic/modal.js";

export type ConfirmRoleContext = {
  userId: string;
  userLabel: string;
  role: string;
  action: "add" | "remove";
};

type ConfirmRoleModalHost = HTMLElement & {
  context: ConfirmRoleContext | null;
};

function ConfirmRoleModal(host: ConfirmRoleModalHost) {
  const ctx = host.context;
  if (!ctx) return html``;

  const meta = getRoleMeta(ctx.role);
  if (!meta) return html``;

  const dispatch = (name: string, detail?: unknown) =>
    host.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));

  const handleCancel = () => dispatch("modal-close");
  const handleConfirm = () => dispatch("role-confirmed", { ...ctx });

  const isGrant = ctx.action === "add";
  const title = `${isGrant ? "Grant" : "Revoke"} ${meta.label} ${isGrant ? "to" : "from"} ${ctx.userLabel}?`;
  const confirmLabel = isGrant ? "Grant" : "Revoke";
  const confirmClass = isGrant ? "btn btn-sm" : "btn btn-sm destructive";

  const content = html`
    <p class="confirm-role-modal__blurb">${meta.blurb}</p>
    <div class="confirm-role-modal__powers-label">Powers granted</div>
    <ul class="confirm-role-modal__powers">
      ${meta.powers.map((p) => html`<li>${p}</li>`)}
    </ul>
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
