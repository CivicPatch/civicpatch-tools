import { html } from "lit-html";
import { component } from "haunted";

type StatusToastHost = HTMLElement & {
  message: string;
  onDismiss: () => void;
};

function StatusToast(host: StatusToastHost) {
  const handleDismiss = () => host.onDismiss?.();

  return html`
    <div class="status-toast" role="status" aria-live="polite">
      <span class="status-toast__message">${host.message}</span>
      <button
        type="button"
        class="status-toast__close"
        @click=${handleDismiss}
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  `;
}

customElements.define(
  "status-toast",
  component(StatusToast as unknown as () => unknown, { useShadowDOM: false }),
);
