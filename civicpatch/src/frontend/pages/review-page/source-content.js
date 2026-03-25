import { component, useState } from "haunted";
import { html } from "lit-html";

function SourceContent({ sourceContentUrls }) {
    const [selectedTab, setSelectedTab] = useState(0);
    if (!sourceContentUrls || sourceContentUrls.length === 0) {
        return html`<div class="source-content"><p>No source content available.</p></div>`;
    }

    return html`
        <div class="source-content">
            <div class="source-content__tabs">
                <div class="source-content__tab-bar">
                    ${sourceContentUrls.map((url, idx) => html`
                        <button
                            class="source-content__tab${selectedTab === idx ? ' source-content__tab--active' : ''}"
                            @click=${() => setSelectedTab(idx)}
                        >
                            Tab ${idx + 1}
                        </button>
                    `)}
                </div>
                <div class="source-content__tab-content">
                    <iframe
                        src=${sourceContentUrls[selectedTab]}
                        title=${`Source Content ${selectedTab + 1}`}
                        class="source-content__iframe"
                    ></iframe>
                </div>
            </div>
        </div>
    `;
}

customElements.define("source-content", component(SourceContent, { useShadowDOM: false }));