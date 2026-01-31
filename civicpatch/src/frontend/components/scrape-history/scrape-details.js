import { component } from "haunted";
import { html } from "lit-html";

const DummyScrapeJobInfo = {
    created_at: "2024-06-01T12:00:00Z",
    status: "Accepted",
    duration_in_s: 360,
    source_urls: ["https://example.com", "https://example.org"],
}

function formatDuration(seconds) {
    if (seconds == null) return "";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return [
        h ? `${h}h` : null,
        m ? `${m}m` : null,
        `${s}s`
    ].filter(Boolean).join(" ");
}

function ScrapeDetails({ detail = DummyScrapeJobInfo }) {
    const createdAt = detail?.created_at ? new Date(detail.created_at) : null;
    const formattedCreatedAt = createdAt ? createdAt.toLocaleString() : "";
    const duration = formatDuration(detail?.duration_in_s);
    const urls = detail?.source_urls || [];

    return html`
    <article class="container">
      <form>
        <div class="grid">
          <label>
            <span>Date / Time</span>
            <input type="text" value="${formattedCreatedAt}" readonly />
          </label>

          <label>
            <span>Status</span>
            <input type="text" value="${detail?.status || ""}" readonly />
          </label>

          <label>
            <span>Time to scrape</span>
            <input type="text" value="${duration}${detail?.duration_in_s != null ? ` (${detail.duration_in_s}s)` : ""}" readonly />
          </label>
        </div>

        <section>
          <h4>URLs scraped</h4>
          ${urls.length
            ? html`<ul>
                ${urls.map(
                  u => html`<li><a href="${u}" target="_blank" rel="noopener">${u}</a></li>`
                )}
              </ul>`
            : html`<p><em>No source URLs</em></p>`}
        </section>
      </form>
    </article>
    `
}

customElements.define('scrape-details', component(ScrapeDetails));