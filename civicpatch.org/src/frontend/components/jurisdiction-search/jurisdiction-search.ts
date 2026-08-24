import "./jurisdiction-search.css";
import { component, useState } from "haunted";
import { html } from "lit-html";
import { searchJurisdictions } from "../../api.js";
import { jurisdictionOcdidToFriendly } from "../ocdid-utils.js";
import "../inputs/auto-complete-select.js";

const PAGE_SIZE = 10;
// Examples carry the format better than an abstract label, and sitting in the input they
// cost no vertical space next to the map.
const PLACEHOLDER = 'Try “Seattle, WA” or “King County”';
const SELECT_EVENT = "jurisdiction-select";

interface SearchResult {
  jurisdiction_ocdid: string;
  level: string;
  name: string;
  display_name: string | null;
  population: number | null;
  parent_names: string[];
}

interface SearchMetadata {
  total_items: number;
  page: number;
  total_pages: number;
  limit: number;
  links: { prev: string; next: string; self: string };
}

// The API returns display_name as null until open-data emits the field, so fall back to
// the ocdid-derived form rather than showing the Census suffix as the headline.
const friendlyName = (result: SearchResult) =>
  result.display_name || jurisdictionOcdidToFriendly(result.jurisdiction_ocdid);

const levelLabel = (level: string) =>
  level === "counties" ? "County" : "Local";

type JurisdictionSearchHost = HTMLElement & {
  state?: string;
  level?: string;
  placeholder?: string;
};

function JurisdictionSearch(this: JurisdictionSearchHost) {
  const hostState = this.state;
  const hostLevel = this.level;
  const hostPlaceholder = this.placeholder || PLACEHOLDER;
  const [results, setResults] = useState<SearchResult[]>([]);
  const [metadata, setMetadata] = useState<SearchMetadata | null>(null);
  const [query, setQuery] = useState("");

  const fetchSuggestions = async (detail: { query: string; page: number }) => {
    if (!detail.query) {
      setResults([]);
      setMetadata(null);
      return;
    }
    try {
      const body = await searchJurisdictions(detail.query, {
        page: detail.page,
        limit: PAGE_SIZE,
        state: hostState,
      });
      setResults(body.data);
      setMetadata(body);
    } catch (error) {
      // An aborted request is the expected outcome of typing another character, not a
      // failure — leave the previous results in place for the in-flight query to replace.
      if ((error as Error).name === "AbortError") return;
      throw error;
    }
  };

  const handleSelect = (result: SearchResult) =>
    this.dispatchEvent(
      new CustomEvent(SELECT_EVENT, {
        detail: result,
        bubbles: true,
        composed: true,
      }),
    );

  // The option list carries {label, value} for the component's own bookkeeping; the row
  // itself is rendered from the full result.
  const options = results.map((result) => ({
    label: friendlyName(result),
    value: result.jurisdiction_ocdid,
    result,
  }));

  const renderOption = (option: { result: SearchResult }) => {
    const { result } = option;
    const parents = (result.parent_names || []).join(", ");
    return html`
      <div class="jurisdiction-search__row">
        <span>
          <span class="jurisdiction-search__name">${friendlyName(result)}</span>
          <span class="jurisdiction-search__where">
            ${result.name}${parents ? ` — ${parents}` : ""}
          </span>
        </span>
        <span class="jurisdiction-search__meta">
          <span class="jurisdiction-search__level">${levelLabel(result.level)}</span>
          ${result.population === null
            ? ""
            : html`<span>${result.population.toLocaleString()}</span>`}
        </span>
      </div>
    `;
  };

  return html`
    <div class="jurisdiction-search">
      <civ-autocomplete-select
        .label=${"Search by location"}
        .placeholder=${hostPlaceholder}
        .showToggle=${false}
        .options=${options}
        .optionsMetadata=${metadata ?? {}}
        .inputValue=${query}
        .pageSize=${PAGE_SIZE}
        .renderOption=${renderOption}
        @fetch-suggestions=${(e: CustomEvent) => fetchSuggestions(e.detail)}
        @input-change=${(e: CustomEvent) => setQuery(e.detail.value)}
        @item-selected=${(e: CustomEvent) => handleSelect(e.detail.result)}
      ></civ-autocomplete-select>
    </div>
  `;
}

customElements.define(
  "civ-jurisdiction-search",
  component(JurisdictionSearch as any, {
    useShadowDOM: false,
    observedAttributes: [],
  }),
);
