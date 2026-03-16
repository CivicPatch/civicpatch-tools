import { html, component } from 'haunted';

function PullRequestTabs({ pullRequests = [], selectedPullRequest, loading, onTabClick }) {
  function truncateBranchName(branchName, maxLength = 24) {
    if (!branchName) return "";
    if (branchName.length > maxLength) {
      return branchName.substring(0, maxLength);
    }
    return branchName;
  }

  if (loading) return html`<p>Loading pull requests...</p>`;

  return html`
    <div class="pr-tabs">
      <div class="pr-tabs__list">
        ${pullRequests.map(
          pr => html`
            <a
              href="#"
              class="pr-tabs__link ${selectedPullRequest?.branch_name === pr.branch_name ? 'active' : ''}"
              @click=${(e) => { e.preventDefault(); onTabClick?.(pr); }}
            >${truncateBranchName(pr.branch_name)}</a>
          `
        )}
        <a
          href="#"
          class="pr-tabs__link ${!selectedPullRequest ? 'active' : ''}"
          @click=${(e) => { e.preventDefault(); onTabClick?.(null); }}
        >Existing Data</a>
      </div>
    </div>
  `;
}

customElements.define(
  'civ-pull-request-tabs',
  component(PullRequestTabs, { useShadowDOM: false })
);
