import { html } from "lit-html";
import { component } from "haunted";
import { dateStringToFriendly } from "../../../utils/date-utils.js";

function ActiveJobs({ jobs }) {
  if (!jobs || jobs.length === 0) return null;

  return html`
    <style>
      .aj-section { margin-bottom: 2rem; }
      .aj-label {
        font-size: 0.8125rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--pico-muted-color);
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--pico-muted-border-color);
        margin-bottom: 0.75rem;
      }
      .aj-table { width: 100%; font-size: 0.8125rem; margin: 0; }
      .aj-table td { padding: 0.3rem 0.5rem; vertical-align: middle; }
      .aj-table tr:last-child td { border-bottom: none; }
      .aj-ocdid { font-family: var(--pico-font-family-monospace); color: var(--pico-primary); }
      .aj-status { color: var(--pico-muted-color); }
      .aj-progress { color: var(--pico-muted-color); text-align: right; white-space: nowrap; }
    </style>

    <div class="aj-section">
      <div class="aj-label">Active jobs (${jobs.length})</div>
      <table class="aj-table" role="grid">
        <tbody>
          ${jobs.map(job => html`
            <tr>
              <td>
                <a class="aj-ocdid" href="/${job.jurisdiction_path}">
                  ${job.jurisdiction_ocdid}
                </a>
              </td>
              <td class="aj-status">${job.status}</td>
              <td class="aj-progress">${job.progress ?? 0}% &middot; ${dateStringToFriendly(job.created_at)}</td>
            </tr>
          `)}
        </tbody>
      </table>
    </div>
  `;
}

customElements.define("queue-active-jobs", component(ActiveJobs, { useShadowDOM: false }));
