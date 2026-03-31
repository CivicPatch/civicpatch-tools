import { html, component } from 'haunted';

function PeopleTabs({ pullRequests = [], selectedPullRequest, loading, onTabClick }) {
  if (loading) return html`<p>Loading pull requests...</p>`;

  function prTabLabel(pr) {
    const date = pr.created_at ? pr.created_at.slice(0, 10) : "";
    const parts = pr.request_id ? pr.request_id.split("-") : [];
    const hash = parts.length > 1 ? parts[0] : pr.request_id ?? "";
    return `${date} ${hash}`;
  }

  return html`
    <div class="people-tabs">
      <div class="people-tabs__list">
        ${pullRequests.map(
          pr => html`
            <a
              href="#"
              class="people-tabs__link ${selectedPullRequest?.request_id === pr.request_id ? 'active' : ''}"
              @click=${(e) => { e.preventDefault(); onTabClick?.(pr); }}
            >${prTabLabel(pr)}</a>
          `
        )}
        <a
          href="#"
          class="people-tabs__link ${!selectedPullRequest ? 'active' : ''}"
          @click=${(e) => { e.preventDefault(); onTabClick?.(null); }}
        >Current</a>
        <a
          href="#"
          class="people-tabs__link ${selectedPullRequest === 'directory' ? 'active' : ''}"
          @click=${(e) => { e.preventDefault(); onTabClick?.('directory'); }}
        >Directory</a>
      </div>
    </div>
  `;
}

customElements.define(
  'civ-people-tabs',
  component(PeopleTabs, { useShadowDOM: false })
);
