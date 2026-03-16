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
    <fieldset>
      <input
        type="radio"
        id="top-level-url"
        name="scrape-scope"
        value="top-level-url"
        ?checked=${scrapeScope === "top-level-url"}
        @change=${handleScopeChange}
      />
      <label for="top-level-url">Top-level URL only</label>

      <input
        type="radio"
        id="specific-urls"
        name="scrape-scope"
        value="specific-urls"
        ?checked=${scrapeScope === "specific-urls"}
        @change=${handleScopeChange}
      />
      <label for="specific-urls">Specific URLs</label>
    </fieldset>

    ${scrapeScope === "top-level-url"
      ? html`
        <form @submit=${(e) => e.preventDefault()}>
          <fieldset role="group">
            <input
              type="url"
              .value="${currentUrl}"
              @input=${handleUrlChange}
            />
            <button type="button" @click=${resetUrl}>Reset</button>
          </fieldset>
        </form>
        `
      : html`
          ${currentSourceUrls.map(
            (url, index) => html`
              <fieldset role="group">
                <input
                  type="url"
                  @input=${(e) => handleSourceUrlChange(index, e)}
                />
                <button type="button" @click=${() => removeSourceUrl(index)}>
                  Delete
                </button>
              </fieldset>
            `,
          )}
          <button @click=${addSourceUrl}>Add URL</button>
        `}
  `;

  const footer = html`
    <button @click=${modalProps.onClose} class="secondary">Cancel</button>
    <button
      @click=${() => {
        submitScrape();
        modalProps.onClose();
      }}
      class="primary"
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
