import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import { config } from '../../assets/config.js';
const API_URL = config.apiUrl;
import "../../components/progress-dashboard/summary-stats.js";
import "../../components/progress-dashboard/locality-gaps.js";

function SearchJurisdictions() {
  const [selectedState, setSelectedState] = useState(null);
  const [selectedJurisdictionOcdid, setSelectedJurisdictionOcdid] =
    useState(null);
  const [people, setPeople] = useState([]);
  const [geojson, setGeojson] = useState([]);
  const [dashboardData, setDashboardData] = useState(null);

  useEffect(() => {
    if (!selectedJurisdictionOcdid) return;

    const selectedJurisdictionOcdidEncoded = encodeURIComponent(
      selectedJurisdictionOcdid,
    );

    fetch(
      `/api/api_proxy/people?jurisdiction_ocdid=${selectedJurisdictionOcdidEncoded}`,
    )
      .then((response) => response.json())
      .then((data) => {
        setPeople(data.data);
      });
  }, [selectedJurisdictionOcdid]);

  useEffect(() => {
    // Fetch dashboard data once on mount
    fetch(`${API_URL}/api/v1/data/dashboard`)
      .then(res => res.json())
      .then(data => setDashboardData(data.data));
  }, []);

  const handleSelectJurisdictionChange = (event) => {
    const { state, jurisdiction_ocdid } = event.detail;
    console.log("Selected State:", state);
    setSelectedState(state);
    // TODO: pan the map if state but no jurisdiction
    console.log("Selected Jurisdiction:", jurisdiction_ocdid);
    setSelectedJurisdictionOcdid(jurisdiction_ocdid);
    // TODO: pan the map & zoom if state and jurisdiction
  };

  const handleMapChange = (event) => {
    const { latlng, zoom } = event.detail;
    if (!latlng || !zoom) return;
    console.log("Map Change - LatLng:", latlng, "Zoom:", zoom);
    fetch(
      `/api/api_proxy/jurisdictions/geojson?lat=${latlng.lat}&long=${latlng.lng}&zoom=${zoom}`,
    )
      .then((response) => response.json())
      .then((data) => {
        setGeojson(data);
      });
  };

  return html`
    <div style="display: flex; flex-direction: column; gap: 2rem;">
      <div class="grid">
        <div>
          <civ-map
            @on-map-change=${handleMapChange}
            @on-jurisdiction-change=${handleSelectJurisdictionChange}
            .geojson=${geojson}
          ></civ-map>
        </div>
        <div>
          <civ-select-jurisdiction
            @select-jurisdiction-change=${handleSelectJurisdictionChange}
          ></civ-select-jurisdiction>
            ${dashboardData && selectedState ? html`
                <section style="padding: 2rem 0;">
                <h3>Progress by State</h3>
                <summary-stats .stats=${dashboardData} .state=${selectedState}></summary-stats>
                </section>
            ` : ""}
        </div>
      </div>
      <civ-people-list .local=${people}></civ-people-list>
      ${dashboardData && selectedState ? html`
        <section style="margin-top:2rem;">
          <locality-gaps .stats=${dashboardData} .state=${selectedState}></locality-gaps>
        </section>
      ` : ""}
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
