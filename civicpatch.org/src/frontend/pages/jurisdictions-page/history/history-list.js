import { component, useState } from "haunted";
import { html } from "lit-html";
import { dateStringToFriendly, durationBetween } from "../../../utils/date-utils.js";
import { cancelJob } from "../../../api.js";
import { TERMINAL_JOB_STATUSES } from "../../../components/job-status.js";
import "./history-modal.js";
import "../../../components/status-badge.js";

function HistoryList({ history, jobStatus, canCancel, onCancel }) {
  let parsedHistory = history?.["data"] ?? [];

  if (jobStatus && jobStatus.request_id) {
    parsedHistory = parsedHistory.map(item =>
      item.request_id === jobStatus.request_id
        ? { ...item, job_progress: jobStatus.progress, job_status: jobStatus.status }
        : item
    );
  }

  const [modalOpen, setModalOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [cancellingIds, setCancellingIds] = useState(new Set());

  const openFor = (item) => { setSelectedItem(item); setModalOpen(true); };
  const closeModal = () => { setModalOpen(false); setSelectedItem(null); };

  const handleCancel = async (requestId) => {
    setCancellingIds(prev => new Set(prev).add(requestId));
    try {
      await cancelJob(requestId);
      if (onCancel) onCancel(requestId);
    } catch (_) {
      // noop — leave the row visible so the user can retry
    } finally {
      setCancellingIds(prev => {
        const next = new Set(prev);
        next.delete(requestId);
        return next;
      });
    }
  };

  const statusBadgeProps = (status) => {
    const s = (status || "").toLowerCase().replace(/\s+/g, "-");
    switch (s) {
      case "done":
      case "merged":
        return { bg: "var(--pico-ins-background)", color: "var(--pico-ins-color)" };
      case "failed":
      case "error":
      case "closed":
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
      .status-cell {
        display: flex;
        align-items: center;
        gap: 0.3rem;
        white-space: nowrap;
      }
      .status-arrow {
        font-size: 0.7rem;
        color: var(--pico-muted-color);
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
      .sh-cancel-btn {
        font-size: 0.75rem;
        padding: 0.15rem 0.5rem;
        cursor: pointer;
      }
      progress {
        width: 100%;
        height: 0.3rem;
        margin-top: 0.2rem;
      }
    </style>

    <div class="sh-section">
      <h4 class="sh-title">History</h4>

      ${!parsedHistory || parsedHistory.length === 0 ? html`
        <p class="sh-empty">No history available.</p>
      ` : html`
        <div class="sh-scroll">
          <table class="sh-table" role="grid">
            <tbody>
              ${parsedHistory.map(item => html`
                <tr>
                  <td>
                    <button class="date-btn" @click=${() => openFor(item)}>
                      ${dateStringToFriendly(item.created_at)}
                    </button>
                    ${item.job_progress !== undefined && item.job_progress !== 100 && !item.pull_request_status ? html`
                      <progress value=${item.job_progress ?? 0} max="100"></progress>
                    ` : null}
                  </td>
                  <td class="duration-cell">
                    ${durationBetween(item.created_at, item.updated_at)}
                  </td>
                  <td>
                    <div class="status-cell">
                      <civ-status-badge
                        label="${item.job_status}"
                        bg="${statusBadgeProps(item.job_status).bg}"
                        color="${statusBadgeProps(item.job_status).color}"
                      ></civ-status-badge>
                      ${item.pull_request_status ? html`
                        <span class="status-arrow">→</span>
                        <a href="${item.pull_request_url}" target="_blank" rel="noopener" style="text-decoration: none;">
                          <civ-status-badge
                            label="${item.pull_request_status}"
                            bg="${statusBadgeProps(item.pull_request_status).bg}"
                            color="${statusBadgeProps(item.pull_request_status).color}"
                          ></civ-status-badge>
                        </a>
                      ` : null}
                    </div>
                  </td>
                  ${canCancel && !TERMINAL_JOB_STATUSES.has(item.job_status) ? html`
                    <td>
                      <button
                        class="sh-cancel-btn"
                        ?disabled=${cancellingIds.has(item.request_id)}
                        @click=${() => handleCancel(item.request_id)}
                      >${cancellingIds.has(item.request_id) ? "Cancelling…" : "Cancel"}</button>
                    </td>
                  ` : html`<td></td>`}
                </tr>
              `)}
            </tbody>
          </table>
        </div>
      `}
    </div>

    <civ-history-modal
      .open=${modalOpen}
      .item=${selectedItem}
      .onClose=${closeModal}
    ></civ-history-modal>
  `;
}

customElements.define(
  "civ-history-list",
  component(HistoryList, { useShadowDOM: false })
);
