import { html } from "lit-html";

export const EMPTY_VALUE = "—";

const FRIENDLY_TIME = new Intl.DateTimeFormat("en", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
const RELATIVE_TIME = new Intl.RelativeTimeFormat("en", { numeric: "auto", style: "short" });
const TIME_UNITS = [
  ["year", 365 * 24 * 60 * 60],
  ["month", 30 * 24 * 60 * 60],
  ["week", 7 * 24 * 60 * 60],
  ["day", 24 * 60 * 60],
  ["hour", 60 * 60],
  ["minute", 60],
  ["second", 1],
];

// Seconds kept: concurrent runs share a minute, and truncating made them look identical.
export function formatFriendly(timestamp) {
  return FRIENDLY_TIME.format(new Date(timestamp));
}

export function formatAgo(timestamp, now = Date.now()) {
  const seconds = Math.round((new Date(timestamp).getTime() - now) / 1000);
  const [unit, size] = TIME_UNITS.find(([, unitSeconds]) => Math.abs(seconds) >= unitSeconds) || TIME_UNITS.at(-1);
  return RELATIVE_TIME.format(Math.round(seconds / size), unit);
}

export function formatValue(value) {
  if (Array.isArray(value)) {
    return value.length ? value.join(", ") : EMPTY_VALUE;
  }
  return value == null || value === "" ? EMPTY_VALUE : String(value);
}

export function formatCount(count, singular, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

export function shortModel(model) {
  return model.split("/").pop();
}

export function lineageLabel(lineage) {
  return `${shortModel(lineage.model)} on ${lineage.provider}`;
}

export function caseInputUrl(section, caseId) {
  return `${section.dataset_dir}/${caseId}/input.md`;
}

// Only "per case" markers vary: `<canonical type>` and `<value>` are the officials prompt's own words.
const PER_CASE_PLACEHOLDER = /(<[^<>\n]*per case>)/;
// Must match CASE_PROMPT_KEY_SEPARATOR in eval_utils.py.
const CASE_PROMPT_KEY_SEPARATOR = "|";

export function promptWithPlaceholders(text) {
  return text.split(PER_CASE_PLACEHOLDER).map((part) => (PER_CASE_PLACEHOLDER.test(part) ? html`<b>${part}</b>` : part));
}

// The case's prompt with whatever filled the template's placeholders in bold. Walks the template's
// fixed text in order; fixed text the case prompt lacks ends up inside the next bold run.
export function promptWithChanges(text, template) {
  const fixedParts = template.split(PER_CASE_PLACEHOLDER).filter((part) => part && !PER_CASE_PLACEHOLDER.test(part));
  const parts = [];
  let cursor = 0;
  for (const fixed of fixedParts) {
    const at = text.indexOf(fixed, cursor);
    if (at === -1) {
      continue;
    }
    if (at > cursor) {
      parts.push(html`<b>${text.slice(cursor, at)}</b>`);
    }
    parts.push(fixed);
    cursor = at + fixed.length;
  }
  if (cursor < text.length) {
    parts.push(html`<b>${text.slice(cursor)}</b>`);
  }
  return parts;
}

// One entry for most evals; page covers asks once per body, keyed "<case id>|<body>".
export function casePrompts(section, provider, caseId) {
  const saved = section.latest_case_prompts[provider];
  if (!saved) {
    return [];
  }
  return Object.entries(saved.prompts)
    .filter(([key]) => key === caseId || key.startsWith(`${caseId}${CASE_PROMPT_KEY_SEPARATOR}`))
    .map(([key, sha]) => ({
      label: key.slice(caseId.length + CASE_PROMPT_KEY_SEPARATOR.length),
      url: `${section.prompts_dir}/${sha}.txt`,
      template_sha256: saved.template_sha256,
    }));
}

// The inputs this case's prompt was given, since the archived prompt shows only placeholders.
export function casePromptInputs(section, caseId) {
  const inputs = Object.entries(section.case_inputs[caseId] || {});
  if (!inputs.length) {
    return html`<p class="note">No inputs recorded: the case is no longer in the dataset.</p>`;
  }
  return html`
    <dl class="case-inputs">
      ${inputs.map(([key, value]) => html`<dt>${key}</dt><dd>${value}</dd>`)}
    </dl>
  `;
}

export function caseLink(section, caseId) {
  return html`<a class="case-link" href=${caseInputUrl(section, caseId)}><code>${caseId}</code></a>`;
}

export function scorePill(score, isBest = false) {
  return html`
    <span class="score-pill${isBest ? " score-pill--best" : ""}" style="--score:${score.toFixed(3)}">${score.toFixed(2)}</span>
  `;
}

export function joinTemplates(templates, separator = ", ") {
  return templates.map((template, index) => (index === 0 ? template : html`${separator}${template}`));
}

export function sectionLabel(section) {
  return html`<p class="eval-label">${section.eval_name}</p>`;
}
