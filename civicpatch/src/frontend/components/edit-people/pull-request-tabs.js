import { html, component, useEffect, useState } from 'haunted';
import { config } from '../../assets/config.js';
const API_URL = config.apiUrl;

function PullRequestTabs(props) {
  const { jurisdiction_ocdid } = props;

  const [selectedPullRequest, setSelectedPullRequest] = useState(null);
  const [pullRequests, setPullRequests] = useState([]);
  const [loading, setLoading] = useState(true);

  const element = this;

  function dispatchSelectedPullRequest(pullRequest) {
    const event = new CustomEvent('selected-pull-request', {
      detail: { pullRequest },
      bubbles: true,
      composed: true
    });
    // Dispatch from the component's root element
    element?.dispatchEvent(event);
  }

  useEffect(() => {
    if (!jurisdiction_ocdid) return;
    setLoading(true);
    fetch(
      `${API_URL}/api/v1/pull_requests?jurisdiction_ocdid=${encodeURIComponent(jurisdiction_ocdid)}`,
      {
        credentials: "include"
      }
    )
      .then(r => r.json())
      .then(data => {
        const pullRequests = data.data || [];
        const pullRequest = pullRequests.length > 0 ? pullRequests[0] : null;

        // First one should always be selected
        setSelectedPullRequest(pullRequest);
        setPullRequests(pullRequests);
        dispatchSelectedPullRequest(pullRequest);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [jurisdiction_ocdid]);

  function handleTabClick(branchName) {
    const pullRequest = pullRequests.find(pr => pr.branch_name === branchName);
    setSelectedPullRequest(pullRequest);
    dispatchSelectedPullRequest(pullRequest);
  }

  function truncateBranchName(branchName, maxLength = 24) {
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
              @click=${(e) => { e.preventDefault(); handleTabClick(pr.branch_name); }}
            >${truncateBranchName(pr.branch_name)}</a>
          `
        )}
        <a
          href="#"
          class="pr-tabs__link ${!selectedPullRequest ? 'active' : ''}"
          @click=${(e) => { e.preventDefault(); handleTabClick(null); }}
        >Existing Data</a>
      </div>
    </div>
  `;
}

customElements.define(
  'civ-pull-request-tabs',
  component(PullRequestTabs, { useShadowDOM: false, observedAttributes: ['jurisdiction_ocdid'] })
);