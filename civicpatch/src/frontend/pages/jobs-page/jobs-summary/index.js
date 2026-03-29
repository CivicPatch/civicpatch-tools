import { html } from "lit-html";
import { component, useState } from "haunted";

function JobsSummary({ summary }) {
  const [copied, setCopied] = useState(null);

  const copy = (key, text) => {
    navigator.clipboard.writeText(String(text));
    setCopied(key);
    setTimeout(() => setCopied(null), 1500);
  };

  const withIssuesPct = summary?.total_with_pr
    ? ((summary.with_issues / summary.total_with_pr) * 100).toFixed(1)
    : null;

  return html`
    <section class="jobs-summary">
      <div class="jobs-summary__grid">
        <button class="jobs-summary__stat-card" @click=${() => copy("with_issues", `[with issues] ${summary.with_issues} (${withIssuesPct}% of ${summary.total_with_pr} open PRs)`)}>
          <div class="jobs-summary__stat-label">With issues</div>
          <div class="jobs-summary__stat-main">${summary.with_issues}</div>
          <div class="jobs-summary__stat-sub">${withIssuesPct}% of ${summary.total_with_pr} open PRs</div>
          <i class="jobs-summary__copy-icon ${copied === "with_issues" ? "jobs-summary__copy-icon--copied fa-solid fa-check" : "fa-regular fa-copy"}"></i>
        </button>
        <button class="jobs-summary__stat-card" @click=${() => copy("open", `[open pull requests] ${summary.total_with_pr}`)}>
          <div class="jobs-summary__stat-label">Open pull requests</div>
          <div class="jobs-summary__stat-main">${summary.total_with_pr}</div>
          <div class="jobs-summary__stat-sub">awaiting review or merge</div>
          <i class="jobs-summary__copy-icon ${copied === "open" ? "jobs-summary__copy-icon--copied fa-solid fa-check" : "fa-regular fa-copy"}"></i>
        </button>
      </div>
    </section>
  `;
}

customElements.define("jobs-summary", component(JobsSummary, { useShadowDOM: false }));
