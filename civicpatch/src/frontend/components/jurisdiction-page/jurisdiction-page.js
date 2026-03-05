import { component, useState } from "haunted";
import { html } from "lit-html";
import { useSSE } from "../../hooks/useSse.js";
import { useAuth } from "../../hooks/useAuth.js";
import { useJurisdiction } from "../../hooks/useJurisdiction.js";
import { usePeople } from "../../hooks/usePeople.js";
import { buildIdentitiesMap } from "../../utils/people.js";
import "../edit-people/edit-people.js";
import "./config-detail.js";
import "./jurisdiction-header.js";
import "./jurisdiction-sidebar.js";

const API_URL = __API_URL__;

function JurisdictionPage({ jurisdiction_ocdid, history }) {
  const { loading: authLoading, permissions } = useAuth();
  const { data: jurisdictionData, isLoading: jurisdictionLoading } = useJurisdiction(jurisdiction_ocdid);
  const { people, isLoading: peopleLoading } = usePeople(jurisdiction_ocdid);
  const [scrapeModalOpen, setScrapeModalOpen] = useState(false);

  // Guard: show loading or block if not authenticated
  if (authLoading) {
    return html`<p>Checking authentication...</p>`;
  }
  if (!permissions.JURISDICTION_PAGE) {
    return html`<p>You must be logged in to view this page.</p>`;
  }

  const identities = buildIdentitiesMap(people);
  const isLoading = jurisdictionLoading || peopleLoading;

  const sseUrl = jurisdiction_ocdid
    ? `${API_URL}/api/v1/sse/jobs/status?jurisdiction_ocdid=${encodeURIComponent(jurisdiction_ocdid)}&job_type=people`
    : null;

  const { data: jobStatus, isConnected, error: sseError } = useSSE(sseUrl, { 
    autoConnect: !!sseUrl 
  });

  const handleScrapeStartClick = async (details) => {
    setScrapeModalOpen(false);
    const body = {
      jurisdiction_ocdid: jurisdictionData.data.id,
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
  const canStartScrape = true;

  return html`
    <div style="display: flex; flex-direction: column; gap: 2rem;">
      <div class="grid">
        <div style="display: flex; flex-direction: column; gap: 2rem;">
          <civ-map
            canmove="false"
            .latlng=${jurisdictionData?.geo_center
              ? { lat: jurisdictionData.geo_center.lat, lng: jurisdictionData.geo_center.lng }
              : null}
          ></civ-map>
          <civ-config-detail .people=${people}></civ-config-detail>
        </div>

        <div>
          <civ-jurisdiction-header
            .name=${jurisdictionData?.data?.name}
            .scrapeStatus=${scrapeStatus}
          ></civ-jurisdiction-header>
          
          <hr />
          
          <civ-jurisdiction-sidebar
            .jurisdictionData=${jurisdictionData}
            .history=${history}
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
            ></civ-scrape-modal>
          ` : null}

        </div>
      </div>

      ${!isLoading ? html`
        <civ-editable-people-list 
          jurisdiction_ocdid=${jurisdiction_ocdid}
          .people=${people}
        ></civ-editable-people-list>
      ` : null}
    </div>
  `;
}

customElements.define(
  "civ-jurisdiction-page",
  component(JurisdictionPage, {
    useShadowDOM: false,
    observedAttributes: ["jurisdiction_ocdid", "history"],
  }),
);
