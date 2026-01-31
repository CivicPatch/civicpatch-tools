import { component, useState } from "haunted";
import { html } from "lit-html";
import { map } from "lit/directives/map.js";
import "../modal.js";

const DUMMY_DATA = [
  { id: 1, name: "Scrape Job 1", status: "Completed", start_date: "2024-01-01", duration_in_s: 120, 
        source_urls: ["https://example.com", "https://example.com/2"], progress: 100 },
  { id: 2, name: "Scrape Job 2", status: "In Progress", start_date: "2024-01-02", duration_in_s: 150, source_urls: ["https://example.org"], progress: 50 },
  { id: 3, name: "Scrape Job 3", status: "Failed", start_date: "2024-01-03", duration_in_s: 90, source_urls: [], progress: 0 },
];

function ScrapeHistoryList() {
  const scrapeJobs = DUMMY_DATA;
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

  // debug-friendly modal content: shows raw JSON + mapped list
  const modalContent = selectedJob
    ? html`<div>
        <p><strong>Date / Time:</strong> ${fmtDate(selectedJob.start_date)}</p>
        <p><strong>Status:</strong> ${selectedJob.status}</p>
        <p><strong>Time to scrape:</strong> ${selectedJob.duration_in_s}s</p>
        <p><strong>URLs scraped:</strong></p>
        <ul>
          ${selectedJob.source_urls && selectedJob.source_urls.length > 0
            ? selectedJob.source_urls.map((url) => html`<li><a href="${url}" target="_blank" rel="noopener">${url}</a></li>`)
            : html`<li><em>No source URLs</em></li>`}
        </ul>
      </div>`
    : null;

  if (!scrapeJobs || scrapeJobs.length === 0) {
    return html`<p>No scrape history available.</p>`;
  }

  return html`
    <style>
      ul.list { padding: 0; margin: 0; }
      ul li { list-style: none; margin: 0; }
      .item { padding: 0.5rem 0; }
      .row { display: grid; grid-template-columns: 1fr auto; gap: 0.75rem; align-items: center; }
      .btn { all: unset; cursor: pointer; text-decoration: underline; display: inline-block; }
      .pill { font-weight: 600; padding: 0.25rem 0.5rem; border-radius: 999px; background: rgba(0,0,0,0.04); font-size: 0.9rem; }
      .pill.completed { background: #e6f9ea; color: #117a2d; }
      .pill.in-progress { background: #fff7e6; color: #99660b; }
      .pill.failed { background: #ffecec; color: #9b1f1f; }
    </style>

    <ul class="list">
      ${map(
        scrapeJobs,
        (job) => {
          const statusClass = job.status ? job.status.toLowerCase().replace(/\s+/g, "-") : "";
          return html`
            <li class="item">
              <div class="row">
                <button class="btn" @click=${() => openFor(job)}>
                  ${fmtDate(job.start_date)}
                </button>
                <div><span class="pill ${statusClass}">${job.status}</span></div>
              </div>
            </li>
          `;
        }
      )}
    </ul>

    <hr />

    <civ-modal
      .title=${"Scrape Details"}
      .content=${modalContent}
      .modalProps=${{ open: modalOpen, onClose: closeModal, closeOnBackdropClick: true }}
    ></civ-modal>
  `;
}

customElements.define("civ-scrape-history-list", component(ScrapeHistoryList, { useShadowDOM: false }));