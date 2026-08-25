import { component, useState } from "haunted";
import { html } from "lit-html";
import { dateStringToFriendly, durationBetween } from "../../../utils/date-utils.js";
import { cancelPipelineRun } from "../../../api.js";
import "./history-modal.js";
import "../../../components/status-badge.js";
import { REQUEST_TYPE } from "../awaiting-review.ts";
import { REVIEW_STATUS } from "../../../components/review-status.js";
import { LOGIN_PATH, reviewSessionUrl as reviewUrl } from "../../review-routes.ts";
import { jurisdictionOcdidToState } from "../../../components/ocdid-utils.js";

function HistoryList({ history, pipelineRunStatus, canCancel, onCancel, isSignedIn = false }) {
  let parsedHistory = history?.["data"] ?? [];

  if (pipelineRunStatus && pipelineRunStatus.request_id) {
    parsedHistory = parsedHistory.map(item =>
      item.request_id === pipelineRunStatus.request_id
        ? { ...item, pipeline_run_progress: pipelineRunStatus.progress, pipeline_run_status: pipelineRunStatus.status }
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
      await cancelPipelineRun(requestId);
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
      case "success":
      case "resolved":
      case "merged":
        return { bg: "var(--pico-ins-background)", color: "var(--pico-ins-color)" };
      case "error":
      case "closed":
        return { bg: "var(--pico-del-background)", color: "var(--pico-del-color)" };
      case "cancelled":
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
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--pico-muted-color);
        padding-bottom: 0.4rem;
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
        width: 100%;
        /* styles.css sets table-layout: fixed globally, which (with a width:100%
           column) starves the other columns to zero and overlaps their text.
           Opt back into auto so the status column can absorb the slack. */
        table-layout: auto;
        font-size: 0.75rem;
        font-family: inherit;
      }
      /* Roomier than it was: the status cell holds two badges and an arrow, and at the old
         density a wrapped second badge collided with the first. Costs ~0.4rem per row, which
         the 300px scroll absorbs. */
      .sh-table td {
        vertical-align: middle;
        padding: 0.5rem 0.6rem;
      }
      .sh-table td:first-child {
        white-space: nowrap;
      }
      /* The status column absorbs the table's slack; the others hug their content. */
      .sh-table td:nth-child(3) {
        width: 100%;
      }
      .sh-table tr:last-child td {
        border-bottom: none;
      }
      .status-cell {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.4rem;
        row-gap: 0.3rem;
        --badge-font-size: 0.72rem;
        --badge-padding: 0.15rem 0.5rem;
      }
      .status-cell .badge {
        white-space: normal;
        overflow-wrap: anywhere;
      }
      /* The scrape is pending until someone decides: the badge says so, this is the way in. */
      .sh-review-link {
        font-size: 0.7rem;
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
        font-size: 0.75rem;
      }
      .date-btn:hover { opacity: 0.75; }
      .duration-cell {
        font-size: 0.7rem;
        color: var(--pico-muted-color);
        text-align: right;
        white-space: nowrap;
      }
      .sh-cancel-btn {
        font-size: 0.68rem;
        padding: 0.12rem 0.45rem;
        cursor: pointer;
      }
      progress {
        display: block;
        width: 100%;
        height: 0.3rem;
        margin-top: 0.2rem;
      }
    </style>

    <div class="sh-section">
      <h4 class="sh-title">Past</h4>

      ${!parsedHistory || parsedHistory.length === 0 ? html`
        <p class="sh-empty">No scrapes yet.</p>
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
                    ${item.pipeline_run_progress !== undefined && item.pipeline_run_progress !== 100 && !item.review_status ? html`
                      <progress value=${item.pipeline_run_progress ?? 0} max="100"></progress>
                    ` : null}
                  </td>
                  <td class="duration-cell">
                    ${durationBetween(item.created_at, item.updated_at)}
                  </td>
                  <td>
                    <div class="status-cell">
                      <civ-status-badge
                        label="${item.pipeline_run_status}"
                        bg="${statusBadgeProps(item.pipeline_run_status).bg}"
                        color="${statusBadgeProps(item.pipeline_run_status).color}"
                      ></civ-status-badge>
                      ${item.review_status ? html`
                        <span class="status-arrow">→</span>
                        ${item.open_data_url ? html`
                          <a href="${item.open_data_url}" target="_blank" rel="noopener" style="text-decoration: none;">
                            <civ-status-badge
                              label="${item.review_status}"
                              bg="${statusBadgeProps(item.review_status).bg}"
                              color="${statusBadgeProps(item.review_status).color}"
                            ></civ-status-badge>
                          </a>
                        ` : html`
                          <civ-status-badge
                            label="${item.review_status}"
                            bg="${statusBadgeProps(item.review_status).bg}"
                            color="${statusBadgeProps(item.review_status).color}"
                          ></civ-status-badge>
                        `}
                        ${item.review_status === REVIEW_STATUS.PENDING && item.request_type !== REQUEST_TYPE.JURISDICTION_MANUAL_EDIT ? html`
                          <a class="sh-review-link" href=${isSignedIn
                            ? reviewUrl(jurisdictionOcdidToState(item.jurisdiction_ocdid), item.request_id)
                            : LOGIN_PATH}>
                            ${isSignedIn ? "Needs review →" : "Sign in to review"}
                          </a>
                        ` : null}
                      ` : null}
                    </div>
                  </td>
                  ${canCancel && item.is_running ? html`
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
