import { component, useEffect, useState } from 'haunted';
import { html } from 'lit-html';

function JurisdictionDashboard({ jurisdiction_ocdid_slug }) {
    const [data, setData] = useState(null);
    const [people, setPeople] = useState([]);

    useEffect(() => {
        if (!jurisdiction_ocdid_slug) return;

        fetchData()
    }, [])

    const fetchJurisdictionData = async (ocdid) => {
        const response = await fetch(`/api/crudder/jurisdictions/${ocdid}`);
        const result = await response.json();
        return result.data;
    }

    const fetchPeopleData = async (ocdid) => {
        const response = await fetch(`/api/crudder/jurisdictions/${ocdid}/people`);
        const result = await response.json();
        return result.data;
    }

    const fetchData = async () => {
        const [jurisdictionData, peopleData] = await Promise.all([
            fetchJurisdictionData(jurisdiction_ocdid_slug),
            fetchPeopleData(jurisdiction_ocdid_slug),
        ]);
        setData(jurisdictionData);
        setPeople(peopleData);
    }

    return html`
        <div style="display: flex; flex-direction: column; gap: 2rem;">
          <div class="grid">
              <div>
                  <civ-map
                    canmove="false"
                    latlngstring="30.24171,-91.991044"
                  ></civ-map>
              </div>

              <div> 
              ${
                data ? html`
                      <header>
                        <h2>${data.name}</h2>
                        <small>Population: ${data.population.toLocaleString()}</small>
                      </header>

                      <p>
                        <strong>Jurisdiction ID:</strong> ${data.id} <br/>
                        <strong>Website:</strong> ${data.url}
                      </p>

                      <a href="${data.url}" target="_blank" role="button" class="secondary">
                        Visit Official Website
                      </a>
                ` : html`
                  <p>Loading jurisdiction data...</p>
                `
              }
              </div>
          </div>
          <civ-people-list
            .local=${people} 
          ></civ-people-list>
        </div>
    `
}

customElements.define(
    'civ-jurisdiction-dashboard', 
    component(JurisdictionDashboard, { useShadowDOM: false, observedAttributes: ['jurisdiction_ocdid_slug'] })
);