import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";

function SearchJurisdictions() {
    const [selectedState, setSelectedState] = useState(null);
    const [selectedJurisdiction, setSelectedJurisdiction] = useState(null);
    const [people, setPeople] = useState([]);
    const [geojson, setGeojson] = useState([]);

    useEffect(() => {
        if (!selectedJurisdiction) return;


        fetch(`/api/crudder/jurisdictions/${selectedJurisdiction.jurisdiction_ocdid_slug}/people`)
            .then((response) => response.json())
            .then((data) => {
                setPeople(data.data);
            });
    }, [selectedJurisdiction])

    const handleSelectJurisdictionChange = (event) => {
        const { state, jurisdiction } = event.detail;
        console.log("Selected State:", state);
        setSelectedState(state);
        // TODO: pan the map if state but no jurisdiction
        console.log("Selected Jurisdiction:", jurisdiction);
        setSelectedJurisdiction(jurisdiction)
        // TODO: pan the map & zoom if state and jurisdiction
    }

    const handleMapChange = (event) => {
        const { latlng, zoom } = event.detail;
        if (!latlng || !zoom) return;
        console.log("Map Change - LatLng:", latlng, "Zoom:", zoom);
        fetch(`/api/crudder/jurisdictions/geojson?lat=${latlng.lat}&long=${latlng.lng}&zoom=${zoom}`)
            .then((response) => response.json())
            .then((data) => {
                setGeojson(data);
            });
    }

    return html`
        <div style="display: flex; flex-direction: column; gap: 2rem;">
          <div class="grid">
              <div>
                  <civ-map
                    @on-map-change=${handleMapChange}
                    .geojson=${geojson}
                  ></civ-map>
              </div>
              <civ-select-jurisdiction 
                  @select-jurisdiction-change=${handleSelectJurisdictionChange} 
              ></civ-select-jurisdiction>
          </div>
          <civ-people-list .local=${people}></civ-people-list>
        </div>
        `
}

customElements.define(
  "civ-search-jurisdictions",
  component(SearchJurisdictions, { useShadowDOM: false, observedAttributes: [] })
);
