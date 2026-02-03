import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";

function PicoChipsInput({ value = [], onChange, placeholder = "Add..." }) {
  const [chips, setChips] = useState(value);

  useEffect(() => {
    setChips(value);
  }, [value]);

  useEffect(() => {
    onChange && onChange(chips);
  }, [chips]);

  const handleAdd = (e) => {
    e.preventDefault();
    const input = e.target.elements["chip-input"];
    const val = input.value.trim();
    if (val && !chips.includes(val)) {
      setChips([...chips, val]);
    }
    input.value = "";
  };

  const handleRemove = (idx) => {
    setChips(chips.filter((_, i) => i !== idx));
  };

  return html`
    <style>
      .pico-chips-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5em;
        align-items: center;
        margin-bottom: 0.5em;
      }
      .pico-chip-btn {
        display: inline-flex;
        align-items: center;
        background: var(--pico-primary-background, #e0e8f3);
        border: 1px solid var(--pico-primary, #264478);
        border-radius: 2em;
        padding: 0.18em 0.7em 0.18em 0.7em;
        font-size: 0.97em;
        font-weight: 500;
        cursor: pointer;
      }
      .pico-chip-btn .close-x {
        margin-left: 0.5em;
        font-size: 1.1em;
        opacity: 0.7;
        transition: opacity 0.2s;
        background: none;
        border: none;
        cursor: pointer;
        padding: 0;
        line-height: 1;
        display: flex;
        align-items: center;
      }
      .pico-chip-btn .close-x:hover {
        opacity: 1;
      }
      .pico-chips-row input[type="text"] {
        min-width: 100px;
        border: 1px solid var(--pico-muted-border-color, #e0e0e0);
        padding: 0.25em 0.75em;
        font-size: 1em;
        outline: none;
        transition: border 0.2s;
      }
      .pico-chips-row input[type="text"]:focus {
        border: 1.5px solid var(--pico-primary, #0d6efd);
      }
    </style>
    <div class="pico-chips-row">
      ${chips.map(
        (chip, i) => html`
          <button
            type="button"
            class="pico-chip-btn"
            @click=${() => handleRemove(i)}
            aria-label="Remove ${chip}"
          >
            <span>${chip}</span>
            <span class="close-x" aria-hidden="true">&times;</span>
          </button>
        `
      )}
      <form @submit=${handleAdd} style="display: inline;">
        <input
          name="chip-input"
          type="text"
          placeholder=${placeholder}
          autocomplete="off"
        />
      </form>
    </div>
  `;
}

customElements.define(
  "pico-chips-input",
  component(PicoChipsInput, { useShadowDOM: false })
);