import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import { fetchPeople, fetchDashboard, fetchJurisdictionsGeojson } from "../../api.js";
import "../../components/progress-dashboard/summary-stats.js";
import "../../components/progress-dashboard/locality-gaps.js";

function SearchJurisdictions() {
  const [selectedState, setSelectedState] = useState(null);
  const [selectedJurisdictionOcdid, setSelectedJurisdictionOcdid] = useState(null);
  const [people, setPeople] = useState([]);
  const [geojson, setGeojson] = useState([]);
  const [dashboardData, setDashboardData] = useState(null);

  useEffect(() => {
    if (!selectedJurisdictionOcdid) return;
    fetchPeople(selectedJurisdictionOcdid).then(data => setPeople(data.data));
  }, [selectedJurisdictionOcdid]);

  useEffect(() => {
    fetchDashboard().then(data => setDashboardData(data.data));
  }, []);

  const handleSelectJurisdictionChange = (event) => {
    const { state, jurisdiction_ocdid } = event.detail;
    setSelectedState(state);
    setSelectedJurisdictionOcdid(jurisdiction_ocdid);
  };

  const handleMapChange = (event) => {
    const { latlng, zoom } = event.detail;
    if (!latlng || !zoom) return;
    fetchJurisdictionsGeojson(latlng.lat, latlng.lng, zoom).then(data => setGeojson(data));
  };

  return html`
    <style>
      .search-page {
        display: flex;
        flex-direction: column;
        gap: 2rem;
      }

      /* Equal-split map + controls */
      .page-grid {
        display: grid;
        gap: 1rem;
        grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
        align-items: start;
      }

      /* Map column */
      .map-col {
        order: 1;
        position: sticky;
        top: 1rem;
        align-self: start;
      }

      /* Controls column */
      .select-col {
        order: 2;
        display: flex;
        flex-direction: column;
        gap: 1.5rem;
      }

      /* State progress section */
      .state-progress {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
      }
      .state-progress h3 {
        margin: 0;
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--pico-muted-color);
      }

      /* People list + locality gaps — full width below grid */
      .below-grid {
        display: flex;
        flex-direction: column;
        gap: 2rem;
      }

      /* Responsive */
      @media (max-width: 900px) {
        .page-grid {
          grid-template-columns: 1fr;
        }
        .map-col {
          order: 2;
          position: static;
        }
        .select-col {
          order: 1;
        }
      }
    </style>

    <div class="search-page">
      <div class="page-grid">

        <div class="map-col">
          <civ-map
            @on-map-change=${handleMapChange}
            @on-jurisdiction-change=${handleSelectJurisdictionChange}
            .geojson=${geojson}
          ></civ-map>
        </div>

        <div class="select-col">
          <civ-select-jurisdiction
            @select-jurisdiction-change=${handleSelectJurisdictionChange}
          ></civ-select-jurisdiction>

          ${dashboardData && selectedState ? html`
            <div class="state-progress">
              <h3>Progress — ${selectedState}</h3>
              <summary-stats .stats=${dashboardData} .state=${selectedState}></summary-stats>
            </div>
          ` : ''}
        </div>

      </div>

      <div class="below-grid">
        <civ-people-list .local=${people}></civ-people-list>
        ${dashboardData && selectedState ? html`
          <locality-gaps .stats=${dashboardData} .state=${selectedState}></locality-gaps>
        ` : ''}
      </div>
    </div>
  `;
}

customElements.define(
  "civ-search-jurisdictions",
  component(SearchJurisdictions, {
    useShadowDOM: false,
    observedAttributes: [],
  }),
);