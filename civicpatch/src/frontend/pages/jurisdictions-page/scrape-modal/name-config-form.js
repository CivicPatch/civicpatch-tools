import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import "../../basic/chip.js"

function NameConfigForm({ onChange, identities = {} }) {
  const [configs, setConfigs] = useState({ ...identities });
  const [newIdentity, setNewIdentity] = useState("");

  useEffect(() => {
    setConfigs({ ...identities });
  }, [identities]);

  useEffect(() => {
    onChange(configs);
  }, [configs, onChange]);

  const handleAddIdentity = (e) => {
    e.preventDefault();
    const name = newIdentity.trim();
    if (name && !configs[name]) {
      setConfigs((prev) => ({ ...prev, [name]: [] }));
      setNewIdentity("");
    }
  };

  return html`
    <div>
      ${Object.keys(configs).map(
        (identity) => html`
          <fieldset style="margin-bottom: 1em;">
            <label>${identity}</label>
            <pico-chips-input
              .value=${configs[identity] || []}
              .onChange=${(chips) => {
                setConfigs((prev) => ({
                  ...prev,
                  [identity]: chips,
                }));
              }}
              placeholder="Add alternate name..."
            ></pico-chips-input>
          </fieldset>
        `
      )}
      <form @submit=${handleAddIdentity} style="margin-top: 1em; display: flex; gap: 0.5em;">
        <input
          type="text"
          .value=${newIdentity}
          @input=${(e) => setNewIdentity(e.target.value)}
          placeholder="Add identity name..."
          style="flex: 1;"
        />
        <button type="submit" class="secondary">Add Identity</button>
      </form>
    </div>
  `;
}

customElements.define(
  "name-config-form",
  component(NameConfigForm, { useShadowDOM: false })
);