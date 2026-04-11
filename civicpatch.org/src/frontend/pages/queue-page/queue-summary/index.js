import { html } from "lit-html";
import { component } from "haunted";
import "../../../components/stat-cards/index.js";

function QueueSummary({ summary }) {
  const withIssuesPct = summary?.total_with_pr
    ? ((summary.with_issues / summary.total_with_pr) * 100).toFixed(1)
    : null;

  const stats = [
    {
      key: "with_issues",
      label: "With issues",
      value: summary.with_issues,
      sub: `${withIssuesPct}% of ${summary.total_with_pr} open PRs`,
      copyText: `[with issues] ${summary.with_issues} (${withIssuesPct}% of ${summary.total_with_pr} open PRs)`,
    },
    {
      key: "open",
      label: "Open pull requests",
      value: summary.total_with_pr,
      sub: "awaiting review or merge",
      copyText: `[open pull requests] ${summary.total_with_pr}`,
    },
  ];

  return html`
    <section class="queue-summary">
      <stat-cards .stats=${stats}></stat-cards>
    </section>
  `;
}

customElements.define("queue-summary", component(QueueSummary, { useShadowDOM: false }));
