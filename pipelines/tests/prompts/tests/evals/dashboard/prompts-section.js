import { html } from "lit-html";

import { formatCount, formatWhen, sectionLabel } from "./format.js";

function countLines(diff, kind) {
  return diff.filter((line) => line.kind === kind).length;
}

function promptDiff(version) {
  if (!version.diff.length) {
    return "";
  }
  return html`
    <details class="prompt-diff">
      <summary>
        changed vs ${version.previous_sha256}
        (<span class="prompt-diff__line--added">+${countLines(version.diff, "added")}</span> /
        <span class="prompt-diff__line--removed">-${countLines(version.diff, "removed")}</span>)
      </summary>
      <pre>${version.diff.map((line) => html`<span class="prompt-diff__line prompt-diff__line--${line.kind}">${line.text}</span>`)}</pre>
    </details>
  `;
}

function promptVersion(version) {
  return html`
    <div class="prompt-version" id="prompt-${version.prompt_sha256}">
      <div class="prompt-version__header">
        <code>${version.prompt_sha256}</code>
        <span class="meta">${formatCount(version.runs.length, "run")}, ${formatCount(version.text.split("\n").length, "line")}</span>
        <span class="meta">
          ${formatWhen(version.first_run_at, 16)} → ${formatWhen(version.last_run_at, 16)}, ${version.providers.join(", ")}
        </span>
      </div>
      ${promptDiff(version)}
    </div>
  `;
}

export function promptsSection(sections) {
  return sections
    .filter((section) => section.prompt_versions.length)
    .map((section) => html`
      ${sectionLabel(section)}
      <div class="eval-card">
        ${section.prompt_versions.length === 1
          ? html`<p class="note">Only one version recorded, so there is no diff. A second will add one.</p>`
          : ""}
        ${section.prompt_versions.map(promptVersion)}
      </div>
    `);
}
