import { component, useEffect, useState, useRef } from "haunted";
import { html } from "lit-html";
import { useAuth } from "../../hooks/useAuth.js";
import "./select-state.js";

function CivSelectJurisdiction() {
  const { permissions } = useAuth();
  const [jurisdictions, setJurisdictions] = useState([]);
  const [jurisdictionsMetadata, setJurisdictionsMetadata] = useState({});
  const [selectedState, setSelectedState] = useState("");
  const [selectedJurisdiction, setSelectedJurisdiction] = useState("");
  const [jurisdictionInputValue, setJurisdictionInputValue] = useState("");
  console.log("permissions in CivSelectJurisdiction:", permissions);

  const isInitialMount = useRef(true);

  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return; 
    }
    // Call the handler with the current selections
    handleInputChange(selectedState, selectedJurisdiction);
  }, [selectedState, selectedJurisdiction]);

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
  };

  const handleJurisdictionSuggestions = (detail) => {
    const query = detail.query || "";
    const page = detail.page || 1;
    const pageSize = detail.pageSize || 25;
    fetch(`/api/api_proxy/jurisdictions/${selectedState}/search?search_string=${encodeURIComponent(query)}&limit=${pageSize}&page=${page}`)
      .then((res) => res.json())
      .then((data) => {
        setJurisdictions(data.data || []);
        setJurisdictionsMetadata({
          total_items: data.total_items,
          total_pages: data.total_pages,
          page: data.page,
          limit: data.limit,
          links: data.links
        });
      }); 
  };

  const handleSubmitClick = (e) => {
    e.preventDefault();

    const jurisdiction_data = jurisdictions.find(jur => jur.id === selectedJurisdiction);
    const jurisdiction_ocdid_slug = jurisdiction_data["jurisdiction_ocdid_slug"];
    window.location.href = `/jurisdictions/${jurisdiction_ocdid_slug}`;
  };

  const jurisdictionLink = () => {
    if (!selectedJurisdiction) return "";
    if (!jurisdictions) return "";

    const jurisdictionOcdidFormatted = encodeURIComponent(selectedJurisdiction);
    return jurisdictionOcdidFormatted ? `/jurisdictions?jurisdiction_ocdid=${jurisdictionOcdidFormatted}` : "";
  };

  return html`
    <form 
      class="grid" 
      style="grid-template-columns: 2fr; gap: 1rem;"
      onsubmit="return false;"
    >
      <civ-select-state
        .selected=${selectedState}
        @state-change=${(e) => setSelectedState(e.detail.state)}
      ></civ-select-state>
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
          setJurisdictionInputValue(value);
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
      ${ permissions.JURISDICTION_PAGE ? html`
        <a href="${jurisdictionLink()}" ?hidden=${!selectedJurisdiction}>
          Go to jurisdiction page
        </a>
      ` : null }
    </form>
  `;
}

customElements.define(
  "civ-select-jurisdiction",
  component(CivSelectJurisdiction, { useShadowDOM: false, observedAttributes: [] })
);


