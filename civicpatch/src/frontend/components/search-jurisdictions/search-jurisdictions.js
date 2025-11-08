import { component } from "haunted";
import { html } from "lit-html";

function SearchJurisdictions() {
    const jurisdictionSection = html`
        <div class="grid">
          <div>
            <civ-map
                canmove="false"
                latlngstring="30.24171,-91.991044"
            ></civ-map>
          </div>

          <div>
            <h1>Jurisdiction</h1>
            <h2>blah blah</h2>
            <civ-pipeline-details></civ-pipeline-details>
            <civ-people-list></civ-people-list>
            <p>The content in the second column is flexible and takes up the remaining available space equally.</p>
            <ul>
              <li>Item 1</li>
              <li>Item 2</li>
            </ul>
          </div>
        </div>
    `;

    return html`
        <div style="display: flex; flex-direction: column; gap: 2rem;">
          <div class="grid">
              <div>
                  <civ-map></civ-map>
              </div>
              <civ-pipeline-form></civ-pipeline-form>
          </div>
          <civ-people-list></civ-people-list>
        </div>
        `
}

customElements.define(
  "civ-search-jurisdictions",
  component(SearchJurisdictions, { useShadowDOM: false, observedAttributes: [] })
);
