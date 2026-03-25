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