import "./tabs.css";
import { html, component } from "haunted";
import "../civ-tab-bar/civ-tab-bar.js";

function prTabLabel(pr) {
  const date = pr.created_at ? pr.created_at.slice(0, 10) : "";
  const parts = pr.request_id ? pr.request_id.split("-") : [];
  const hash = parts.length > 1 ? parts[0] : pr.request_id ?? "";
  return `${date} ${hash}`;
}

function getSelectedIndex(pullRequests, selectedPullRequest) {
  if (!selectedPullRequest) return pullRequests.length;
  const idx = pullRequests.findIndex(pr => pr.request_id === selectedPullRequest?.request_id);
  return idx >= 0 ? idx : pullRequests.length;
}

function PeopleTabs({ pullRequests = [], selectedPullRequest, loading, onTabClick }) {
  if (loading) return html`<p>Loading pull requests...</p>`;

  const tabs = [
    ...pullRequests.map(pr => ({ label: prTabLabel(pr) })),
    { label: "Current" },
  ];

  const selectedIndex = getSelectedIndex(pullRequests, selectedPullRequest);

  const handleTabClick = (idx) => {
    if (idx < pullRequests.length) onTabClick?.(pullRequests[idx]);
    else onTabClick?.(null);
  };

  return html`
    <div class="people-tabs">
      <civ-tab-bar
        .tabs=${tabs}
        .selectedIndex=${selectedIndex}
        .onTabClick=${handleTabClick}
      ></civ-tab-bar>
    </div>
  `;
}

customElements.define("civ-people-tabs", component(PeopleTabs, { useShadowDOM: false }));
