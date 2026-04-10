import "./search-jurisdictions.css";
import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import { fetchPeople, fetchDashboard } from "../../api.js";
// import { fetchJurisdictionsGeojson } from "../../api.js"; // map temporarily disabled
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { useAuth } from "../../hooks/useAuth.js";
import "../../components/badge/badge.js";
import "../../components/progress-dashboard/summary-stats.js";
import "../../components/progress-dashboard/locality-gaps.js";
import "../../components/progress-dashboard/states-overview.js";

function SearchJurisdictions() {
  const { permissions } = useAuth();
  const [defaultState] = useLocalStorage("app:default-state", "", { ttl: PERSIST_FOREVER });
  const [selectedState, setSelectedState] = useState((defaultState || '').toLowerCase());
  const [selectedJurisdictionOcdid, setSelectedJurisdictionOcdid] = useState(null);
  const [people, setPeople] = useState([]);
  const [dashboardData, setDashboardData] = useState(null);

  const [gapsOpen, setGapsOpen] = useLocalStorage("search_page_gaps_open", true, { ttl: PERSIST_FOREVER });

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

  const handleStateChange = (event) => {
    setSelectedState((event.detail.state || '').toLowerCase());
  };

  const handleSelectJurisdictionChange = (event) => {
    const { jurisdiction_ocdid } = event.detail;
    setSelectedJurisdictionOcdid(jurisdiction_ocdid);
  };

  // const handleMapChange = (event) => { // map temporarily disabled
  //   const { latlng, zoom } = event.detail;
  //   if (!latlng || !zoom) return;
  //   fetchJurisdictionsGeojson(latlng.lat, latlng.lng, zoom).then(data => setGeojson(data));
  // };

  return html`
    <div class="search-page">
      <hgroup>
        <h1>Find your representatives</h1>

        <p>Find contact information for local government officials across the U.S.</p>

        <p>Select a jurisdiction below to get started.</p>
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
              <li>Funding and support for ongoing operations: Reach out to <a href="mailto:info@civicdata.tech"><civ-badge .label=${"info@civicdata.tech"} .variant=${"primary"}></civ-badge></a></li>
            </ul>
          </div>
        </div>

        <div class="select-col">
          <civ-select-jurisdiction
            .selected=${selectedState}
            @state-change=${handleStateChange}
            @select-jurisdiction-change=${handleSelectJurisdictionChange}
          ></civ-select-jurisdiction>
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

      <div class="below-grid">
        <civ-people-list .local=${people} .jurisdictionSelected=${!!selectedJurisdictionOcdid}></civ-people-list>
        ${permissions.JURISDICTION_PAGE && dashboardData && selectedState && dashboardData.states?.[selectedState]?.locality_gaps?.not_yet_scraped?.length ? html`
          <details ?open=${gapsOpen} @toggle=${e => setGapsOpen(e.target.open)}>
            <summary>Not scraped</summary>
            <locality-gaps .stats=${dashboardData} .state=${selectedState}></locality-gaps>
          </details>
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
