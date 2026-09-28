import { html } from "lit-html";

import {
  caseInputUrl,
  casePromptInputs,
  casePrompts,
  formatAgo,
  formatCount,
  formatFriendly,
  formatValue,
  promptWithChanges,
  promptWithPlaceholders,
} from "./format.js";

export const RUN_BROWSER_ID = "run-browser";

export function focusedCaseElementId(caseId) {
  return `mismatch-case-${caseId}`;
}
const NOT_ARCHIVED = "(not archived)";
const LOADING = "loading…";
const LABEL_FIELDS = new Set(["primary_role", "roles", "district", "designations_other"]);

function isSelectedRun(version, run, selection) {
  return version.prompt_sha256 === selection.prompt_sha256
    && run.timestamp === selection.timestamp
    && run.provider === selection.provider;
}

function runRow(version, run, selection, actions) {
  const score = selection.metric ? run.scores[selection.metric] : null;
  const select = () => actions.selectRun({ prompt_sha256: version.prompt_sha256, timestamp: run.timestamp, provider: run.provider });
  return html`
    <button type="button" class="run-row${isSelectedRun(version, run, selection) ? " run-row--selected" : ""}" @click=${select}>
      <span class="run-row__time">
        ${formatFriendly(run.timestamp)}
        <span class="subtext">${formatAgo(run.timestamp)}</span>
      </span>
      <span class="run-row__provider">${run.provider}</span>
      <span class="run-row__score">${score == null ? "" : score.toFixed(3)}</span>
    </button>
  `;
}

function versionGroup(version, selection, actions) {
  const selected = version.prompt_sha256 === selection.prompt_sha256;
  return html`
    <div class="version-group${selected ? " version-group--selected" : ""}">
      <button type="button" class="version-group__header" @click=${() => actions.selectRun({ prompt_sha256: version.prompt_sha256 })}>
        <span class="version-group__sha">${version.prompt_sha256}</span>
        <span class="count">${formatCount(version.runs.length, "run")}</span>
      </button>
      ${version.runs.map((run) => runRow(version, run, selection, actions))}
    </div>
  `;
}

function valueCell(className, value, label, showLabel) {
  return html`
    <td class=${className}>
      ${formatValue(value)}
      ${showLabel && label ? html`<span class="subtext">label: ${label}</span>` : ""}
    </td>
  `;
}

function mismatchCase(section, caseId, mismatches, selection, actions) {
  const selected = caseId === selection.case_id;
  const highlighted = selected || caseId === selection.focused_case_id;
  return html`
    <div id=${focusedCaseElementId(caseId)} class="mismatch-case${highlighted ? " mismatch-case--selected" : ""}">
      <div class="mismatch-case__header">
        <h3 class="mismatch-case__title"><code>${caseId}</code> <span class="count">${formatCount(mismatches.length, "wrong value")}</span></h3>
        <button type="button" class="secondary btn-sm" @click=${() => actions.toggleCase(caseId)}>
          ${selected ? "hide page" : "show prompt and page"}
        </button>
      </div>
      ${casePromptInputs(section, caseId)}
      <table class="data-table mismatch-table">
        <colgroup>
          <col class="mismatch-table__col-subject"><col class="mismatch-table__col-field">
          <col class="mismatch-table__col-value"><col class="mismatch-table__col-value">
        </colgroup>
        <thead><tr><th></th><th>field</th><th>expected</th><th>actual</th></tr></thead>
        <tbody>
          ${mismatches.map((mismatch) => html`
            <tr>
              <th>${mismatch.subject}</th>
              <td class="mismatch-table__field">${mismatch.field}</td>
              ${valueCell("mismatch-table__expected", mismatch.expected, mismatch.expected_label, LABEL_FIELDS.has(mismatch.field))}
              ${valueCell("mismatch-table__actual", mismatch.actual, mismatch.actual_label, LABEL_FIELDS.has(mismatch.field))}
            </tr>
          `)}
        </tbody>
      </table>
    </div>
  `;
}

function mismatchList(section, selection, actions) {
  const byCase = section.latest_mismatches[selection.provider] || {};
  const caseIds = Object.keys(byCase).sort();
  if (!caseIds.length) {
    return html`<p class="run-browser__note">No recorded mismatches for ${selection.provider || "this provider"} on the latest run.</p>`;
  }
  return html`
    <p class="run-browser__note">${selection.provider}, latest run only. <code>—</code> means nothing was returned.</p>
    ${caseIds.map((caseId) => mismatchCase(section, caseId, byCase[caseId], selection, actions))}
  `;
}

function savedPrompt(section, prompt, caseInputs) {
  const text = caseInputs[prompt.url];
  const template = section.prompt_versions.find((v) => v.prompt_sha256 === prompt.template_sha256);
  return html`
    ${prompt.label ? html`<p class="run-browser__note">${prompt.label}</p>` : ""}
    <pre class="case-detail__prompt">${text == null ? LOADING : template ? promptWithChanges(text, template.text) : text}</pre>
  `;
}

function casePromptBlock(section, version, selection, caseInputs) {
  const prompts = selection.case_id ? casePrompts(section, selection.provider, selection.case_id) : [];
  if (prompts.length) {
    return html`
      <p class="run-browser__note">The prompt this case was sent on ${selection.provider}&rsquo;s latest run, with this
      case&rsquo;s page content as the user message. Bold marks what differs from the template.</p>
      ${prompts.map((prompt) => savedPrompt(section, prompt, caseInputs))}
    `;
  }
  return html`
    <p class="run-browser__note">No saved prompt for this case, so this is the template;
    <code>&lt;per case&gt;</code> marks what varies.</p>
    <pre class="case-detail__prompt">${version ? promptWithPlaceholders(version.text) : NOT_ARCHIVED}</pre>
  `;
}

function caseDetail(section, version, selection, caseInputs, actions) {
  const caseId = selection.case_id;
  return html`
    <div class="case-detail${caseId ? " case-detail--open" : ""}" aria-hidden=${caseId ? "false" : "true"}>
      <div class="case-detail__header">
        <span>${caseId || ""}</span>
        <button type="button" class="secondary btn-sm" @click=${() => actions.toggleCase(null)}>close case</button>
      </div>
      ${casePromptBlock(section, version, selection, caseInputs)}
      <p class="run-browser__note">Case input${caseId ? `, ${caseId}/input.md` : ""}</p>
      <pre class="case-detail__input">${caseId ? caseInputs[caseInputUrl(section, caseId)] || LOADING : ""}</pre>
    </div>
  `;
}

function browserContent(section, selection, caseInputs, actions) {
  const version = section.prompt_versions.find((v) => v.prompt_sha256 === selection.prompt_sha256);
  const lineCount = version ? version.text.split("\n").length : 0;
  const metricNote = selection.metric ? `, column shows ${selection.metric}` : "";
  return html`
    <article>
      <header>
        <div>
          <code>${selection.prompt_sha256}</code>
          <span class="meta">
            ${section.eval_name}, ${formatCount(version ? version.runs.length : 0, "run")}, ${formatCount(lineCount, "line")}${metricNote}
          </span>
        </div>
        <button type="button" class="secondary btn-sm" @click=${actions.closeBrowser}>close</button>
      </header>
      <section class="run-browser__body">
        <aside class="run-browser__versions">
          ${section.prompt_versions.map((v) => versionGroup(v, selection, actions))}
        </aside>
        <div class="run-browser__main">
          <div>${mismatchList(section, selection, actions)}</div>
          ${caseDetail(section, version, selection, caseInputs, actions)}
        </div>
      </section>
    </article>
  `;
}

export function runBrowser(sections, selection, caseInputs, actions) {
  const section = selection && sections.find((s) => s.eval_name === selection.eval_name);
  const closeOnBackdrop = (e) => {
    if (e.target.id === RUN_BROWSER_ID) {
      actions.closeBrowser();
    }
  };
  return html`
    <dialog id=${RUN_BROWSER_ID} class="run-browser" @close=${actions.closeBrowser} @click=${closeOnBackdrop}>
      ${section ? browserContent(section, selection, caseInputs, actions) : ""}
    </dialog>
  `;
}
