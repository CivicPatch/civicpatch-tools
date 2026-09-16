import { html, render } from "lit-html";

import { detailSection } from "./detail-section.js";
import { caseInputUrl } from "./format.js";
import { issuesSection } from "./issues-section.js";
import { modelsSection } from "./models-section.js";
import { promptsSection } from "./prompts-section.js";
import { RUN_BROWSER_ID, focusedCaseElementId, runBrowser } from "./run-browser.js";
import { trendSection } from "./trend-section.js";
import { verdictSection } from "./verdict-section.js";

const DATA_URL = "dashboard-data.json";
const ROOT_ID = "dashboard";
const SERVE_HINT = 'open the dashboard with "mise run evals-serve"';

let state = {
  data: null,
  loadError: null,
  selection: null,
  comparisonChoices: {},
  caseInputs: {},
};

function setState(patch) {
  state = { ...state, ...patch };
  draw();
}

async function fetchCaseInput(url) {
  if (url in state.caseInputs) {
    return;
  }
  let text;
  try {
    const response = await fetch(url);
    text = response.ok ? await response.text() : `(${response.status} fetching ${url})`;
  } catch (err) {
    text = `(cannot fetch ${url}, ${SERVE_HINT})`;
  }
  setState({ caseInputs: { ...state.caseInputs, [url]: text } });
}

function sectionFor(evalName) {
  return state.data.evals.find((section) => section.eval_name === evalName);
}

const actions = {
  openBrowser: (selection) => {
    setState({ selection: { case_id: null, focused_case_id: null, ...selection } });
    const focused = document.getElementById(focusedCaseElementId(selection.focused_case_id));
    if (focused) {
      focused.scrollIntoView({ block: "start" });
    }
  },
  selectRun: (patch) => setState({ selection: { ...state.selection, ...patch } }),
  closeBrowser: () => setState({ selection: null }),
  toggleCase: (caseId) => {
    const shownCaseId = caseId === state.selection.case_id ? null : caseId;
    setState({ selection: { ...state.selection, case_id: shownCaseId } });
    if (shownCaseId) {
      fetchCaseInput(caseInputUrl(sectionFor(state.selection.eval_name), shownCaseId));
    }
  },
  chooseComparison: (evalName, choice) => setState({
    comparisonChoices: { ...state.comparisonChoices, [evalName]: choice },
  }),
};

function page(data) {
  const sections = data.evals;
  return html`
    <h2 class="civ-section-label">Can I ship it</h2>
    ${verdictSection(sections, actions)}
    <h2 class="civ-section-label">Which model and prompt score best</h2>
    ${modelsSection(sections, state.comparisonChoices, actions)}
    <h2 class="civ-section-label">What is the trend</h2>
    ${trendSection(sections, actions)}
    <h2 class="civ-section-label">What do I fix</h2>
    ${issuesSection(data.issues, sections)}
    <h2 class="civ-section-label">Which prompt produced it</h2>
    ${promptsSection(sections)}
    <h2 class="civ-section-label">Detail</h2>
    ${detailSection(sections)}
    ${runBrowser(sections, state.selection, state.caseInputs, actions)}
  `;
}

// A dialog's open state lives in the DOM, not the template.
function syncDialog() {
  const dialog = document.getElementById(RUN_BROWSER_ID);
  if (state.selection && !dialog.open) {
    dialog.showModal();
  }
  if (!state.selection && dialog.open) {
    dialog.close();
  }
}

function draw() {
  const root = document.getElementById(ROOT_ID);
  if (state.loadError) {
    render(html`<p class="note">Could not load ${DATA_URL}: ${state.loadError}. Run <code>mise run evals-report</code>, then ${SERVE_HINT}.</p>`, root);
    return;
  }
  if (!state.data) {
    render(html`<p class="note">Loading…</p>`, root);
    return;
  }
  render(page(state.data), root);
  syncDialog();
}

async function loadData() {
  try {
    // Regenerated after every eval run; http.server's headers let the browser reuse a stale copy.
    const response = await fetch(DATA_URL, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    setState({ data: await response.json() });
  } catch (err) {
    setState({ loadError: err.message });
  }
}

draw();
loadData();
