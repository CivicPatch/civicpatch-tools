import { component, useEffect, useState, useRef}  from "haunted";
import { html } from "lit-html";

function CivSelectJurisdiction() {
  const [states, setStates] = useState([]);
  const [jurisdictions, setJurisdictions] = useState([]);
  const [selectedState, setSelectedState] = useState("");
  const [selectedJurisdiction, setSelectedJurisdiction] = useState("");

  const isInitialMount = useRef(true);

  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return; 
    }
    // Call the handler with the current selections
    handleInputChange(selectedState, selectedJurisdiction);
  }, [selectedState, selectedJurisdiction])

  useEffect(() => {
    // Fetch states from backend proxy (no auth header needed)
    fetch("/api/crudder/jurisdictions/states")
      .then((res) => res.json())
      .then((data) => setStates(data.data || []));
  }, []);

  useEffect(() => {
    setJurisdictions([]);
    setSelectedJurisdiction("");

    if (!selectedState) return;
    
    // Fetch jurisdictions for selected state (no auth header needed)
    fetch(`/api/crudder/jurisdictions/${selectedState}/search?limit=100`)
      .then((res) => res.json())
      .then((data) => setJurisdictions(data.data || []));
  }, [selectedState]);

  const handleInputChange = (state, jurisdiction) => {
    // Dispatch a custom event with the selected state and jurisdiction
    this.dispatchEvent(
      new CustomEvent("select-jurisdiction-change", {
        detail: { state, jurisdiction },
        bubbles: true,
        composed: true,
      })
    );
  }

  const handleSubmitClick = (e) => {
    e.preventDefault();


    this.dispatchEvent(
      new CustomEvent("select-jurisdiction-submit", {
        detail: { state: selectedState, jurisdiction: selectedJurisdiction },
        bubbles: true,
        composed: true,
      })
    );
  }

  const canSubmit = !!selectedJurisdiction

  return html`
    <form class="grid" style="grid-template-columns: 2fr; gap: 1rem;">
      <label for="state-select" class="visually-hidden">State:</label>
      <select
        id="state-select"
        .value=${selectedState}
        @change=${(e) => setSelectedState(e.target.value)}
        required
      >
        <option value="">Select a state</option>
        ${states.map(
          (state) => html`<option value=${state}>${state}</option>`
        )}
      </select>

      <label for="jurisdiction-select" class="visually-hidden">Jurisdiction:</label>
      <select
        id="jurisdiction-select"
        .value=${selectedJurisdiction}
        @change=${(e) => setSelectedJurisdiction(e.target.value)}
        required
      >
        <option value="">Select a jurisdiction</option>
        ${jurisdictions.map(
          (jur) => html`<option value=${jur.id}>${jur.name}</option>`
        )}
      </select>
      <civ-autocomplete-select
        id="jurisdiction-autocomplete"
        .options=${jurisdictions.map(jur => ({ label: jur.name, value: jur.id }))}
        @fetch-suggestions=${(e) => {
          const query = e.detail.query.toLowerCase();
          console.log("suggestions needed for query:", query);
        }}
        @input-change=${(e) => {
          const item = e.detail.item;
          console.log("Autocomplete input change:", item);
        }}
        @item-selected=${(e) => setSelectedJurisdiction(e.detail.value)}
      ></civ-autocomplete-select>

      <button 
        type="submit" 
        @click=${handleSubmitClick} 
        ?disabled=${!canSubmit}>Submit</button>
    </form>
  `;
}

customElements.define(
  "civ-select-jurisdiction",
  component(CivSelectJurisdiction, { useShadowDOM: false, observedAttributes: [] })
);


