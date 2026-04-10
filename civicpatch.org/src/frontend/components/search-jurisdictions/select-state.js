import { component, useEffect, useState } from "haunted";
import { html } from "lit-html";

function CivSelectState({ selected }) {
  const [states, setStates] = useState([]);

  useEffect(() => {
    fetch("/api/v1/jurisdictions/states")
      .then((res) => res.json())
      .then((data) => setStates(data.data || []));
  }, []);

  const handleChange = (e) => {
    e.target.dispatchEvent(
      new CustomEvent("state-change", {
        detail: { state: e.target.value },
        bubbles: true,
        composed: true,
      }),
    );
  };

  return html`
    <select .value=${selected || ""} @change=${handleChange}>
      <option value="" ?selected=${!selected}>Select a state</option>
      ${states.map(
        (state) =>
          html`<option value=${state.code} ?selected=${state.code === selected}>${state.name}</option>`,
      )}
    </select>
  `;
}


customElements.define(
  "civ-select-state",
  component(CivSelectState, { useShadowDOM: false, observedAttributes: [] }),
);
