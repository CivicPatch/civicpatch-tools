import "./active-jobs.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { durationBetween } from "../../../utils/date-utils.js";
import { Pagination } from "../../../components/pagination/index.js";
import { cancelJob } from "../../../api.js";

function ActiveJobs({ jobs, page = 1, totalPages = 1, perPage = 25, onPageChange, onPerPageChange, onCancel, canCancel }) {
  const [cancellingIds, setCancellingIds] = useState(new Set());

  if (!jobs || (jobs.length === 0 && totalPages <= 1)) return null;

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

  return html`
    <div class="aj-section">
      <div class="queue-page__section-label">Active jobs</div>
      <table class="aj-table" role="grid">
        <thead>
          <tr>
            <th>Jurisdiction</th>
            <th>State</th>
            <th>Status</th>
            <th>Progress</th>
            <th>Request ID</th>
            <th>Duration</th>
            ${canCancel ? html`<th></th>` : null}
          </tr>
        </thead>
        <tbody>
          ${jobs.map(job => html`
            <tr>
              <td>
                <a class="aj-name" href="/${job.jurisdiction_path}">
                  ${job.jurisdiction_name || job.jurisdiction_ocdid}
                </a>
              </td>
              <td class="aj-meta">${job.state}</td>
              <td class="aj-meta">${job.status}</td>
              <td class="aj-meta">${job.progress ?? 0}%</td>
              <td class="aj-meta aj-mono aj-request-id">${job.request_id}</td>
              <td class="aj-meta">${durationBetween(job.created_at, job.updated_at)}</td>
              ${canCancel ? html`
                <td>
                  <button
                    class="aj-cancel-btn"
                    ?disabled=${cancellingIds.has(job.request_id)}
                    @click=${() => handleCancel(job.request_id)}
                  >${cancellingIds.has(job.request_id) ? "Cancelling…" : "Cancel"}</button>
                </td>
              ` : null}
            </tr>
          `)}
        </tbody>
      </table>
      ${Pagination({ page, totalPages, onPrevious: () => onPageChange(page - 1), onNext: () => onPageChange(page + 1), perPage, onPerPageChange })}
    </div>
  `;
}

customElements.define("queue-active-jobs", component(ActiveJobs, { useShadowDOM: false }));
