import { html, svg } from "lit-html";

import { formatAgo, formatFriendly, sectionLabel } from "./format.js";

const CHART_WIDTH = 200;
const CHART_HEIGHT = 92;
const PAD = { left: 28, right: 7, top: 9, bottom: 16 };
const INNER_WIDTH = CHART_WIDTH - PAD.left - PAD.right;
const INNER_HEIGHT = CHART_HEIGHT - PAD.top - PAD.bottom;
const GRID_VALUES = [0, 0.5, 1];

function providerColour(trends, provider) {
  return `rgb(var(--color-${trends.providers.indexOf(provider) + 1}))`;
}

function yFor(score) {
  return PAD.top + (1 - score) * INNER_HEIGHT;
}

function xFor(index, count) {
  return PAD.left + (INNER_WIDTH * index) / (count - 1);
}

function horizontalLine(y, className) {
  return svg`<line x1=${PAD.left} y1=${y} x2=${CHART_WIDTH - PAD.right} y2=${y} class=${className}></line>`;
}

function grid() {
  return GRID_VALUES.map((value) => svg`
    ${horizontalLine(yFor(value), "trend-chart__grid")}
    <text x=${PAD.left - 5} y=${yFor(value) + 3} class="trend-chart__axis">${value.toFixed(1)}</text>
  `);
}

function point(section, chart, series, colour, actions, runPoint, index) {
  const x = xFor(index, series.points.length);
  const y = yFor(runPoint.score);
  const open = (e) => {
    e.preventDefault();
    actions.openBrowser({
      eval_name: section.eval_name, prompt_sha256: runPoint.prompt_sha256, timestamp: runPoint.timestamp,
      provider: series.provider, metric: chart.metric,
    });
  };
  const title = `${series.provider}, ${chart.metric} ${runPoint.score.toFixed(3)}\n`
    + `${formatFriendly(runPoint.timestamp)} (${formatAgo(runPoint.timestamp)})\nprompt ${runPoint.prompt_sha256}, click to open`;
  return svg`
    <a href="#prompt-${runPoint.prompt_sha256}" class="trend-chart__point" @click=${open}>
      <title>${title}</title>
      <circle cx=${x} cy=${y} r="4.5" class="trend-chart__hit-area"></circle>
      <circle cx=${x} cy=${y} r="2.4" style="fill:${colour}"></circle>
    </a>
  `;
}

function seriesMarks(section, chart, series, actions) {
  const colour = providerColour(section.trends, series.provider);
  const count = series.points.length;
  const line = series.points.map((p, i) => `${xFor(i, count)},${yFor(p.score)}`).join(" ");
  return svg`
    <polyline points=${line} style="stroke:${colour}"></polyline>
    ${series.points.map((runPoint, index) => point(section, chart, series, colour, actions, runPoint, index))}
  `;
}

function trendChart(section, chart, actions) {
  const floor = chart.gate_floor == null ? "" : horizontalLine(yFor(chart.gate_floor), "trend-chart__floor");
  return html`
    <figure class="trend-chart${chart.is_priority ? " trend-chart--priority" : ""}">
      <figcaption>${chart.metric}${chart.is_priority ? " ★" : ""}</figcaption>
      <svg viewBox="0 0 ${CHART_WIDTH} ${CHART_HEIGHT}" width="100%">
        ${grid()}${floor}${chart.series.map((series) => seriesMarks(section, chart, series, actions))}
      </svg>
    </figure>
  `;
}

function trendKey(trends) {
  return html`
    <div class="trend-key">
      ${trends.providers.map((provider) => html`
        <span><i class="trend-key__swatch" style="background:${providerColour(trends, provider)}"></i>${provider}</span>
      `)}
      <span class="trend-key__floor">- - - gate floor</span><span>★ priority metric</span>
    </div>
  `;
}

function evalTrends(section, actions) {
  const { trends } = section;
  if (!trends.charts.length) {
    return trends.run_count ? html`${sectionLabel(section)}<p class="note">Only one run recorded, no trend yet.</p>` : "";
  }
  return html`
    ${sectionLabel(section)}
    <div class="eval-card eval-card--padded">
      <div class="trend-grid">${trends.charts.map((chart) => trendChart(section, chart, actions))}</div>
      <p class="trend-hint">Every point links to the prompt that produced it. Hover for the run, click to open it.</p>
      ${trendKey(trends)}
    </div>
  `;
}

export function trendSection(sections, actions) {
  return sections.map((section) => evalTrends(section, actions));
}
