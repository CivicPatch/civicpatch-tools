import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { fetchNotes, createNote, dismissIssue } from "../../api.js";
import { formatIssueType, formatDate } from "./utils.js";
import "../../components/basic/modal.js";

function DismissModal(host) {
  const issue = host.issue;

  const [dismissNote, setDismissNote] = useState("");
  const [dismissNotes, setDismissNotes] = useState(null);
  const [dismissLoading, setDismissLoading] = useState(false);

  useEffect(() => {
    if (!issue) return;
    const ocdid = issue.jurisdictions?.[0]?.jurisdiction_ocdid;
    if (ocdid) {
      fetchNotes(ocdid, 1, 5)
        .then((r) => setDismissNotes(r.data || []))
        .catch(() => setDismissNotes([]));
    } else {
      setDismissNotes([]);
    }
  }, []);

  const dispatch = (name, detail) =>
    host.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));

  const handleClose = () => dispatch("modal-close", {});

  const handleConfirm = async () => {
    setDismissLoading(true);
    try {
      const ocdid = issue.jurisdictions?.[0]?.jurisdiction_ocdid;
      const label = formatIssueType(issue.issue_type);
      const noteBody = dismissNote.trim()
        ? `Dismissed — ${label}: ${dismissNote.trim()}`
        : `Dismissed — ${label}`;
      if (ocdid) await createNote(ocdid, noteBody);
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
    ${dismissNotes === null
      ? html`<div class="issues-page__modal-source-loading">Loading notes…</div>`
      : dismissNotes.length
      ? html`
        <div class="issues-page__modal-source">
          <div class="issues-page__modal-source-label">Recent notes</div>
          ${dismissNotes.map((n) => html`
            <div class="issues-page__modal-source-entry">
              <div class="issues-page__modal-source-people">${n.created_by_display_name || "Unknown"} · ${formatDate(n.created_at)}</div>
              <div>${n.body}</div>
            </div>
          `)}
        </div>
      `
      : null}
    <label>
      Note <span class="issues-page__modal-optional">(optional)</span>
      <textarea
        class="issues-page__dismiss-note"
        placeholder="Reason for dismissing…"
        rows="3"
        .value=${dismissNote}
        @input=${(e) => setDismissNote(e.target.value)}
      ></textarea>
    </label>
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
