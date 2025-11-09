import { component, useEffect, useState, useRef}  from "haunted";
import { html } from "lit-html";

function CivSelectJurisdiction() {
  const [states, setStates] = useState([]);
  const [jurisdictions, setJurisdictions] = useState([]);
  const [selectedState, setSelectedState] = useState("");
  const [selectedJurisdiction, setSelectedJurisdiction] = useState("");
  const [jurisdictionInputValue, setJurisdictionInputValue] = useState("");

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
    setJurisdictionInputValue("");

    if (!selectedState) return;
    
    // Fetch jurisdictions for selected state (no auth header needed)
    fetch(`/api/crudder/jurisdictions/${selectedState}/search?limit=100`)
      .then((res) => res.json())
      .then((data) => setJurisdictions(data.data || []));
  }, [selectedState]);

  const handleInputChange = (state, jurisdiction) => {
    // Dispatch a custom event with the selected state and jurisdiction

    const jurisdiction_data = jurisdictions.find(jur => jur.id === selectedJurisdiction);
    this.dispatchEvent(
      new CustomEvent("select-jurisdiction-change", {
        detail: { state, jurisdiction: jurisdiction_data },
        bubbles: true,
        composed: true,
      })
    );
  }

  const handleSubmitClick = (e) => {
    e.preventDefault();

    const jurisdiction_data = jurisdictions.find(jur => jur.id === selectedJurisdiction);
    const jurisdiction_ocdid_slug = jurisdiction_data["jurisdiction_ocdid_slug"];
    window.location.href = `/jurisdictions/${jurisdiction_ocdid_slug}`;
  }

  const jurisdictionLink = () => {
    if (!selectedJurisdiction) return "";
    const jurisdiction_data = jurisdictions.find(jur => jur.id === selectedJurisdiction);
    const jurisdiction_ocdid_slug = jurisdiction_data["jurisdiction_ocdid_slug"];
    return `/jurisdictions/${jurisdiction_ocdid_slug}`;
  }

  return html`
    <form 
      class="grid" 
      style="grid-template-columns: 2fr; gap: 1rem;"
    >
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
      <civ-autocomplete-select
        id="jurisdiction-autocomplete"
        .disabled=${!selectedState}
        .inputValue=${jurisdictionInputValue}
        .options=${jurisdictions.map(jur => ({ label: jur.name, value: jur.id }))}
        @fetch-suggestions=${(e) => {
          const query = e.detail.query.toLowerCase();
          console.log("suggestions needed for query:", query);
        }}
        @input-change=${(e) => {
          const value = e.detail.value;
          console.log("Autocomplete input change:", value);
          setJurisdictionInputValue(value)
        }}
        @item-selected=${(e) => setSelectedJurisdiction(e.detail.value)}
      ></civ-autocomplete-select>
      <!-- comment out submit button for now.
      <button 
        type="submit" 
        @click=${handleSubmitClick} 
        ?disabled=${!selectedJurisdiction}>Submit</button>
      -->
      <a href="${jurisdictionLink()}" ?hidden=${!selectedJurisdiction}>
        Go to jurisdiction page
      </a>
    </form>
  `;
}

customElements.define(
  "civ-select-jurisdiction",
  component(CivSelectJurisdiction, { useShadowDOM: false, observedAttributes: [] })
);


