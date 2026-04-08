import { component, useState } from "haunted";
import { html } from "lit-html";
import { dateStringToFriendly } from "../../utils/date-utils.js";
import "./scrape-history-modal.js";
import "../status-badge.js";

function ScrapeHistoryList({ history, jobStatus }) {
  let parsedHistory = history?.["data"] ?? [];

  if (jobStatus && jobStatus.request_id) {
    parsedHistory = parsedHistory.map(job =>
      job.request_id === jobStatus.request_id
        ? { ...job, progress: jobStatus.progress, status: jobStatus.status }
        : job
    );
  }

  const [modalOpen, setModalOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState(null);

  const openFor = (job) => { setSelectedJob(job); setModalOpen(true); };
  const closeModal = () => { setModalOpen(false); setSelectedJob(null); };

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
        return { bg: "var(--pico-ins-background)", color: "var(--pico-ins-color)" };
      case "failed":
      case "error":
        return { bg: "var(--pico-del-background)", color: "var(--pico-del-color)" };
      case "finalize":
        return { bg: "var(--pico-muted-background)", color: "var(--pico-muted-color)" };
      default:
        return { bg: "var(--pico-info-background)", color: "var(--pico-info-color)" };
    }
  };

  return html`
    <style>
      .sh-section {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
      }
      .sh-title {
        margin: 0;
        font-size: 0.8125rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--pico-muted-color);
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--pico-muted-border-color);
      }
      .sh-empty {
        font-size: 0.875rem;
        color: var(--pico-muted-color);
        margin: 0;
      }
      .sh-scroll {
        max-height: 300px;
        overflow-y: auto;
      }
      .sh-table {
        margin: 0;
        font-size: inherit;
        font-family: inherit;
      }
      .sh-table td {
        vertical-align: middle;
        padding: 0.4rem 0.5rem;
      }
      .sh-table tr:last-child td {
        border-bottom: none;
      }
      .date-btn {
        all: unset;
        cursor: pointer;
        color: var(--pico-primary);
        font-size: 0.875rem;
      }
      .date-btn:hover { opacity: 0.75; }
      .duration-cell {
        font-size: 0.8rem;
        color: var(--pico-muted-color);
        text-align: right;
        white-space: nowrap;
      }
      progress {
        width: 100%;
        height: 0.3rem;
        margin-top: 0.2rem;
      }
    </style>

    <div class="sh-section">
      <h4 class="sh-title">Scrape History</h4>

      ${!parsedHistory || parsedHistory.length === 0 ? html`
        <p class="sh-empty">No scrape history available.</p>
      ` : html`
        <div class="sh-scroll">
          <table class="sh-table" role="grid">
            <tbody>
              ${parsedHistory.map(job => html`
                <tr>
                  <td>
                    <button class="date-btn" @click=${() => openFor(job)}>
                      ${dateStringToFriendly(job.created_at)}
                    </button>
                    ${job.progress !== undefined && job.progress !== 100 ? html`
                      <progress value=${job.progress ?? 0} max="100"></progress>
                    ` : null}
                  </td>
                  <td class="duration-cell">
                    ${job.created_at && job.updated_at
                      ? getDurationString(job.created_at, job.updated_at)
                      : ""}
                  </td>
                  <td>
                    <civ-status-badge
                      label="${job.status}"
                      bg="${statusBadgeProps(job.status).bg}"
                      color="${statusBadgeProps(job.status).color}"
                    ></civ-status-badge>
                  </td>
                </tr>
              `)}
            </tbody>
          </table>
        </div>
      `}
    </div>

    <civ-scrape-history-modal
      .open=${modalOpen}
      .job=${selectedJob}
      .onClose=${closeModal}
    ></civ-scrape-history-modal>
  `;
}

customElements.define(
  "civ-scrape-history-list",
  component(ScrapeHistoryList, { useShadowDOM: false })
);