import { component } from "haunted";
import { html } from "lit-html";
import "../../../components/basic/modal.js";

function fmtDate(d) {
  if (!d) return "";
  const p = new Date(d);
  if (isNaN(p)) return String(d);
  return `${String(p.getMonth() + 1).padStart(2, "0")}/${String(p.getDate()).padStart(2, "0")}/${p.getFullYear()}`;
}

function getDurationString(created_at, updated_at) {
  const duration = (new Date(updated_at) - new Date(created_at)) / 1000;
  const minutes = Math.floor(duration / 60);
  const seconds = Math.round(duration % 60);
  return `${minutes}m ${seconds}s`;
}

function HistoryModal({ open, item, onClose }) {
  if (!item) return null;

  return html`
    <civ-modal
      .title=${"Details"}
      .content=${html`
        <div>
          <p><strong>Date / Time:</strong> ${fmtDate(item.created_at)}</p>
          <p><strong>Request ID:</strong> <code>${item.changeset_id}</code></p>
          <p><strong>Job status:</strong> ${item.pipeline_run_status}</p>
          <p><strong>Progress:</strong> ${item.pipeline_run_progress ?? "?"}%</p>
          <p><strong>Time to scrape:</strong> ${getDurationString(item.created_at, item.updated_at)}</p>
          ${item.change_url ? html`
            <p><strong>Published to:</strong> <a href="${item.change_url}" target="_blank" rel="noopener">${item.change_url}</a></p>
            <p><strong>Review status:</strong> ${item.review_status}</p>
          ` : null}
          <p><strong>URLs scraped:</strong></p>
          <ul>
            ${item.source_urls && item.source_urls.length > 0
              ? item.source_urls.map((url) => html`<li><a href="${url}" target="_blank" rel="noopener">${url}</a></li>`)
              : html`<li><em>No source URLs</em></li>`}
          </ul>
        </div>
      `}
      .modalProps=${{ open, onClose, closeOnBackdropClick: true }}
    ></civ-modal>
  `;
}

customElements.define("civ-history-modal", component(HistoryModal, { useShadowDOM: false }));
