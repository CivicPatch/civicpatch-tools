import "./source-content-debug-modal.css";
import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import { MODAL_SIZE_WIDE } from "../basic/modal.js";
import "../basic/modal.js";
import "../civ-tab-bar/civ-tab-bar.js";
import { pageText } from "./page-text.js";

// `markdown` and `html` are the debug bucket's copies of the page: what the pipeline read, and
// what it fetched. Admins only; null for everyone else, who never open this modal.
export type SourceContentUrl = {
  url: string;
  markdown: string | null;
  html: string | null;
};

type SourceContentDebugModalHost = HTMLElement & {
  sourceContentUrls: SourceContentUrl[] | null;
};

type PageCopies = { fetched: string; read: string };

const NO_COPIES: PageCopies = { fetched: "", read: "" };
const FAILED_TO_LOAD = "Failed to load.";

async function fetchText(url: string | null): Promise<string> {
  if (!url) return "";
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.text();
}

async function loadCopies(source: SourceContentUrl): Promise<PageCopies> {
  const [fetchedHtml, read] = await Promise.all([
    fetchText(source.html).catch(() => null),
    fetchText(source.markdown).catch(() => FAILED_TO_LOAD),
  ]);
  return {
    fetched: fetchedHtml === null ? FAILED_TO_LOAD : pageText(fetchedHtml),
    read,
  };
}

function SourceContentDebugModal(host: SourceContentDebugModalHost) {
  const sourceContentUrls = host.sourceContentUrls ?? [];
  const [debugTab, setDebugTab] = useState(0);
  const [copies, setCopies] = useState<PageCopies>(NO_COPIES);

  const safeTab = sourceContentUrls.length > 0
    ? Math.min(debugTab, sourceContentUrls.length - 1)
    : 0;

  useEffect(() => {
    setCopies(NO_COPIES);
    if (sourceContentUrls.length === 0) return;
    let isMounted = true;
    loadCopies(sourceContentUrls[safeTab]).then((loaded) => {
      if (isMounted) setCopies(loaded);
    });
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
    >Live page</a>
    <div class="source-content-debug-modal__columns">
      <section class="source-content-debug-modal__column">
        <h3 class="source-content-debug-modal__heading">
          Page text
          ${sourceContentUrls[safeTab].html
            ? html`<a
                class="source-content-debug-modal__source"
                href=${sourceContentUrls[safeTab].html}
                target="_blank"
                rel="noopener noreferrer"
              >Fetched HTML</a>`
            : null}
        </h3>
        <pre class="source-content-debug-modal__text">${copies.fetched}</pre>
      </section>
      <section class="source-content-debug-modal__column">
        <h3 class="source-content-debug-modal__heading">Markdown the pipeline read</h3>
        <pre class="source-content-debug-modal__text">${copies.read}</pre>
      </section>
    </div>
  `;

  return html`
    <civ-modal
      .title=${"Source content"}
      .content=${content}
      .modalProps=${{ open: true, onClose: handleClose, size: MODAL_SIZE_WIDE }}
    ></civ-modal>
  `;
}

customElements.define(
  "source-content-debug-modal",
  component(SourceContentDebugModal as unknown as () => unknown, { useShadowDOM: false }),
);
