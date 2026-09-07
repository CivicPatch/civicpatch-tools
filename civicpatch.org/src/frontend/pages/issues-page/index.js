import "../../components/action-btn/action-btn.css";
import { html } from "lit-html";
import { component } from "haunted";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { STORAGE_KEYS } from "../../utils/storage-keys.js";
import { PIPELINE_RUN_ISSUES, CHANGESET_ISSUES } from "./issue-sections.ts";
import "./issues-section.ts";
import "./config-editor.js";
import "./issues-page.css";

function getStateFromUrl() {
  const val = new URLSearchParams(window.location.search).get("state");
  return val ? val.toLowerCase() : "";
}

function IssuesPage() {
  const [defaultState] = useLocalStorage(STORAGE_KEYS.DEFAULT_STATE, "", { ttl: PERSIST_FOREVER });
  const stateCode = (getStateFromUrl() || defaultState || "").toLowerCase();

  // One key, held here: two sections writing one localStorage entry would clobber each other.
  const [openSections, setOpenSections] = useLocalStorage(
    STORAGE_KEYS.ISSUES_OPEN_SECTIONS,
    { [PIPELINE_RUN_ISSUES]: true, [CHANGESET_ISSUES]: true },
    { ttl: PERSIST_FOREVER },
  );
  const toggle = (kind) => setOpenSections({ ...openSections, [kind]: !openSections[kind] });

  return html`
    <main class="issues-page page-content">
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
    </main>
  `;
}

customElements.define("issues-page", component(IssuesPage, { useShadowDOM: false }));
export default IssuesPage;
