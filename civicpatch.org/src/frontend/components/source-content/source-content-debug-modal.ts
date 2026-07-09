import "./source-content-debug-modal.css";
import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { unsafeHTML } from "lit-html/directives/unsafe-html.js";
import DOMPurify from "dompurify";
import { marked } from "marked";
import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import "../basic/modal.js";
import "../civ-tab-bar/civ-tab-bar.js";

export type SourceContentUrl = {
  url: string;
  markdown: string;
};

type SourceContentDebugModalHost = HTMLElement & {
  sourceContentUrls: SourceContentUrl[] | null;
};

function SourceContentDebugModal(host: SourceContentDebugModalHost) {
  const sourceContentUrls = host.sourceContentUrls ?? [];
  const [debugTab, setDebugTab] = useState(0);
  const [markdownHtml, setMarkdownHtml] = useState("");

  const safeTab = sourceContentUrls.length > 0
    ? Math.min(debugTab, sourceContentUrls.length - 1)
    : 0;

  useEffect(() => {
    if (sourceContentUrls.length === 0) {
      setMarkdownHtml("");
      return;
    }
    let isMounted = true;
    const markdownUrl = sourceContentUrls[safeTab].markdown;
    fetch(markdownUrl)
      .then((res) => res.text())
      .then((markdown) => DOMPurify.sanitize(marked.parse(markdown) as string))
      .then((cleanHtml) => { if (isMounted) setMarkdownHtml(cleanHtml); })
      .catch(() => { if (isMounted) setMarkdownHtml("<p>Failed to load markdown.</p>"); });
    return () => { isMounted = false; };
  }, [safeTab, sourceContentUrls]);

  const handleClose = () =>
    host.dispatchEvent(new CustomEvent("modal-close", { bubbles: true, composed: true }));

  if (sourceContentUrls.length === 0) return html``;

  const urlMap = buildSourceUrlMap(sourceContentUrls);
  const tabs = sourceContentUrls.map(({ url }) => {
    const entry = urlMap.get(url)!;
    return { label: entry.number, colorClass: entry.colorClass };
  });

  const content = html`
    <civ-tab-bar
      .tabs=${tabs}
      .selectedIndex=${safeTab}
      .onTabClick=${(idx: number) => setDebugTab(idx)}
    ></civ-tab-bar>
    <a
      class="source-content-debug-modal__link"
      href=${sourceContentUrls[safeTab].url}
      target="_blank"
      rel="noopener noreferrer"
    >View Original</a>
    <div class="source-content-debug-modal__markdown">${unsafeHTML(markdownHtml)}</div>
  `;

  return html`
    <civ-modal
      .title=${"Source content"}
      .content=${content}
      .modalProps=${{ open: true, onClose: handleClose }}
    ></civ-modal>
  `;
}

customElements.define(
  "source-content-debug-modal",
  component(SourceContentDebugModal as unknown as () => unknown, { useShadowDOM: false }),
);
