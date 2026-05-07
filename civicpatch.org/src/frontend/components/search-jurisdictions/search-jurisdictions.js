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

  const coverageMap = useMemo(() => {
    if (!dashboardData || !selectedState) return {};
    const notScraped = new Set(
      dashboardData?.states?.[selectedState]?.locality_gaps?.not_yet_scraped ?? []
    );
    const result = {};
    for (const ocdid of notScraped) {
      result[ocdid] = 0;
    }
    return result;
  }, [dashboardData, selectedState]);

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

        <p>Select a jurisdiction below or click the map to get started.</p>
      </hgroup>
      <div class="page-grid">

        <div class="about-col">
          <div class="about-blurb">
            <h2>What is CivicPatch?</h2>
            <p>
              CivicPatch is a project that collects and maintains contact
              information for local government officials across the United States.
            </p>

            <h3>Where does the data go?</h3>
            <p>
              Collected data is published to
              <a href="https://github.com/civicpatch/open-data">civicpatch/open-data</a>,
              a public repository of U.S. local government contact information.
            </p>

            <h3>How can I help?</h3>
            <ul>
              <li><a href="https://github.com/civicpatch/civicpatch-tools/discussions">Share ideas or feedback</a></li>
              <li><a href="https://github.com/civicpatch/civicpatch-tools/issues">Report a bug</a></li>
              <li>Research and data validation:
                Reach out to <a href="mailto:michelle@civicpatch.org"><civ-badge .label=${"michelle@civicpatch.org"} .variant=${"primary"}></civ-badge></a>
                or
                <a href="https://unified.me/chat/!NcnsrToWrvzzzoLHWn" target="_blank" rel="noopener noreferrer"><civ-badge .label=${"community chat"} .variant=${"secondary"}></civ-badge></a>
              </li>
              <li>Funding and support for ongoing operations: <a href="https://ko-fi.com/civicpatch" target="_blank" rel="noopener noreferrer"><civ-badge .label=${"Ko-fi"} .variant=${"primary"}></civ-badge></a></li>
            </ul>
          </div>
        </div>

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
