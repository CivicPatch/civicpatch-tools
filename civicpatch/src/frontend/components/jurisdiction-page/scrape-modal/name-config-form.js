import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";

function NameConfigForm({ onChange, existingNameConfigs = {} }) {
  // nameConfigs: [{ canonical: string, alternates: [string, ...] }]
  const [nameConfigs, setNameConfigs] = useState(
    Object.entries(existingNameConfigs).map(([canonical, alternates]) => ({
      canonical,
      alternates,
    }))
  );
  const [newCanonical, setNewCanonical] = useState("");
  const [newAlternate, setNewAlternate] = useState("");

  useEffect(() => {
    // Convert to { canonical: [alternates] } for parent
    const obj = {};
    nameConfigs.forEach(({ canonical, alternates }) => {
      if (canonical.trim()) obj[canonical.trim()] = alternates.filter((a) => a.trim());
    });
    onChange(obj);
  }, [nameConfigs]);

  const addIdentity = () => {
    if (newCanonical.trim()) {
      setNameConfigs([
        ...nameConfigs,
        { canonical: newCanonical.trim(), alternates: [] },
      ]);
      setNewCanonical("");
    }
  };

  const removeIdentity = (idx) => {
    setNameConfigs(nameConfigs.filter((_, i) => i !== idx));
  };

  const addAlternate = (idx) => {
    if (newAlternate.trim()) {
      const updated = [...nameConfigs];
      updated[idx].alternates.push(newAlternate.trim());
      setNameConfigs(updated);
      setNewAlternate("");
    }
  };

  const removeAlternate = (idx, altIdx) => {
    const updated = [...nameConfigs];
    updated[idx].alternates = updated[idx].alternates.filter((_, i) => i !== altIdx);
    setNameConfigs(updated);
  };

  return html`
    <section class="container">
      <label>
        <span>New Identity Name</span>
        <input
          type="text"
          class="input"
          .value=${newCanonical}
          @input=${(e) => setNewCanonical(e.target.value)}
          placeholder="e.g. Bob A"
        />
      </label>
      <button type="button" class="button" @click=${addIdentity}>
        Add Identity
      </button>
      <ul class="list" style="list-style: none;">
        ${nameConfigs.map(
          (cfg, idx) => html`
            <li class="card" style="list-style: none;">
              <div class="grid">
                <strong>${cfg.canonical}</strong>
                <button type="button" class="button outline" @click=${() => removeIdentity(idx)}>
                  Remove Identity
                </button>
              </div>
              <ul class="list" style="list-style: none;">
                ${cfg.alternates.map(
                  (alt, altIdx) => html`
                    <li class="grid">
                      <span>${alt}</span>
                      <button type="button" class="button outline" @click=${() => removeAlternate(idx, altIdx)}>
                        Remove
                      </button>
                    </li>
                  `
                )}
              </ul>
              <input
                type="text"
                class="input"
                .value=${idx === nameConfigs.length - 1 ? newAlternate : ""}
                @input=${(e) => setNewAlternate(e.target.value)}
                placeholder="Add alternate name"
              />
              <button type="button" class="button" @click=${() => addAlternate(idx)}>
                Add Alternate
              </button>
            </li>
          `
        )}
      </ul>
      <small>
        Add identities and their alternate names.<br>
        Example: Identity "Robert Allen" with alternates "Bob A", "Bob B", etc.
      </small>
    </section>
  `;
}

customElements.define("name-config-form", component(NameConfigForm, { useShadowDOM: false }));