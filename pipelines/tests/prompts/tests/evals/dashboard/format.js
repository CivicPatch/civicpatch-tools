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
export function formatWhen(timestamp, length = 19) {
  return (timestamp || "").replace("T", " ").replace("+00:00", "").slice(0, length) || EMPTY_VALUE;
}

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
