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
                    ${sourceContentUrls.map((source, idx) => html`
                        <button
                            class="source-content__tab${selectedTab === idx ? ' source-content__tab--active' : ''}"
                            @click=${() => setSelectedTab(idx)}
                        >
                            Tab ${idx + 1}
                        </button>
                    `)}
                </div>
                <div class="source-content__tab-content">
                    <a href="${sourceContentUrls[selectedTab].source_url}" target="_blank" rel="noopener noreferrer">View Original</a>
                    <iframe
                        src=${sourceContentUrls[selectedTab].markdown_url}
                        title=${`Source Content ${selectedTab + 1}`}
                        class="source-content__iframe"
                    ></iframe>
                </div>
            </div>
        </div>
    `;
}

customElements.define("source-content", component(SourceContent, { useShadowDOM: false }));