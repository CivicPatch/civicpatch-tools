import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import { unsafeHTML } from "lit-html/directives/unsafe-html.js";

import DOMPurify from "dompurify";
import { marked } from "marked";
import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import "../civ-tab-bar/civ-tab-bar.js";


function SourceContent({ sourceContentUrls }) {
    const [selectedTab, setSelectedTab] = useState(0);
    const [markdownHtml, setMarkdownHtml] = useState("");

    useEffect(() => {
        setSelectedTab(0);
    }, [sourceContentUrls]);

    const safeTab = sourceContentUrls && sourceContentUrls.length > 0
        ? Math.min(selectedTab, sourceContentUrls.length - 1)
        : 0;

    useEffect(() => {
        let isMounted = true;
        if (!sourceContentUrls || sourceContentUrls.length === 0) {
            setMarkdownHtml("");
            return;
        }
        const url = sourceContentUrls[safeTab].markdown;
        fetch(url)
            .then(res => res.text())
            .then(markdown => DOMPurify.sanitize(marked.parse(markdown)))
            .then(html => { if (isMounted) setMarkdownHtml(html); })
            .catch(() => { if (isMounted) setMarkdownHtml("<p>Failed to load markdown.</p>"); });
        return () => { isMounted = false; };
    }, [safeTab, sourceContentUrls]);

    if (!sourceContentUrls || sourceContentUrls.length === 0) {
        return html`<div class="source-content"><p>No source content available.</p></div>`;
    }


    return html`
        <div class="source-content">
            <div class="source-content__tabs">
                <civ-tab-bar
                    .tabs=${(() => {
                        const urlMap = buildSourceUrlMap(sourceContentUrls);
                        return sourceContentUrls.map(({ url }) => {
                            const entry = urlMap.get(url);
                            return { label: entry.number, colorClass: entry.colorClass };
                        });
                    })()}
                    .selectedIndex=${safeTab}
                    .onTabClick=${(idx) => setSelectedTab(idx)}
                ></civ-tab-bar>
                <div class="source-content__tab-content">
                    <a href="${sourceContentUrls[safeTab].url}" target="_blank" rel="noopener noreferrer">View Original</a>
                    <div class="source-content__markdown">${unsafeHTML(markdownHtml)}</div>
                </div>
            </div>
        </div>
    `;
}

customElements.define("source-content", component(SourceContent, { useShadowDOM: false }));