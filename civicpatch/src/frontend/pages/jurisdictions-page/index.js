import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import { useWS } from "../../hooks/useSse.js";
import { useAuth } from "../../hooks/useAuth.js";
import { usePeople } from "../../hooks/usePeople.js";
import { buildIdentitiesMap } from "../../utils/people.js";
import "../../components/edit-people/edit-people.js";
import "../../components/source-content/index.js";
import "./config-detail.js";
import "./jurisdiction-header.js";
import "./jurisdiction-sidebar.js";
import "./scrape-modal/scrape-modal.js";
import "./scrape-modal/name-config-form.js";

import { triggerRemoteJob, fetchPullRequests } from '../../api.js';

function JurisdictionPage({ jurisdiction_ocdid, jurisdiction_data }) {
  const { loading: authLoading, permissions } = useAuth();
  const { people, isLoading: peopleLoading } = usePeople(jurisdiction_ocdid);
  const [scrapeModalOpen, setScrapeModalOpen] = useState(false);
  const [sourceContentUrls, setSourceContentUrls] = useState([]);

  useEffect(() => {
    if (!jurisdiction_ocdid) return;
    fetchPullRequests(jurisdiction_ocdid)
      .then((res) => setSourceContentUrls(res.data?.[0]?.sources ?? []))
      .catch(() => {});
  }, [jurisdiction_ocdid]);

  // Guards after all hooks (hooks must not be called conditionally)
  if (authLoading) {
    return html`<p>Checking authentication...</p>`;
  }
  if (!permissions.JURISDICTION_PAGE) {
    return html`<p>You must be logged in to view this page.</p>`;
  }

  const jurisdictionData = jurisdiction_data ? JSON.parse(jurisdiction_data) : null;
  const identities = buildIdentitiesMap(people);

  const wsTopic = jurisdiction_ocdid ? `job_status:${jurisdiction_ocdid}` : null;

  const { data: jobStatus, isConnected, error: sseError } = useWS(wsTopic, {
    autoConnect: !!wsTopic,
  });

  const handleScrapeStartClick = async (details) => {
    setScrapeModalOpen(false);

    if (details.scrapeMode === "remote") {
      await triggerRemoteJob(
        jurisdictionData.data.id,
        jurisdictionData.data.name,
        details.data.url || jurisdictionData.data.url,
      );
      return;
    }

    const body = {
      jurisdiction_ocdid: jurisdictionData.data.id,
      scrape_mode: details.scrapeMode,
      config: {
        url: details.data.url || jurisdictionData.data.url,
        name: jurisdictionData.data.name,
        source_urls: details.data.sourceUrls,
      }
    };

    await fetch(`/api/pipelines`, {
      headers: { "Content-Type": "application/json" },
      method: "POST",
      body: JSON.stringify(body),
    });
  };

  const scrapeStatus = people?.length > 0 ? "Scraped" : "Unscraped";
  const canStartScrape = permissions.JURISDICTION_PAGE_SCRAPE_REMOTE || permissions.JURISDICTION_PAGE_SCRAPE_LOCAL;

  return html`
    <div style="display: flex; flex-direction: column; gap: 2rem;">
      <div class="grid">
        <div style="display: flex; flex-direction: column; gap: 2rem;">
          <civ-map
            canmove="false"
            .latlng=${jurisdictionData?.geo_center
              ? { lat: jurisdictionData.geo_center.lat, lng: jurisdictionData.geo_center.lng }
              : null}
            .height=${"20rem"}
          ></civ-map>
          <civ-config-detail .people=${people}></civ-config-detail>
        </div>

        <div>
          <civ-jurisdiction-header
            .name=${jurisdictionData?.data?.name}
            .scrapeStatus=${scrapeStatus}
            .details=${jurisdictionData}
          ></civ-jurisdiction-header>

          <hr />

          <civ-jurisdiction-sidebar
            .jurisdictionData=${jurisdictionData}
            .jurisdiction_ocdid=${jurisdiction_ocdid}
            .jobStatus=${jobStatus}
            .isConnected=${isConnected}
            .sseError=${sseError}
            .onScrapeClick=${() => setScrapeModalOpen(true)}
            .canStartScrape=${canStartScrape}
          ></civ-jurisdiction-sidebar>

          ${jurisdictionData ? html`
            <civ-scrape-modal
              .onStartScrape=${handleScrapeStartClick}
              .url=${jurisdictionData?.data?.url}
              .modalProps=${{
                open: scrapeModalOpen,
                onClose: () => setScrapeModalOpen(false),
                closeOnBackdropClick: false
              }}
              .identities=${identities}
              .canScrapeRemote=${permissions.JURISDICTION_PAGE_SCRAPE_REMOTE}
              .canScrapeLocal=${permissions.JURISDICTION_PAGE_SCRAPE_LOCAL}
            ></civ-scrape-modal>
          ` : null}

        </div>
      </div>

      ${!peopleLoading ? html`
        <div class="review-page__content">
          <civ-editable-people-list
            jurisdiction_ocdid=${jurisdiction_ocdid}
            .people=${people}
          ></civ-editable-people-list>
          <source-content .sourceContentUrls=${sourceContentUrls}></source-content>
        </div>
      ` : null}
    </div>
  `;
}

customElements.define(
  "civ-jurisdiction-page",
  component(JurisdictionPage, {
    useShadowDOM: false,
    observedAttributes: ["jurisdiction_ocdid", "jurisdiction_data"],
  }),
);
