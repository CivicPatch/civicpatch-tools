import { component, useState } from "haunted";
import { html } from "lit-html";
import { ref } from "lit-html/directives/ref.js";
import "../../basic/modal.js";

function ScrapeModal({ onStartScrape, url = "", sourceUrls = [], modalProps = {}, identities = {} }) {
  const [scrapeScope, setScrapeScope] = useState("top-level-url");
  const [currentUrl, setCurrentUrl] = useState(url);
  const [currentSourceUrls, setCurrentSourceUrls] = useState(sourceUrls);
  const [nameConfigs, setNameConfigs] = useState({});

  const handleNameConfigsChange = (configs) => {
    setNameConfigs(configs);
  };

  const handleScopeChange = (event) => {
    setScrapeScope(event.target.value);
  };

  const resetUrl = () => {
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
    data.identities = nameConfigs;
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
          <fieldset role="group">
            <input
              type="url"
              .value="${currentUrl}"
              @input=${handleUrlChange}
            />
          </fieldset>
          <div style="display: flex;">
            <button
              class="secondary outline"
              style="margin-left: auto;"
              @click=${resetUrl}
            >
              Reset URL
            </button>
          </div>
        `
      : html`
          ${currentSourceUrls.map(
            (url, index) => html`
              <fieldset role="group">
                <input
                  type="url"
                  @input=${(e) => handleSourceUrlChange(index, e)}
                />
                <button
                  type="button"
                  class="secondary outline"
                  @click=${() => removeSourceUrl(index)}
                >
                  Delete
                </button>
              </fieldset>
            `,
          )}
          <button @click=${addSourceUrl}>Add URL</button>
        `}

    <details name="override-names" style="margin-top: 1.5em;">
      <summary>
        <span style="font-weight: 600; font-size: 1.1em;">Name Configs</span>
      </summary>
      <div
        style="
          background: var(--pico-muted-border-color, #f6f8fa);
          border: 1px solid var(--pico-muted-border-color, #e0e0e0);
          border-radius: 0.75em;
          padding: 1.25em 1em 1em 1em;
          margin-top: 1em;
          box-shadow: 0 2px 8px 0 rgba(0,0,0,0.03);
        "
      >
        <p style="color: var(--pico-muted-color, #666); margin-bottom: 1em;">
          Some people go by multiple names that aren't easily guessable to be
          the same identity. Specify alternate names for identities to improve
          matching.
        </p>
        <name-config-form
          .onChange=${handleNameConfigsChange}
          .identities=${identities}
        ></name-config-form>
      </div>
    </details>
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
