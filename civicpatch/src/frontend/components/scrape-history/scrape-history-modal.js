import { component, useEffect } from "haunted";
import { html } from "lit-html";
import "../basic/modal.js";

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

function ScrapeHistoryModal({ open, job, onClose }) {
  if (!job) return null;

  return html`
    <civ-modal
      .title=${"Scrape Details"}
      .content=${html`
        <div>
          <p><strong>Date / Time:</strong> ${fmtDate(job.created_at)}</p>
          <p><strong>Status:</strong> ${job.status}</p>
          <p><strong>Progress:</strong> ${job.progress ?? "?"}%</p>
          <p><strong>Time to scrape:</strong> ${getDurationString(job.created_at, job.updated_at)}</p>
          <p><strong>URLs scraped:</strong></p>
          <ul>
            ${job.source_urls && job.source_urls.length > 0
              ? job.source_urls.map((url) => html`<li><a href="${url}" target="_blank" rel="noopener">${url}</a></li>`)
              : html`<li><em>No source URLs</em></li>`}
          </ul>
          <!-- Optionally, render a new component here and pass job.request_id -->
          <!-- <pull-request-details .requestId=${job.request_id}></pull-request-details> -->
        </div>
      `}
      .modalProps=${{ open, onClose, closeOnBackdropClick: true }}
    ></civ-modal>
  `;
}

customElements.define("civ-scrape-history-modal", component(ScrapeHistoryModal, { useShadowDOM: false }));