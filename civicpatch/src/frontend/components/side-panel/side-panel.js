import { component } from "haunted";
import { html } from "lit-html";
import "../notes-panel/notes-panel.js";
import "../source-content/index.js";

function SidePanel({ jurisdictionOcdid, sourceContentUrls }) {
    return html`
        <div class="side-panel">
            <civ-notes-panel .jurisdictionOcdid=${jurisdictionOcdid}></civ-notes-panel>
            ${sourceContentUrls && sourceContentUrls.length > 0
                ? html`<source-content .sourceContentUrls=${sourceContentUrls}></source-content>`
                : ""}
        </div>
    `;
}

customElements.define("civ-side-panel", component(SidePanel, { useShadowDOM: false }));
