import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import { fetchPeople, fetchDashboard } from "../../api.js";
// import { fetchJurisdictionsGeojson } from "../../api.js"; // map temporarily disabled
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import "../../components/progress-dashboard/summary-stats.js";
import "../../components/progress-dashboard/locality-gaps.js";

function SearchJurisdictions() {
  const [selectedState, setSelectedState] = useState(null);
  const [selectedJurisdictionOcdid, setSelectedJurisdictionOcdid] = useState(null);
  const [people, setPeople] = useState([]);
  const [dashboardData, setDashboardData] = useState(null);

  const [aboutOpen, setAboutOpen] = useLocalStorage("search_page_about_open", true, { ttl: PERSIST_FOREVER });
  const [progressOpen, setProgressOpen] = useLocalStorage("search_page_progress_open", true, { ttl: PERSIST_FOREVER });
  const [gapsOpen, setGapsOpen] = useLocalStorage("search_page_gaps_open", true, { ttl: PERSIST_FOREVER });

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
          <details ?open=${aboutOpen} @toggle=${e => setAboutOpen(e.target.open)}>
            <summary>What is CivicPatch?</summary>
            <div class="about-blurb">
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
                <li>Funding or data partnerships: <a href="mailto:info@civicdata.tech">info@civicdata.tech</a></li>
              </ul>
            </div>
          </details>
        </div>

        <div class="select-col">
          <civ-select-jurisdiction
            @select-jurisdiction-change=${handleSelectJurisdictionChange}
          ></civ-select-jurisdiction>

          ${dashboardData && selectedState ? html`
            <details ?open=${progressOpen} @toggle=${e => setProgressOpen(e.target.open)}>
              <summary>Progress — ${selectedState}</summary>
              <summary-stats .stats=${dashboardData} .state=${selectedState}></summary-stats>
            </details>
          ` : ''}
        </div>

      </div>

      <div class="below-grid">
        <civ-people-list .local=${people} .jurisdictionSelected=${!!selectedJurisdictionOcdid}></civ-people-list>
        ${dashboardData && selectedState ? html`
          <details ?open=${gapsOpen} @toggle=${e => setGapsOpen(e.target.open)}>
            <summary>Not yet scraped</summary>
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
