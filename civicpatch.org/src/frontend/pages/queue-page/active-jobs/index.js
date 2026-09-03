import "./active-jobs.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { durationBetween } from "../../../utils/date-utils.js";
import { Pagination } from "../../../components/pagination/index.js";
import { cancelPipelineRun } from "../../../api.js";
import { jurisdictionOcdidToPath } from "../../../components/ocdid-utils.js";

function ActiveJobs({ jobs, page = 1, totalPages = 1, perPage = 25, onPageChange, onPerPageChange, onCancel, canCancel }) {
  const [cancellingIds, setCancellingIds] = useState(new Set());

  if (!jobs || (jobs.length === 0 && totalPages <= 1)) return null;

  const handleCancel = async (changesetId) => {
    setCancellingIds(prev => new Set(prev).add(changesetId));
    try {
      await cancelPipelineRun(changesetId);
      if (onCancel) onCancel(changesetId);
    } catch (_) {
      // noop — leave the row visible so the user can retry
    } finally {
      setCancellingIds(prev => {
        const next = new Set(prev);
        next.delete(changesetId);
        return next;
      });
    }
  };

  return html`
    <div class="pipeline-run-section">
      <div class="queue-page__section-label">Active jobs</div>
      <table class="pipeline-run-table" role="grid">
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
                <a class="pipeline-run-name" href="/${jurisdictionOcdidToPath(job.jurisdiction_path)}">
                  ${job.jurisdiction_name || job.jurisdiction_ocdid}
                </a>
              </td>
              <td class="pipeline-run-meta">${job.state}</td>
              <td class="pipeline-run-meta">${job.status}</td>
              <td class="pipeline-run-meta">${job.progress ?? 0}%</td>
              <td class="pipeline-run-meta pipeline-run-mono pipeline-run-changeset-id">${job.changeset_id}</td>
              <td class="pipeline-run-meta">${durationBetween(job.created_at, job.updated_at)}</td>
              ${canCancel ? html`
                <td>
                  <button
                    class="pipeline-run-cancel-btn"
                    ?disabled=${cancellingIds.has(job.changeset_id)}
                    @click=${() => handleCancel(job.changeset_id)}
                  >${cancellingIds.has(job.changeset_id) ? "Cancelling…" : "Cancel"}</button>
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

customElements.define("queue-active-pipeline-runs", component(ActiveJobs, { useShadowDOM: false }));
