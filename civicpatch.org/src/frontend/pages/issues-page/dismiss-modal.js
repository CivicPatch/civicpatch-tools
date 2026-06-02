import { html } from "lit-html";
import { component, useState } from "haunted";
import { dismissIssue } from "../../api.js";
import { formatIssueType } from "./utils.js";
import "../../components/basic/modal.js";

function DismissModal(host) {
  const issue = host.issue;

  const [dismissLoading, setDismissLoading] = useState(false);

  const dispatch = (name, detail) =>
    host.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));

  const handleClose = () => dispatch("modal-close", {});

  const handleConfirm = async () => {
    setDismissLoading(true);
    try {
      await dismissIssue(issue.id);
      dispatch("issue-dismissed", { issue_id: issue.id });
    } catch (err) {
      console.error("Failed to dismiss issue:", err);
    } finally {
      setDismissLoading(false);
    }
  };

  if (!issue) return null;

  const content = html`
    ${issue.jurisdictions?.length === 1 ? html`
      <div class="issues-page__modal-jurisdiction-link">${issue.jurisdictions[0].name}</div>
    ` : null}
    <p>Dismiss this issue without opening a PR?</p>
  `;

  const footer = html`
    <button class="btn btn-sm secondary" @click=${handleClose} ?disabled=${dismissLoading}>Cancel</button>
    <button class="btn btn-sm" @click=${handleConfirm} ?disabled=${dismissLoading}>
      ${dismissLoading ? "Dismissing…" : "Confirm"}
    </button>
  `;

  return html`
    <civ-modal
      .title=${"Dismiss — " + formatIssueType(issue.issue_type)}
      .content=${content}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleClose }}
    ></civ-modal>
  `;
}

customElements.define("issues-dismiss-modal", component(DismissModal, { useShadowDOM: false }));
