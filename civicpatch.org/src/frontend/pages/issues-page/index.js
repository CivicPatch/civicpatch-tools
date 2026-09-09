import "../../components/action-btn/action-btn.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { STORAGE_KEYS } from "../../utils/storage-keys.js";
import { PIPELINE_RUN_ISSUES, CHANGESET_ISSUES } from "./issue-sections.ts";
import "./issues-section.ts";
import "./config-editor.js";
import "./issues-page.css";
import { useAuth } from "../../hooks/useAuth.js";
import { SectionNav, adminSection } from "../../components/section-nav/index.js";
import "../../components/select-state/select-state.js";

const STATE_QUERY_KEY = "state";

function getStateFromUrl() {
  const val = new URLSearchParams(window.location.search).get(STATE_QUERY_KEY);
  return val ? val.toLowerCase() : "";
}

// Issues span every state — filtering to "your" state isn't a sensible default the
// way it is for review or bulk-review, so this doesn't fall back to the navbar's
// stored default. Its own filter, own URL param, starting at "all states" (empty).
function setStateInUrl(code) {
  const params = new URLSearchParams(window.location.search);
  if (code) params.set(STATE_QUERY_KEY, code);
  else params.delete(STATE_QUERY_KEY);
  const qs = params.toString();
  window.history.replaceState({}, "", `${window.location.pathname}${qs ? "?" + qs : ""}`);
}

function IssuesPage() {
  const { permissions } = useAuth();
  const [stateCode, setStateCode] = useState(getStateFromUrl());
  const handleStateChange = (e) => {
    const code = (e.detail.state || "").toLowerCase();
    setStateCode(code);
    setStateInUrl(code);
  };

  // One key, held here: two sections writing one localStorage entry would clobber each other.
  const [openSections, setOpenSections] = useLocalStorage(
    STORAGE_KEYS.ISSUES_OPEN_SECTIONS,
    { [PIPELINE_RUN_ISSUES]: true, [CHANGESET_ISSUES]: true },
    { ttl: PERSIST_FOREVER },
  );
  const toggle = (kind) => setOpenSections({ ...openSections, [kind]: !openSections[kind] });

  return html`
    <main class="issues-page page-content">
      <div class="page-focal">
        <h1 class="page-focal__title">Issues</h1>
      </div>

      <div class="sectioned">
      ${SectionNav("admin", adminSection(permissions), "/issues")}
      <div class="secbody">

      <div class="issues-page__state-filter">
        <label>State</label>
        <civ-select-state .selected=${stateCode} @state-change=${handleStateChange}></civ-select-state>
      </div>

      <issues-section
        .kind=${PIPELINE_RUN_ISSUES}
        .stateCode=${stateCode}
        .open=${openSections[PIPELINE_RUN_ISSUES] !== false}
        @section-toggle=${() => toggle(PIPELINE_RUN_ISSUES)}
      ></issues-section>

      <issues-section
        .kind=${CHANGESET_ISSUES}
        .stateCode=${stateCode}
        .open=${openSections[CHANGESET_ISSUES] !== false}
        @section-toggle=${() => toggle(CHANGESET_ISSUES)}
      ></issues-section>
      </div>
      </div>
    </main>
  `;
}

customElements.define("issues-page", component(IssuesPage, { useShadowDOM: false }));
export default IssuesPage;
