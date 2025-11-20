import { component } from "haunted";
import { html, css } from "lit-html";

function ScrapeHistory({ scrapes = [] }) {

  return html`
    <ul style="padding-left: 0;">
      ${scrapes.length === 0
        ? html`<li style="list-style-type: none">No scrape history available.</li>`
        : scrapes.map(
            (scrape) => html`
              <li>
                <strong>${new Date(scrape.timestamp).toLocaleString()}:</strong>
                ${scrape.status} - ${scrape.message}
              </li>
            `
          )}
    </ul>
  `;
}

customElements.define(
  'civ-scrape-history',
  component(ScrapeHistory, { useShadowDOM: false, observedAttributes: [] })
);