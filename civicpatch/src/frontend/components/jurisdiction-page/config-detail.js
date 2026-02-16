import { component, useState } from "haunted";
import { html } from "lit-html";


const DummyConfig = {
  source_urls: [
    "https://www.austintexas.gov/department/city-council/council-members",
    "https://www.austintexas.gov/department/mayor-kirk-watson"
  ],
  identities: [],
  offices: [
    {
      name: "Mayor",
      division_ocdid: "ocd-division/country:us/state:tx/place:austin"
    },
    {
      name: "Council Member",
      division_ocdid: "ocd-division/country:us/state:tx/place:austin/council_district:1"
    },
    {
      name: "Council Member",
      division_ocdid: "ocd-division/country:us/state:tx/place:austin/council_district:2"
    }
  ]
};

/* Should display the config details for a jurisdiction, 
and allow users to edit and save the config. */
function ConfigDetail({ config = DummyConfig, onSave }) {
  const [isEditMode, setEditMode] = useState(false);
  const [formData, setFormData] = useState(config);

  const toggleEditMode = () => {
    setEditMode(!isEditMode);
  };

  const handleInputChange = (field, value) => {
    setFormData({ ...formData, [field]: value });
  };

  const handleArrayChange = (field, index, key, value) => {
    const updatedArray = [...formData[field]];
    updatedArray[index] = { ...updatedArray[index], [key]: value };
    setFormData({ ...formData, [field]: updatedArray });
  };

  const handleArrayAdd = (field, defaultValue) => {
    const updatedArray = [...(formData[field] || []), defaultValue];
    setFormData({ ...formData, [field]: updatedArray });
  };

  const handleArrayRemove = (field, index) => {
    const updatedArray = formData[field].filter((_, i) => i !== index);
    setFormData({ ...formData, [field]: updatedArray });
  };

  const handleSave = () => {
    if (onSave) {
      onSave(formData);
    }
    setEditMode(false);
  };

  return html`
    <article>
      <header class="d-flex align-items-center justify-content-between">
        <h2>Config Details</h2>
        <button 
          @click=${toggleEditMode} 
          class="contrast outline"
          title="${isEditMode ? 'Switch to View Mode' : 'Switch to Edit Mode'}"
        >
          <i class="fa-solid ${isEditMode ? 'fa-eye' : 'fa-pen'}"></i>
          ${isEditMode ? 'View' : 'Edit'}
        </button>
      </header>


      ${isEditMode
        ? html`
            <form @submit=${e => { e.preventDefault(); handleSave(); }}>
              <h3>Source URLs</h3>
              ${formData.source_urls.map((url, index) => html`
                <fieldset role="group">
                  <input
                    type="url"
                    .value=${url}
                    @input=${e => handleArrayChange('source_urls', index, null, e.target.value)}
                  />
                  <button
                    type="button"
                    class="secondary outline"
                    @click=${() => handleArrayRemove('source_urls', index)}
                  >
                    Remove
                  </button>
                </fieldset>
              `)}
              <button
                type="button"
                class="secondary"
                @click=${() => handleArrayAdd('source_urls', '')}
              >
                + Add URL
              </button>

              <h3>Identities</h3>
              ${formData.identities.map((identity, index) => html`
                <fieldset role="group">
                  <input
                    type="text"
                    .value=${identity}
                    @input=${e => handleArrayChange('identities', index, null, e.target.value)}
                  />
                  <button
                    type="button"
                    class="secondary outline"
                    @click=${() => handleArrayRemove('identities', index)}
                  >
                    Remove
                  </button>
                </fieldset>
              `)}
              <button
                type="button"
                class="secondary"
                @click=${() => handleArrayAdd('identities', '')}
              >
                + Add Identity
              </button>

              <h3>Offices</h3>
              ${formData.offices.map((office, index) => html`
                <fieldset role="group">
                  <label>
                    <strong>Name:</strong>
                    <input
                      type="text"
                      .value=${office.name}
                      @input=${e => handleArrayChange('offices', index, 'name', e.target.value)}
                    />
                  </label>
                  <label>
                    <strong>Division OCDID:</strong>
                    <input
                      type="text"
                      .value=${office.division_ocdid}
                      @input=${e => handleArrayChange('offices', index, 'division_ocdid', e.target.value)}
                    />
                  </label>
                  <button
                    type="button"
                    @click=${() => handleArrayRemove('offices', index)}
                  >
                    Remove Office
                  </button>
                </fieldset>
              `)}
              <button
                type="button"
                class="secondary"
                @click=${() => handleArrayAdd('offices', { name: '', division_ocdid: '' })}
              >
                + Add Office
              </button>

              <button type="submit" class="primary">Save</button>
            </form>
          `
        : html`
            <h3>Source URLs</h3>
            <ul>
              ${config.source_urls.map(url => html`<li>${url}</li>`)}
            </ul>

            <h3>Identities</h3>
            <ul>
              ${config.identities.map(identity => html`<li>${identity}</li>`)}
            </ul>

            <h3>Offices</h3>
            <ul>
              ${config.offices.map(office => html`
                <li>
                  <strong>${office.name}</strong><br/>
                  Division OCDID: ${office.division_ocdid}
                </li>
              `)}
            </ul>
          `}
    </article>
  `;
}

customElements.define('civ-config-detail', component(ConfigDetail, {
  useShadowDOM: false,
  observedAttributes: ['config']
}));