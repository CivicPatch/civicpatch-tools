import { html } from "lit-html";
import { component, useState } from "haunted";
import "../../components/basic/modal.js";
import { hostDispatch } from "../../utils/host-dispatch.js";

type ReportIssueModalHost = HTMLElement & {
  submitting?: boolean;
  error?: string | null;
};

function ReportIssueModal(host: ReportIssueModalHost) {
  const submitting = host.submitting ?? false;
  const error = host.error ?? null;
  const [description, setDescription] = useState("");

  const handleCancel = () => {
    if (submitting) return;
    hostDispatch(host, "modal-close");
  };

  const handleSubmit = (ev: Event) => {
    ev.preventDefault();
    const trimmed = description.trim();
    if (!trimmed || submitting) return;
    hostDispatch(host, "report-issue-confirmed", { description: trimmed });
  };

  const content = html`
    <form class="report-issue-modal__form" @submit=${handleSubmit}>
      <label class="report-issue-modal__label" for="report-issue-modal-description">
        What's the issue?
      </label>
      <textarea
        id="report-issue-modal-description"
        class="report-issue-modal__textarea"
        rows="6"
        placeholder="Describe the data problem you found…"
        required
        autofocus
        .value=${description}
        @input=${(e: Event) => setDescription((e.target as HTMLTextAreaElement).value)}
        ?disabled=${submitting}
      ></textarea>
      ${error ? html`<p class="review-page__error">${error}</p>` : ""}
    </form>
  `;

  const footer = html`
    <button class="btn btn-sm secondary" @click=${handleCancel} ?disabled=${submitting}>
      Cancel
    </button>
    <button class="btn btn-sm" @click=${handleSubmit} ?disabled=${submitting || !description.trim()}>
      ${submitting ? "Filing…" : "File issue"}
    </button>
  `;

  return html`
    <civ-modal
      .title=${"Report an issue"}
      .content=${content}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleCancel }}
    ></civ-modal>
  `;
}

customElements.define(
  "report-issue-modal",
  component(ReportIssueModal as unknown as () => unknown, { useShadowDOM: false }),
);
