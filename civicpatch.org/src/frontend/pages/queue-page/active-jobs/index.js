import "./active-jobs.css";
import { html } from "lit-html";
import { component } from "haunted";
import { dateStringToFriendly } from "../../../utils/date-utils.js";
import { Pagination } from "../../../components/pagination/index.js";

function ActiveJobs({ jobs, page = 1, totalPages = 1, perPage = 25, onPageChange, onPerPageChange }) {
  if (!jobs || (jobs.length === 0 && totalPages <= 1)) return null;

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
            <th>Created</th>
            <th>Last updated</th>
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
              <td class="aj-meta">${dateStringToFriendly(job.created_at)}</td>
              <td class="aj-meta">${dateStringToFriendly(job.updated_at)}</td>
            </tr>
          `)}
        </tbody>
      </table>
      ${Pagination({ page, totalPages, onPrevious: () => onPageChange(page - 1), onNext: () => onPageChange(page + 1), perPage, onPerPageChange })}
    </div>
  `;
}

customElements.define("queue-active-jobs", component(ActiveJobs, { useShadowDOM: false }));
