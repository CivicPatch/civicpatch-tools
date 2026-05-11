import { component, useEffect, useState } from "haunted";
import { html } from "lit-html";

function CivSelectState({ selected }) {
  const [states, setStates] = useState([]);

  const emitStateChange = (code) => {
    const selectEl = this.querySelector('select');
    if (!selectEl) return;
    selectEl.dispatchEvent(
      new CustomEvent("state-change", {
        detail: { state: code },
        bubbles: true,
        composed: true,
      }),
    );
  };

  const handleChange = (e) => emitStateChange(e.target.value);

  useEffect(() => {
    fetch("/api/v1/jurisdictions/states")
      .then((res) => res.json())
      .then((data) => {
        const loaded = data.data || [];
        setStates(loaded);
        // Reset immediately if the stored state isn't in the valid list.
        const validCodes = new Set(loaded.map((s) => s.code));
        if (selected && !validCodes.has(selected)) {
          emitStateChange("");
        }
      });
  }, []);

  // Only use selected if it's recognised — avoids a visible flash of bad state.
  const effectiveSelected = states.some((s) => s.code === selected) ? selected : "";

  return html`
    <select .value=${effectiveSelected} @change=${handleChange}>
      ${states.map(
        (state) =>
          html`<option value=${state.code} ?selected=${state.code === effectiveSelected}>${state.name}</option>`,
      )}
    </select>
  `;
}


customElements.define(
  "civ-select-state",
  component(CivSelectState, { useShadowDOM: false, observedAttributes: [] }),
);
