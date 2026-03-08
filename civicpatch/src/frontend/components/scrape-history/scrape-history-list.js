import { component, useState } from "haunted";
import { html } from "lit-html";
import "./scrape-history-modal.js";
import "../status-badge.js";

function ScrapeHistoryList({ history, jobStatus }) {
  const historyData = JSON.parse(history);
  let parsedHistory = historyData["data"];

  if (jobStatus && jobStatus.request_id) {
    parsedHistory = parsedHistory.map(job =>
      job.request_id === jobStatus.request_id
        ? { ...job, progress: jobStatus.progress, status: jobStatus.status }
        : job
    );
  }

  const [modalOpen, setModalOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState(null);

  const openFor = (job) => {
    setSelectedJob(job);
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setSelectedJob(null);
  };

  const fmtDate = (d) => {
    if (!d) return "";
    const p = new Date(d);
    if (isNaN(p)) return String(d);
    return `${String(p.getMonth() + 1).padStart(2, "0")}/${String(p.getDate()).padStart(2, "0")}/${p.getFullYear()}`;
  };

  const getDurationString = (created_at, updated_at) => {
    const duration = (new Date(updated_at) - new Date(created_at)) / 1000;
    const minutes = Math.floor(duration / 60);
    const seconds = Math.round(duration % 60);
    return `${minutes}m ${seconds}s`;
  };

  const statusBadgeProps = (status) => {
    const s = (status || "").toLowerCase().replace(/\s+/g, "-");
    switch (s) {
      case "done":
        return { bg: "var(--pico-ins-color)" };
      case "failed":
      case "error":
        return { bg: "var(--pico-del-color)", color: "var(--pico-del-inverse)" };
      default:
        return { bg: "var(--pico-warn-color)" };
    }
  };

  if (!parsedHistory || parsedHistory.length === 0) {
    return html`
      <article>
        <header><strong>Scrape History</strong></header>
        <p>No scrape history available.</p>
      </article>
    `;
  }

  return html`
    <style>
      .scrape-history-table { margin: 0; }
      .scrape-history-table td { vertical-align: middle; padding: 0.5rem 0.75rem; }
      .scrape-history-table tr:last-child td { border-bottom: none; }
      .date-btn { all: unset; cursor: pointer; text-decoration: underline; color: var(--pico-primary); }
      .date-btn:hover { opacity: 0.8; }
      .duration-cell { font-size: 0.8rem; color: var(--pico-muted-color); text-align: right; white-space: nowrap; }
      progress { width: 100%; height: 0.4rem; margin-top: 0.25rem; }
      .table-scroll { max-height: 300px; overflow-y: auto; }
    </style>

    <article>
      <header><strong>Scrape History</strong></header>
      <div class="table-scroll">
        <table class="scrape-history-table" role="grid">
        <tbody>
          ${parsedHistory.map(job => html`
            <tr>
              <td>
                <button class="date-btn" @click=${() => openFor(job)}>
                  ${fmtDate(job.created_at)}
                </button>
                ${job.progress !== undefined && job.progress !== 100 ? html`
                  <progress value=${job.progress ?? 0} max="100"></progress>
                ` : null}
              </td>
              <td class="duration-cell">
                ${job.created_at && job.updated_at ? getDurationString(job.created_at, job.updated_at) : ""}
              </td>
              <td class="status-cell">
                <civ-status-badge
                  label="${job.status}"
                  bg="${statusBadgeProps(job.status).bg}"
                  color="${statusBadgeProps(job.status).color || ''}"
                ></civ-status-badge>
              </td>
            </tr>
          `)}
        </tbody>
        </table>
      </div>
    </article>

    <civ-scrape-history-modal
      .open=${modalOpen}
      .job=${selectedJob}
      .onClose=${closeModal}
    ></civ-scrape-history-modal>
  `;
}

customElements.define("civ-scrape-history-list", component(ScrapeHistoryList, { useShadowDOM: false }));