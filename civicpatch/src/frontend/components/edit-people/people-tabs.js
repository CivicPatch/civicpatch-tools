import { html, component } from 'haunted';

function PeopleTabs({ pullRequests = [], selectedPullRequest, loading, onTabClick }) {
  function truncateBranchName(branchName, maxLength = 24) {
    if (!branchName) return "";
    if (branchName.length > maxLength) {
      return branchName.substring(0, maxLength);
    }
    return branchName;
  }

  if (loading) return html`<p>Loading pull requests...</p>`;

  function requestIdToFriendly(requestId) {
    if (!requestId) return "";
    const parts = requestId.split("-");
    return parts.length > 1 ? parts[0] : requestId;
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
            >${truncateBranchName(requestIdToFriendly(pr.request_id))}</a>
          `
        )}
        <a
          href="#"
          class="people-tabs__link ${!selectedPullRequest ? 'active' : ''}"
          @click=${(e) => { e.preventDefault(); onTabClick?.(null); }}
        >Existing Data</a>
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
