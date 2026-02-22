import { component, useEffect, useState, useCallback } from "haunted";
import { html } from "lit-html";
import { useSSE } from "../hooks/useSse.js"; // <-- Import the hook
import "../scrape-history/scrape-history-list.js";
import "../edit-people/edit-people.js";
import "./jurisdiction-detail.js"
import "./config-detail.js";  
// const DEFAULT_CENTER = "30.24171,-91.991044";
const API_URL = __API_URL__;

function JurisdictionPage({ 
  jurisdiction_ocdid, 
  history
}) {
  const [data, setData] = useState(null);
  const [people, setPeople] = useState([]);
  const [scrapeModalOpen, setScrapeModalOpen] = useState(false); 
  const [isLoading, setIsLoading] = useState(true);
  const identities = people?.reduce((acc, person) => {
    if (acc[person.name]) {
      acc[person.name] = [...new Set([...acc[person.name], ...(person.other_names || [])])];
    } else {
      acc[person.name] = [...new Set(person.other_names || [])];
    }

    return acc;

  }, {});


  const sseUrl = jurisdiction_ocdid
    ? [`${API_URL}/api/v1/sse/jobs/status`,
      `?jurisdiction_ocdid=${encodeURIComponent(jurisdiction_ocdid)}`,
      `&job_type=people`].join("")
    : null;

  const {
    data: jobStatus,
    isConnected,
    error: sseError,
    // connect: connectStream,
    // disconnect: disconnectStream,
  } = useSSE(sseUrl, { autoConnect: !!sseUrl });

  useEffect(() => {
    if (!jurisdiction_ocdid) return;
    fetchData();
  }, []);

  const fetchData = async () => {
    setIsLoading(true)
    const [jurisdictionData, peopleData] =
      await Promise.all([
        fetchJurisdictionData(jurisdiction_ocdid),
        fetchPeopleData(jurisdiction_ocdid),
      ]);
    setData(jurisdictionData);
    setPeople(peopleData);
    setIsLoading(false);
  };

  const fetchJurisdictionData = async (ocdid) => {
    const jurisdictionOcdidFormatted = encodeURIComponent(ocdid)
    const response = await fetch(
      `/api/api_proxy/jurisdictions?jurisdiction_ocdid=${jurisdictionOcdidFormatted}&with_geom=true`,
    );
    const result = await response.json();
    return {
      data: result.data,
      geo_center: result.geo_center,
    };
  };

  const fetchPeopleData = async (ocdid) => {
    const encodedOcdid = encodeURIComponent(ocdid);
    const response = await fetch(
      `/api/api_proxy/people?jurisdiction_ocdid=${encodedOcdid}`,
    );
    const result = await response.json();
    return result.data;
  };

  const handleScrapeModalClick = () => setScrapeModalOpen(true);
  const handleScrapeModalClose = () => setScrapeModalOpen(false);

  const handleScrapeStartClick = async (details) => {
    setScrapeModalOpen(false); // Optionally close modal on submit
    const body = {
      jurisdiction_ocdid: data.data.id,
      config: {
        url: details.data.url || data.data.url,
        name: data.data.name,
        source_urls: details.data.sourceUrls,
        identities: details.data.identities
      }
    };
    const _response = await fetch(`/api/pipelines`, {
      headers: { "Content-Type": "application/json" },
      method: "POST",
      body: JSON.stringify(body),
    });

    // Reconnect to the SSE stream to get real-time updates on the new job
    disconnectStream();
    connectStream();
  };

  const canStartScrape = true;
  const scrapeStatus = people?.length > 0 ? `Scraped` : `Unscraped`;

  return html`
    <style>
      .jurisdiction-title {
        position: relative;
        z-index: 1;
        color: rgb(var(--catppuccin-base));
        padding: 0.5rem 1.5rem;
      }

      .jurisdiction-title::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(var(--catppuccin-sapphire), 1.0);
        transform: skew(-20deg);
        z-index: -1;
      }
    </style>
    <div style="display: flex; flex-direction: column; gap: 2rem;">
      <div class="grid">
        <div style="display: flex; flex-direction: column; gap: 2rem;">
          <civ-map
            canmove="false"
            .latlng=${data && data.geo_center
              ? { lat: data.geo_center.lat, lng: data.geo_center.lng }
              : null}
          ></civ-map>
          <civ-config-detail .people=${people}></civ-config-detail>
        </div>

        <div>
          ${data
            ? html`
                <header>
                  <div
                    style="display: flex; justify-content: space-between; align-items: center;"
                  >
                    <h2 class="jurisdiction-title" style="margin-bottom: 0">${data.data.name}</h2>
                    <span style="font-size: 1.75rem"
                      >Status: ${scrapeStatus}</span
                    >
                  </div>
                </header>
                <hr />

                <civ-jurisdiction-detail .data=${data?.data}></civ-jurisdiction-detail>

                <h3>Scrape History</h3>
                <hr />
                <civ-scrape-history-list
                  .history=${history}
                  .jobStatus=${jobStatus}
                  .isConnected=${isConnected}
                  .sseError=${sseError}
                ></civ-scrape-history-list>

                <civ-scrape-modal
                  .onStartScrape=${handleScrapeStartClick}
                  .url=${data.data.url}
                  .modalProps=${{
                    open: scrapeModalOpen,
                    onClose: handleScrapeModalClose,
                    closeOnBackdropClick: false
                  }}
                  .identities=${identities}
                ></civ-scrape-modal> 

                <button
                  @click=${handleScrapeModalClick}
                  ?disabled=${!canStartScrape}
                  class="primary"
                >
                  Scrape Data for Jurisdiction
                </button>
              `
            : html` <p>Loading jurisdiction data...</p> `}
        </div>
      </div>

      <h2>Elected Representatives</h2>
     
      ${!isLoading ? html`
        <civ-editable-people-list 
          jurisdiction_ocdid=${jurisdiction_ocdid}
          .people=${people}
        ></civ-editable-people-list>
      ` : null }
    </div>
  `;
}

customElements.define(
  "civ-jurisdiction-page",
  component(JurisdictionPage, {
    useShadowDOM: false,
    observedAttributes: [
      "jurisdiction_ocdid", 
      "history"
    ],
  }),
);
