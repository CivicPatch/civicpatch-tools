import "./side-panel.css";
import { component } from "haunted";
import { html } from "lit-html";
import "../source-content/index.js";

function SidePanel({ sourceContentUrls }) {
    return html`
        <div class="side-panel">
            ${sourceContentUrls && sourceContentUrls.length > 0
                ? html`<source-content .sourceContentUrls=${sourceContentUrls}></source-content>`
                : ""}
        </div>
    `;
}

customElements.define("civ-side-panel", component(SidePanel, { useShadowDOM: false }));
