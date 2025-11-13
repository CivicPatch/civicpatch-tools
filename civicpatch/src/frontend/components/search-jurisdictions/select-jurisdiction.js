import { component, useEffect, useState, useRef}  from "haunted";
import { html } from "lit-html";

function CivSelectJurisdiction() {
  const [states, setStates] = useState([]);
  const [jurisdictions, setJurisdictions] = useState([]);
  const [jurisdictionsMetadata, setJurisdictionsMetadata] = useState({});
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
    setJurisdictionsMetadata({});
    setSelectedJurisdiction("");
    setJurisdictionInputValue("");

    if (!selectedState) return;
    
    // Fetch jurisdictions for selected state (no auth header needed)
    handleJurisdictionSuggestions("");
  }, [selectedState]);

  const handleInputChange = (state, jurisdictionOcdid) => {
    this.dispatchEvent(
      new CustomEvent("select-jurisdiction-change", {
        detail: { state, jurisdiction_ocdid: jurisdictionOcdid },
        bubbles: true,
        composed: true,
      })
    );
  }

  const handleJurisdictionSuggestions = (detail) => {
    const query = detail.query || "";
    const page = detail.page || 1;
    const pageSize = detail.pageSize || 25;
    fetch(`/api/crudder/jurisdictions/${selectedState}/search?search_string=${encodeURIComponent(query)}&limit=${pageSize}&page=${page}`)
      .then((res) => res.json())
      .then((data) => {
        setJurisdictions(data.data || []);
        setJurisdictionsMetadata({
          total_items: data.total_items,
          total_pages: data.total_pages,
          page: data.page,
          limit: data.limit,
          links: data.links
        })
      }); 
  }

  const handleSubmitClick = (e) => {
    e.preventDefault();

    const jurisdiction_data = jurisdictions.find(jur => jur.id === selectedJurisdiction);
    const jurisdiction_ocdid_slug = jurisdiction_data["jurisdiction_ocdid_slug"];
    window.location.href = `/jurisdictions/${jurisdiction_ocdid_slug}`;
  }

  const jurisdictionLink = () => {
    if (!selectedJurisdiction) return "";
    if (!jurisdictions) return "";
    const jurisdiction_data = jurisdictions.find(jur => jur.id === selectedJurisdiction);
    const jurisdiction_ocdid_slug = jurisdiction_data ? jurisdiction_data["jurisdiction_ocdid_slug"] : "";
    return jurisdiction_ocdid_slug ? `/jurisdictions/${jurisdiction_ocdid_slug}` : "";
  }

  return html`
    <form 
      class="grid" 
      style="grid-template-columns: 2fr; gap: 1rem;"
      onsubmit="return false;"
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
        .optionsMetadata=${jurisdictionsMetadata}
        .pageSize=${25}
        @fetch-suggestions=${(e) => {
          const detail = e.detail;
          handleJurisdictionSuggestions(detail);
        }}
        @input-change=${(e) => {
          const {value, item} = e.detail;
          setJurisdictionInputValue(value)
          setSelectedJurisdiction(item ? item.value : "");
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


