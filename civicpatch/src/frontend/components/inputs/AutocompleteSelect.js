import { component, useState, useMemo } from 'haunted';
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
function AutocompleteSelect({ options = [], label = 'Search' }) {
  const [inputValue, setInputValue] = useState('');
  const [selectedItem, setSelectedItem] = useState(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [isListOpen, setIsListOpen] = useState(false);
  const [inputElement, setInputElement] = useState(null);

  // --- External Fetch Trigger Logic ---
  const triggerParentFetch = (input) => {
    const query = input || '';
    this.dispatchEvent(new CustomEvent('fetch-suggestions', { 
      detail: { query }, 
      bubbles: true, 
      composed: true 
    }));
    setActiveIndex(-1);
  };

  const debouncedFetch = useMemo(() => debounce(triggerParentFetch, 300), []);

  // --- Selection Logic ---
  const selectItem = (item) => {
    setInputValue(item.label);
    setSelectedItem(item);
    setIsListOpen(false);
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

  // --- Handlers ---
  const handleInput = (e) => {
    const value = e.target.value;
    setInputValue(value);
    setSelectedItem(null);
    
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
        if (selectedItem) setInputValue(selectedItem.label);
        break;
    }
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
    <style>
      /* Autocomplete Select Component - Pico CSS Styles */
      .autocomplete-wrapper {
        position: relative;
        width: 100%;
      }

      /* Input and button container */
      .autocomplete-wrapper fieldset.grid {
        margin-bottom: 0;
        gap: 0;
      }

      .autocomplete-input {
        border-top-right-radius: 0;
        border-bottom-right-radius: 0;
        margin-bottom: 0;
      }

      .autocomplete-toggle {
        border-top-left-radius: 0;
        border-bottom-left-radius: 0;
        padding: 0.5rem 0.75rem;
        min-width: 3rem;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 0;
      }

      /* Dropdown list */
      .autocomplete-dropdown {
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: var(--pico-background-color);
        border: var(--pico-border-width) solid var(--pico-muted-border-color);
        border-radius: var(--pico-border-radius);
        margin-top: 0.25rem;
        max-height: 300px;
        overflow-y: auto;
        z-index: 99;
        box-shadow: var(--pico-box-shadow);
        list-style: none;
        margin-left: 0;
        margin-right: 0;
        padding: 0;
      }

      .autocomplete-option {
        padding: 0.75rem 1rem;
        cursor: pointer;
        border-bottom: 1px solid var(--pico-muted-border-color);
        transition: background-color 0.1s ease;
        list-style: none;
      }

      .autocomplete-option:last-child {
        border-bottom: none;
      }

      .autocomplete-option:hover,
      .autocomplete-option.active {
        background-color: var(--pico-secondary-background);
      }

      .autocomplete-option[aria-selected="true"] {
        background-color: var(--pico-primary-background);
        color: var(--pico-primary-inverse);
      }

      /* Visually hidden label for accessibility */
      .visually-hidden {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
      }

      /* Selected item display */
      .autocomplete-selected {
        display: block;
        margin-top: 0.5rem;
        color: var(--pico-muted-color);
      }
    </style>

    <label class="visually-hidden">${label}</label>
    <div class="autocomplete-wrapper">
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
          @blur=${() => setIsListOpen(false)}
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
        <ul 
          role="listbox" 
          aria-label=${label}
          class="autocomplete-dropdown"
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
      ` : ''}
      
      ${selectedItem ? html`<small class="autocomplete-selected">Selected: ${selectedItem.label}</small>` : ''}
    </div>
  `;
}

customElements.define(
  'civ-autocomplete-select',
  component(AutocompleteSelect, { useShadowDOM: false })
);