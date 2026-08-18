import "./scrape-modal.css";
import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import "../../../components/basic/modal.js";

function ScrapeModal({ onStartScrape, url = "", sourceUrls = [], modalProps = {}, identities = {} }) {
  const [scrapeScope, setScrapeScope] = useState("top-level-url");
  const [currentUrl, setCurrentUrl] = useState(url);
  const [currentSourceUrls, setCurrentSourceUrls] = useState(sourceUrls);

  const handleScopeChange = (event) => {
    setScrapeScope(event.target.value);
  };

  const resetUrl = (e) => {
    e.preventDefault();
    setCurrentUrl(url);
  };

  const addSourceUrl = () => {
    setCurrentSourceUrls([...currentSourceUrls, ""]);
  };

  const removeSourceUrl = (index) => {
    const updatedUrls = currentSourceUrls.filter((_, i) => i !== index);
    setCurrentSourceUrls(updatedUrls);
  };

  const handleUrlChange = (event) => {
    setCurrentUrl(event.target.value);
  };

  const handleSourceUrlChange = (index, event) => {
    const updatedUrls = [...currentSourceUrls];
    updatedUrls[index] = event.target.value;
    setCurrentSourceUrls(updatedUrls);
  };

  const isValidUrl = (urlString) => {
    if (!urlString || urlString.trim() === "") return false;
    try {
      new URL(urlString);
      return true;
    } catch {
      return false;
    }
  };

  const currentUrlIsValid = () => {
    return isValidUrl(currentUrl);
  };

  const currentSourceUrlsValid = () => {
    return (
      currentSourceUrls.length > 0 &&
      currentSourceUrls.every((url) => isValidUrl(url))
    );
  };

  const canStartScrape =
    scrapeScope === "top-level-url"
      ? currentUrlIsValid()
      : currentSourceUrlsValid();

  const handleModeChange = (event) => {
    setScrapeMode(event.target.value);
  };

  const submitScrape = () => {
    let data = {};
    if (scrapeScope == "top-level-url") {
      data = {
        scrapeScope,
        data: {
          url: currentUrl,
        },
      };
    } else {
      data = {
        scrapeScope,
        data: {
          sourceUrls: currentSourceUrls,
        },
      };
    }
    onStartScrape(data);
  };

  const content = html`
    <div class="scrape-modal__body">
      <fieldset class="scrape-modal__radio-group">
        <legend>Scope</legend>
        <label class="scrape-modal__radio-label">
          <input
            type="radio"
            name="scrape-scope"
            value="top-level-url"
            ?checked=${scrapeScope === "top-level-url"}
            @change=${handleScopeChange}
          />
          Top-level URL only
        </label>
        <label class="scrape-modal__radio-label">
          <input
            type="radio"
            name="scrape-scope"
            value="specific-urls"
            ?checked=${scrapeScope === "specific-urls"}
            @change=${handleScopeChange}
          />
          Specific URLs
        </label>
      </fieldset>

      <div class="scrape-modal__url-section">
        ${scrapeScope === "top-level-url"
          ? html`
            <fieldset role="group">
              <input
                type="url"
                .value="${currentUrl}"
                @input=${handleUrlChange}
                placeholder="https://…"
              />
              <button type="button" class="secondary" @click=${resetUrl}>Reset</button>
            </fieldset>
          `
          : html`
            ${currentSourceUrls.map(
              (url, index) => html`
                <fieldset role="group">
                  <input
                    type="url"
                    .value="${url}"
                    @input=${(e) => handleSourceUrlChange(index, e)}
                    placeholder="https://…"
                  />
                  <button type="button" class="secondary destructive" @click=${() => removeSourceUrl(index)}>
                    Delete
                  </button>
                </fieldset>
              `,
            )}
            <button class="btn-ghost scrape-modal__add-url" @click=${addSourceUrl}>+ Add URL</button>
          `}
      </div>
    </div>
  `;

  const footer = html`
    <button @click=${modalProps.onClose} class="secondary btn-sm">Cancel</button>
    <button
      @click=${() => {
        submitScrape();
        modalProps.onClose();
      }}
      class="primary btn-sm"
      ?disabled=${!canStartScrape}
    >
      Start Scrape
    </button>
  `;

  return html`
    <civ-modal
      .title=${"URLs to Scrape"}
      .content=${content}
      .footer=${footer}
      .modalProps=${modalProps}
    ></civ-modal>
  `;
}

customElements.define(
  "civ-scrape-modal",
  component(ScrapeModal, { useShadowDOM: false }),
);
