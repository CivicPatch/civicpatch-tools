import { html } from "lit-html";
import { component, useState } from "haunted";

function QueueSummary({ summary }) {
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
    <section class="queue-summary">
      <div class="queue-summary__grid">
        <button class="queue-summary__stat-card" @click=${() => copy("with_issues", `[with issues] ${summary.with_issues} (${withIssuesPct}% of ${summary.total_with_pr} open PRs)`)}>
          <div class="queue-summary__stat-label">With issues</div>
          <div class="queue-summary__stat-main">${summary.with_issues}</div>
          <div class="queue-summary__stat-sub">${withIssuesPct}% of ${summary.total_with_pr} open PRs</div>
          <i class="queue-summary__copy-icon ${copied === "with_issues" ? "queue-summary__copy-icon--copied fa-solid fa-check" : "fa-regular fa-copy"}"></i>
        </button>
        <button class="queue-summary__stat-card" @click=${() => copy("open", `[open pull requests] ${summary.total_with_pr}`)}>
          <div class="queue-summary__stat-label">Open pull requests</div>
          <div class="queue-summary__stat-main">${summary.total_with_pr}</div>
          <div class="queue-summary__stat-sub">awaiting review or merge</div>
          <i class="queue-summary__copy-icon ${copied === "open" ? "queue-summary__copy-icon--copied fa-solid fa-check" : "fa-regular fa-copy"}"></i>
        </button>
      </div>
    </section>
  `;
}

customElements.define("queue-summary", component(QueueSummary, { useShadowDOM: false }));
