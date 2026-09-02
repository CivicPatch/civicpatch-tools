import { html } from "lit-html";
import { component, useState } from "haunted";
import "../../components/basic/modal.js";
import { hostDispatch } from "../../utils/host-dispatch.js";

type InviteUserModalHost = HTMLElement & {
  submitting?: boolean;
};

function InviteUserModal(host: InviteUserModalHost) {
  const submitting = host.submitting ?? false;
  const [email, setEmail] = useState("");

  const handleCancel = () => {
    if (submitting) return;
    hostDispatch(host, "modal-close");
  };

  const handleSubmit = (ev: Event) => {
    ev.preventDefault();
    const trimmed = email.trim();
    if (!trimmed || submitting) return;
    hostDispatch(host, "invite-confirmed", { email: trimmed });
  };

  const content = html`
    <form class="invite-user-modal__form" @submit=${handleSubmit}>
      <label class="invite-user-modal__label" for="invite-user-modal-email">Email</label>
      <input
        id="invite-user-modal-email"
        class="invite-user-modal__input"
        type="email"
        placeholder="email@example.com"
        required
        autofocus
        .value=${email}
        @input=${(e: Event) => setEmail((e.target as HTMLInputElement).value)}
        ?disabled=${submitting}
      />
    </form>
  `;

  const footer = html`
    <button class="btn btn-sm secondary" @click=${handleCancel} ?disabled=${submitting}>
      Cancel
    </button>
    <button class="btn btn-sm" @click=${handleSubmit} ?disabled=${submitting || !email.trim()}>
      ${submitting ? "Sending…" : "Send invite"}
    </button>
  `;

  return html`
    <civ-modal
      .title=${"Invite user"}
      .content=${content}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleCancel }}
    ></civ-modal>
  `;
}

customElements.define(
  "invite-user-modal",
  component(InviteUserModal as unknown as () => unknown, { useShadowDOM: false }),
);
