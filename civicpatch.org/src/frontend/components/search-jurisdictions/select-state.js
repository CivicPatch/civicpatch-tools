import { component, useEffect, useState } from "haunted";
import { html } from "lit-html";

function CivSelectState({ selected }) {
  const [states, setStates] = useState([]);

  // Used only for the validation path — we don't have a direct e.target there.
  const emitResetViaHost = () => {
    const selectEl = this.querySelector('select');
    if (!selectEl) return;
    selectEl.dispatchEvent(
      new CustomEvent("state-change", {
        detail: { state: "" },
        bubbles: true,
        composed: true,
      }),
    );
  };

  // Normal user interaction — dispatch directly from e.target, same as original.
  const handleChange = (e) => {
    e.target.dispatchEvent(
      new CustomEvent("state-change", {
        detail: { state: e.target.value },
        bubbles: true,
        composed: true,
      }),
    );
  };

  useEffect(() => {
    fetch("/api/v1/jurisdictions/states")
      .then((res) => res.json())
      .then((data) => {
        const loaded = data.data || [];
        setStates(loaded);
        const validCodes = new Set(loaded.map((s) => s.code));
        if (selected && !validCodes.has(selected)) {
          emitResetViaHost();
        }
      });
  }, []);

  // Only use selected if it's recognised — avoids a visible flash of bad state.
  const effectiveSelected = states.some((s) => s.code === selected) ? selected : "";

  return html`
    <select .value=${effectiveSelected} @change=${handleChange}>
      <option value="" ?selected=${effectiveSelected === ""}>— Select a state —</option>
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
