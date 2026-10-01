import "./scrape-modal.css";
import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import "../../../components/basic/modal.js";
import { flattenSourceUrls } from "./roster-source-urls.ts";

const TOP_LEVEL_SCOPE = "top-level-url";
const SPECIFIC_URLS_SCOPE = "specific-urls";

function ScrapeModal({
  onStartScrape,
  url = "",
  rosterSourceUrls = [],
  modalProps = {},
}) {
  const [scrapeScope, setScrapeScope] = useState(TOP_LEVEL_SCOPE);
  const [currentUrl, setCurrentUrl] = useState(url);
  const [pageGroups, setPageGroups] = useState(rosterSourceUrls);

  // Typed-in urls replace the roster's pages, so each opening starts from them again, and on
  // them when there are any: the person sees exactly what will be read.
  useEffect(() => {
    if (!modalProps.open) return;
    setPageGroups(rosterSourceUrls);
    setScrapeScope(
      flattenSourceUrls(rosterSourceUrls).length ? SPECIFIC_URLS_SCOPE : TOP_LEVEL_SCOPE,
    );
  }, [modalProps.open]);

  const handleScopeChange = (event) => {
    setScrapeScope(event.target.value);
  };

  const resetUrl = (e) => {
    e.preventDefault();
    setCurrentUrl(url);
  };

  const updateGroupUrls = (groupIndex, updateUrls) => {
    setPageGroups(
      pageGroups.map((group, index) =>
        index === groupIndex ? { ...group, urls: updateUrls(group.urls) } : group,
      ),
    );
  };

  const addSourceUrl = (groupIndex) => {
    updateGroupUrls(groupIndex, (urls) => [...urls, ""]);
  };

  const removeSourceUrl = (groupIndex, urlIndex) => {
    updateGroupUrls(groupIndex, (urls) => urls.filter((_, i) => i !== urlIndex));
  };

  const handleUrlChange = (event) => {
    setCurrentUrl(event.target.value);
  };

  const handleSourceUrlChange = (groupIndex, urlIndex, event) => {
    updateGroupUrls(groupIndex, (urls) =>
      urls.map((url, i) => (i === urlIndex ? event.target.value : url)),
    );
  };

  const currentSourceUrls = flattenSourceUrls(pageGroups);

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
    scrapeScope === TOP_LEVEL_SCOPE
      ? currentUrlIsValid()
      : currentSourceUrlsValid();

  const handleModeChange = (event) => {
    setScrapeMode(event.target.value);
  };

  const submitScrape = () => {
    let data = {};
    if (scrapeScope === TOP_LEVEL_SCOPE) {
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
            value=${TOP_LEVEL_SCOPE}
            ?checked=${scrapeScope === TOP_LEVEL_SCOPE}
            @change=${handleScopeChange}
          />
          Top-level URL only
        </label>
        <label class="scrape-modal__radio-label">
          <input
            type="radio"
            name="scrape-scope"
            value=${SPECIFIC_URLS_SCOPE}
            ?checked=${scrapeScope === SPECIFIC_URLS_SCOPE}
            @change=${handleScopeChange}
          />
          Specific URLs
        </label>
      </fieldset>

      <div class="scrape-modal__url-section">
        ${scrapeScope === TOP_LEVEL_SCOPE
          ? html`
              <fieldset role="group">
                <input
                  type="url"
                  .value="${currentUrl}"
                  @input=${handleUrlChange}
                  placeholder="https://…"
                />
                <button type="button" class="secondary" @click=${resetUrl}>
                  Reset
                </button>
              </fieldset>
            `
          : pageGroups.map(
              (group, groupIndex) => html`
                <fieldset class="scrape-modal__group">
                  <legend>${group.organization_name}</legend>
                  ${group.urls.map(
                    (url, urlIndex) => html`
                      <fieldset role="group">
                        <input
                          type="url"
                          .value="${url}"
                          @input=${(e) => handleSourceUrlChange(groupIndex, urlIndex, e)}
                          placeholder="https://…"
                        />
                        <button
                          type="button"
                          class="secondary destructive"
                          @click=${() => removeSourceUrl(groupIndex, urlIndex)}
                        >
                          Delete
                        </button>
                      </fieldset>
                    `,
                  )}
                  <button
                    class="btn-ghost scrape-modal__add-url"
                    @click=${() => addSourceUrl(groupIndex)}
                  >
                    + Add URL
                  </button>
                </fieldset>
              `,
            )}
      </div>
    </div>
  `;

  const footer = html`
    <button @click=${modalProps.onClose} class="secondary btn-sm">
      Cancel
    </button>
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
