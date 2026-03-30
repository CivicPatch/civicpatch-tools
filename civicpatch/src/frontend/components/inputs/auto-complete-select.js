import { component, useState, useEffect, useMemo } from 'haunted';
import { html } from 'lit-html';
import { ref } from "lit-html/directives/ref.js";

// Debounce Utility
const debounce = (func, delay) => {
  let timeoutId;
  return (...args) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      func.apply(null, args);
    }, delay);
  };
};

// --- Component Definition ---
function AutocompleteSelect({ 
  disabled, 
  optionsMetadata = {},
  options = [], 
  label = 'Search', inputValue = '',
  pageSize = 25,
}) {
  const [selectedItem, setSelectedItem] = useState(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [isListOpen, setIsListOpen] = useState(false);
  const [inputElement, setInputElement] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    if (!inputValue) {
      setSelectedItem(null);
    }
  }, [inputValue])

  useEffect(() => {
    if (activeIndex >= 0) {
      scrollToActiveItem(activeIndex);
    }
  }, [activeIndex])

  const triggerParentFetch = (input, page = 1) => {
    const query = input || '';
    this.dispatchEvent(new CustomEvent('fetch-suggestions', { 
      detail: { query, page, pageSize }, 
      bubbles: true, 
      composed: true 
    }));
    setActiveIndex(-1);
    setCurrentPage(page);
  };

  const debouncedFetch = useMemo(() => debounce(triggerParentFetch, 300), []);

  // --- Selection Logic ---
  const selectItem = (item) => {
    setSelectedItem(item);
    setIsListOpen(false);
    setCurrentPage(1);
    if (inputElement) inputElement.focus();
    
    this.dispatchEvent(new CustomEvent('item-selected', { 
      detail: item, 
      bubbles: true, 
      composed: true 
    }));
    
    this.dispatchEvent(new CustomEvent('input-change', { 
      detail: { value: item.label, item }, 
      bubbles: true, 
      composed: true 
    }));
  };

  const hasPrevPage = optionsMetadata?.links?.prev;
  const hasNextPage = optionsMetadata?.links?.next;

  const handlePrevPage = (e) => {
    e.preventDefault();

    if (hasPrevPage) {
      triggerParentFetch(inputValue, currentPage - 1);
    }
  }


  const handleNextPage = (e) => {
    e.preventDefault();

    if (hasNextPage) {
      triggerParentFetch(inputValue, currentPage + 1);
    }
  }


  // --- Handlers ---
  const handleInput = (e) => {
    const value = e.target.value;
    setSelectedItem(null);
    setCurrentPage(1);
    
    this.dispatchEvent(new CustomEvent('input-change', { 
      detail: { value, item: null }, 
      bubbles: true, 
      composed: true 
    }));
    
    debouncedFetch(value);
  };

  const handleKeyDown = (e) => {
    if (options.length === 0) return;
    
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setIsListOpen(true);
        setActiveIndex(index => (index + 1) % options.length);
        break;
      case 'ArrowUp':
        e.preventDefault();
        setIsListOpen(true);
        setActiveIndex(index => (index - 1 + options.length) % options.length);
        break;
      case 'Enter':
        if (activeIndex >= 0 && isListOpen) {
          e.preventDefault();
          selectItem(options[activeIndex]);
        }
        break;
      case 'Escape':
        setIsListOpen(false);
        break;
    }
  };

    // Scroll active item into view
  const scrollToActiveItem = (index) => {
    // Use setTimeout to ensure DOM has updated
    setTimeout(() => {
      const activeItem = this.querySelector(`.autocomplete-option[aria-selected="true"]`);
      if (activeItem) {
        activeItem.scrollIntoView({ 
          behavior: 'smooth', 
          block: 'nearest' 
        });
      }
    }, 0);
  };

  const handleFocusOut = (e) => {
    if (!this.contains(e.relatedTarget)) setIsListOpen(false);
  };

  const handleButtonClick = () => {
    const newState = !isListOpen;
    setIsListOpen(newState);
    if (newState && inputElement) {
      inputElement.focus();
    }
  };

  const handleSuggestionClick = (item) => {
    selectItem(item);
  };

  return html`
    <label class="visually-hidden">${label}</label>
    <div class="autocomplete-wrapper" @focusout=${handleFocusOut}>
      <fieldset class="grid" role="group">
        <input 
          class="autocomplete-input" 
          type="text" 
          role="combobox" 
          aria-autocomplete="both" 
          aria-expanded=${isListOpen ? 'true' : 'false'}
          aria-label=${label}
          .value=${inputValue}
          @input=${handleInput}
          @keydown=${handleKeyDown}
          @focus=${() => setIsListOpen(true)}
          ${ref(setInputElement)}
        >
        
        <button 
          type="button" 
          class="autocomplete-toggle"
          aria-label="Toggle suggestions list" 
          aria-expanded=${isListOpen ? 'true' : 'false'}
          tabindex="-1"
          @click=${handleButtonClick}
        >
          <svg width="18" height="16" aria-hidden="true" focusable="false">
            <polygon 
              class="arrow" 
              stroke-width="0" 
              fill-opacity="0.75" 
              fill="currentcolor" 
              points="3,6 15,6 9,14"
              style="transform: rotate(${isListOpen ? '180deg' : '0deg'}); transform-origin: 50% 50%; transition: transform 0.2s;"
            ></polygon>
          </svg>
        </button>
      </fieldset>
      
      ${isListOpen && options.length > 0 ? html`
        <div class="autocomplete-dropdown">
          <ul 
            role="listbox" 
            aria-label=${label}
            class="autocomplete-options"
          >
            ${options.map((item, index) => html`
              <li 
                role="option"
                aria-selected=${index === activeIndex ? 'true' : 'false'}
                @mousedown=${(e) => { e.preventDefault(); handleSuggestionClick(item); }}
                @mouseover=${() => setActiveIndex(index)}
                class="autocomplete-option ${index === activeIndex ? 'active' : ''}"
              >
                ${item.label}
              </li>
            `)}
          </ul>
          
          ${optionsMetadata?.total_items > pageSize ? html`
            <div class="autocomplete-pagination">
              <span class="autocomplete-pagination-info">
                Showing ${optionsMetadata?.page}-${optionsMetadata?.total_pages} of ${optionsMetadata?.total_items}
              </span>
              <div class="autocomplete-pagination-controls">
                <button 
                  type="button"
                  @mousedown=${handlePrevPage}
                  ?disabled=${!hasPrevPage}
                  aria-label="Previous page"
                >
                  Previous
                </button>
                <button 
                  type="button"
                  @mousedown=${handleNextPage}
                  ?disabled=${!hasNextPage}
                  aria-label="Next page"
                >
                  Next
                </button>
              </div>
            </div>
          ` : ''}
        </div>
      ` : ''}
      
      ${selectedItem ? html`<small class="autocomplete-selected">Selected: ${selectedItem.label}</small>` : ''}
    </div>
  `;
}

customElements.define(
  'civ-autocomplete-select',
  component(AutocompleteSelect, { useShadowDOM: false })
);