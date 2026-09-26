import { html } from "lit-html";
import { component } from "haunted";
import "../../components/basic/modal.js";
import { hostDispatch } from "../../utils/host-dispatch.js";

type ConfirmRollbackModalHost = HTMLElement & {
  count: number;
  userLabel: string;
  submitting?: boolean;
};

function ConfirmRollbackModal(host: ConfirmRollbackModalHost) {
  const submitting = host.submitting ?? false;

  const handleCancel = () => {
    if (submitting) return;
    hostDispatch(host, "modal-close");
  };
  const handleConfirm = () => hostDispatch(host, "rollback-confirmed-final");

  const content = html`
    <p class="confirm-rollback-modal__blurb">
      Roll back ${host.count} change${host.count === 1 ? "" : "s"} for
      <strong>${host.userLabel}</strong>?
    </p>
    <p class="confirm-rollback-modal__warning">
      This can't be undone automatically. Reverting it means editing the record
      again.
    </p>
  `;

  const footer = html`
    <button
      class="btn btn-sm secondary"
      @click=${handleCancel}
      ?disabled=${submitting}
    >
      Cancel
    </button>
    <button
      class="btn btn-sm destructive"
      @click=${handleConfirm}
      ?disabled=${submitting}
    >
      ${submitting ? "Rolling back…" : "Roll back"}
    </button>
  `;

  return html`
    <civ-modal
      .title=${"Are you sure?"}
      .content=${content}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleCancel }}
    ></civ-modal>
  `;
}

customElements.define(
  "confirm-rollback-modal",
  component(ConfirmRollbackModal as unknown as () => unknown, {
    useShadowDOM: false,
  }),
);
