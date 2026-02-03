import { component, useState } from "haunted";
import { html } from "lit-html";
import "./scrape-history-modal.js";

const DUMMY_DATA = [
  { id: 1, name: "Scrape Job 1", status: "Completed", start_date: "2024-01-01", duration_in_s: 120, 
        source_urls: ["https://example.com", "https://example.com/2"], progress: 100 },
  { id: 2, name: "Scrape Job 2", status: "In Progress", start_date: "2024-01-02", duration_in_s: 150, source_urls: ["https://example.org"], progress: 50 },
  { id: 3, name: "Scrape Job 3", status: "Failed", start_date: "2024-01-03", duration_in_s: 90, source_urls: [], progress: 0 },
];

function renderProgressBar(progress) {
  if (progress === 100) return null;
  return html`
    <div class="progress-bar-container">
      <progress value=${progress ?? 0} max="100">
        ${progress ?? 0}%
      </progress>
    </div>
  `;
}

function ScrapeHistoryList({ history, jobStatus }) {
  // Use history as an object/array directly (no parsing if passed as property)
  const historyData = JSON.parse(history)
  let parsedHistory = historyData["data"]

  // If jobStatus is present and matches a job, update that job's progress/status
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
    // Friendly formatting to minutes, seconds rounded
    const minutes = Math.floor(duration / 60);
    const seconds = Math.round(duration % 60);
    return `${minutes}m ${seconds}s`;
  }

  if (!parsedHistory || parsedHistory.length === 0) {
    return html`<p>No scrape history available.</p>`;
  }

  return html`
    <style>
      ul.list { 
        padding: 0; 
        margin: 0; 
        max-height: 300px;
        overflow-y: auto;
        padding-right: 1rem;
      }
      ul li { list-style: none; margin: 0; }
      .item { padding: 0.5rem 0; }
      .row { display: grid; grid-template-columns: 1fr auto; gap: 0.75rem; align-items: center; }
      .btn { all: unset; cursor: pointer; text-decoration: underline; display: inline-block; }
      .pill { font-weight: 600; padding: 0.25rem 0.5rem; border-radius: 999px; background: rgba(0,0,0,0.04); font-size: 0.9rem; }
      .pill.completed { background: #e6f9ea; color: #117a2d; }
      .pill.in-progress { background: #fff7e6; color: #99660b; }
      .pill.failed { background: #ffecec; color: #9b1f1f; }
      .progress-bar-container { margin-top: 0.5rem; }
      progress { width: 100%; }
    </style>

    <ul class="list">
      ${parsedHistory.map(
        (job) => {
          const statusClass = job.status ? job.status.toLowerCase().replace(/\s+/g, "-") : "";
          return html`
            <li class="item">
              <div class="row">
                <button class="btn" @click=${() => openFor(job)}>
                  ${fmtDate(job.created_at)}
                </button>
                <div><span class="pill ${statusClass}">${job.status}</span></div>
              </div>
              ${renderProgressBar(job.progress)}
            </li>
          `;
        }
      )}
    </ul>

    <hr />

    <civ-scrape-history-modal
      .open=${modalOpen}
      .job=${selectedJob}
      .onClose=${closeModal}
    ></civ-scrape-history-modal>
  `;
}

customElements.define("civ-scrape-history-list", component(ScrapeHistoryList, { useShadowDOM: false }));