import { html, component, useEffect, useState } from 'haunted';
import { css } from 'lit';
import { config } from '../../assets/config.js';
const API_URL = config.apiUrl;

const styles = css`
  civ-pull-request-tabs .tabs {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }
  civ-pull-request-tabs .tabs ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    gap: 0.5rem;
  }
  civ-pull-request-tabs .tabs li {
    margin: 0;
  }
  civ-pull-request-tabs .tabs a {
    display: block;
    padding: 0.5rem 1rem;
    border: 1px solid #ccc;
    background: rgb(var(--catppuccin-crust));
    text-decoration: none;
    color: inherit;
    cursor: pointer;
  }
  civ-pull-request-tabs .tabs a.active {
    background: rgb(var(--catppuccin-sapphire));
    color: white;
  }
  civ-pull-request-tabs .tab-content {
    padding: 1rem;
    border: 1px solid #ccc;
    background: rgb(var(--catppuccin-crust));
  }
`;

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
      `${API_URL}/api/v1/pull_requests/open?jurisdiction_ocdid=${encodeURIComponent(jurisdiction_ocdid)}`,
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
    <style>${styles}</style>
    <div style="margin-bottom: 2rem;">
      <h3>Data Sources</h3>
      <nav class="tabs">
        <ul>
          ${pullRequests.map(
            pr => html`
              <li>
                <a 
                  href="#" 
                  class=${selectedPullRequest?.branch_name === pr.branch_name ? 'active' : ''} 
                  @click=${(e) => {
                    e.preventDefault();
                    handleTabClick(pr.branch_name);
                  }}
                >
                  ${truncateBranchName(pr.branch_name)}
                </a>
              </li>
            `
          )}
          <li>
            <a 
              href="#" 
              class=${!selectedPullRequest ? 'active' : ''} 
              @click=${(e) => {
                e.preventDefault();
                handleTabClick(null);
              }}
            >
              Existing Data (TBD)
            </a>
          </li>
        </ul>
      </nav>
    </div>
  `;
}

customElements.define(
  'civ-pull-request-tabs',
  component(PullRequestTabs, { useShadowDOM: false, observedAttributes: ['jurisdiction_ocdid'] })
);