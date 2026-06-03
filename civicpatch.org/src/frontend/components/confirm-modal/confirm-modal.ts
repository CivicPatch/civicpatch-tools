import { html } from "lit-html";
import { component } from "haunted";
import "../basic/modal.js";

export const CONFIRM_EVENT = "confirm";
export const CANCEL_EVENT = "cancel";
export const ALERT_MODE = "alert";
export const DANGER_VARIANT = "danger";

type ConfirmModalHost = HTMLElement & {
  message?: string;
  title?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "default" | typeof DANGER_VARIANT;
  mode?: "confirm" | typeof ALERT_MODE;
};

// Reusable replacement for native confirm()/alert(). In "confirm" mode it shows
// Cancel + a confirm button and dispatches `confirm`/`cancel`; in "alert" mode
// it shows a single OK button. The parent owns the open/close lifecycle by
// rendering this only while a decision is pending.
function ConfirmModal(host: ConfirmModalHost) {
  const {
    message = "",
    title = "",
    confirmLabel = "Confirm",
    cancelLabel = "Cancel",
    variant = "default",
    mode = "confirm",
  } = host;

  const handleConfirm = () =>
    host.dispatchEvent(new CustomEvent(CONFIRM_EVENT, { bubbles: true, composed: true }));
  const handleCancel = () =>
    host.dispatchEvent(new CustomEvent(CANCEL_EVENT, { bubbles: true, composed: true }));

  const confirmClass = variant === DANGER_VARIANT ? "btn btn-sm destructive" : "btn btn-sm";

  const footer = mode === ALERT_MODE
    ? html`<button class="btn btn-sm" @click=${handleConfirm}>OK</button>`
    : html`
        <button class="btn btn-sm secondary" @click=${handleCancel}>${cancelLabel}</button>
        <button class=${confirmClass} @click=${handleConfirm}>${confirmLabel}</button>
      `;

  return html`
    <civ-modal
      .title=${title}
      .content=${html`<p>${message}</p>`}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleCancel }}
    ></civ-modal>
  `;
}

customElements.define(
  "civ-confirm-modal",
  component(ConfirmModal as unknown as () => unknown, { useShadowDOM: false }),
);
