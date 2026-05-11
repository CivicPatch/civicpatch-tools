import "./search-jurisdictions.css";
import { component, useState, useEffect, useMemo } from "haunted";
import { html } from "lit-html";
import { fetchPeople, fetchDashboard } from "../../api.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { useAuth } from "../../hooks/useAuth.js";
import "../../components/badge/badge.js";
import "../../components/leaderboard/index.js";
import "../../components/progress-dashboard/summary-stats.js";
import "../../components/progress-dashboard/locality-gaps.js";
import "../../components/progress-dashboard/states-overview.js";
import "../../components/people-directory/people-directory.ts";
import "../../components/map/browse-map.ts";
import { buildCoverageMap } from "./coverage-map.ts";

function SearchJurisdictions() {
  const { permissions } = useAuth();
  const [defaultState] = useLocalStorage("app:default-state", "", { ttl: PERSIST_FOREVER });
  const [selectedState, setSelectedState] = useState((defaultState || '').toLowerCase());
  const [selectedJurisdictionOcdid, setSelectedJurisdictionOcdid] = useState(null);
  const [selectedJurisdictionName, setSelectedJurisdictionName] = useState('');
  const [people, setPeople] = useState([]);
  const [dashboardData, setDashboardData] = useState(null);


  useEffect(() => {
    if (!selectedJurisdictionOcdid) {
      setPeople([]);
      return;
    }
    fetchPeople(selectedJurisdictionOcdid).then(data => setPeople(data.data));
  }, [selectedJurisdictionOcdid]);

  useEffect(() => {
    fetchDashboard().then(data => setDashboardData(data.data));
  }, []);

  useEffect(() => {
    const handler = (e) => setSelectedState((e.detail.state || '').toLowerCase());
    document.addEventListener('state-select', handler);
    return () => document.removeEventListener('state-select', handler);
  }, []);

  const coverageMap = useMemo(
    () => buildCoverageMap(dashboardData, selectedState),
    [dashboardData, selectedState],
  );

  const handleStateChange = (event) => {
    setSelectedState((event.detail.state || '').toLowerCase());
  };

  const handleSelectJurisdictionChange = (event) => {
    const { jurisdiction_ocdid, name } = event.detail;
    setSelectedJurisdictionOcdid(jurisdiction_ocdid);
    if (name) setSelectedJurisdictionName(name);
  };

  return html`
    <div class="search-page">
      <hgroup>
        <h1>Find your representatives</h1>
        <p>Find contact information for local government officials across the U.S.</p>
      </hgroup>
      <div class="page-grid">

        <div class="select-col">
          <civ-select-jurisdiction
            .selected=${selectedState}
            .selectedOcdid=${selectedJurisdictionOcdid}
            .selectedName=${selectedJurisdictionName}
            @state-change=${handleStateChange}
            @select-jurisdiction-change=${handleSelectJurisdictionChange}
          ></civ-select-jurisdiction>
        </div>

        <div class="map-col">
          <browse-map
            state=${selectedState || ''}
            selected-ocdid=${selectedJurisdictionOcdid || ''}
            .coverageMap=${coverageMap}
            @on-jurisdiction-change=${handleSelectJurisdictionChange}
            @on-state-change=${handleStateChange}
          ></browse-map>
        </div>

      </div>

      ${dashboardData && !selectedState ? html`
        <states-overview .stats=${dashboardData}></states-overview>
      ` : ''}

      ${dashboardData && selectedState ? html`
        <section>
          <h4>Progress — ${selectedState.toUpperCase()}</h4>
          <summary-stats .stats=${dashboardData} .state=${selectedState}></summary-stats>
        </section>
      ` : ''}

      <civ-leaderboard></civ-leaderboard>

      <div class="below-grid">
        <civ-people-directory .local=${people} .jurisdictionSelected=${!!selectedJurisdictionOcdid}></civ-people-directory>
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
