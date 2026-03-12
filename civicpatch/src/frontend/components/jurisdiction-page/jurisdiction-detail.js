import { html } from 'lit-html';
import { component, useState } from 'haunted';

function JurisdictionDetail({ data, onSave }) {
  const [isEditMode, setEditMode] = useState(false);
  const [formData, setFormData] = useState(data);

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
    <div class="container" style="font-family: var(--pico-font-family-monospace)">
      <header class="d-flex align-items-center justify-content-between">
        <h3>Jurisdiction Details</h3>
        <button 
          @click=${toggleEditMode} 
          class="contrast outline"
          style="margin-bottom: 1rem;"
          title="${isEditMode ? 'Switch to View Mode' : 'Switch to Edit Mode'}"
        >
          <i class="fa-solid ${isEditMode ? 'fa-eye' : 'fa-pen'}"></i>
          ${isEditMode ? 'View' : 'Edit'}
        </button>
      </header>

      ${isEditMode
        ? html`
            <form @submit=${e => { e.preventDefault(); handleSave(); }} class="responsive-grid">
              <label>
                <strong>Jurisdiction OCDID:</strong>
                <input type="text" .value=${formData.id || ''} readonly />
              </label>
              <label>
                <strong>Website:</strong>
                <input type="url" .value=${formData.url || ''} @input=${e => handleInputChange('url', e.target.value)} />
              </label>
              <label>
                <strong>Geoid:</strong>
                <input type="text" .value=${formData.geoid || ''} @input=${e => handleInputChange('geoid', e.target.value)} />
              </label>
              <label>
                <strong>Population:</strong>
                <input type="number" .value=${formData.population || ''} @input=${e => handleInputChange('population', e.target.value)} />
              </label>
              <label>
                <strong>Classification:</strong>
                <input type="text" .value=${formData.classification || ''} @input=${e => handleInputChange('classification', e.target.value)} />
              </label>
              <label>
                <strong>Accurate As Of:</strong>
                <input type="date" .value=${formData.accurate_asof ? new Date(formData.accurate_asof).toISOString().split('T')[0] : ''} @input=${e => handleInputChange('accurate_asof', e.target.value)} />
              </label>
              <label>
                <strong>Last Updated:</strong>
                <input type="date" .value=${formData.last_updated ? new Date(formData.last_updated).toISOString().split('T')[0] : ''} @input=${e => handleInputChange('last_updated', e.target.value)} />
              </label>

              <h4>Term Information</h4>
              ${formData?.term?.map((term, index) => html`
                <div class="term-item">
                  <label>
                    <strong>Duration:</strong>
                    <input type="number" .value=${term.duration || ''} @input=${e => handleArrayChange('term', index, 'duration', e.target.value)} />
                  </label>
                  <label>
                    <strong>Description:</strong>
                    <textarea @input=${e => handleArrayChange('term', index, 'term_description', e.target.value)}>${term.term_description || ''}</textarea>
                  </label>
                  <label>
                    <strong>Number of Positions:</strong>
                    <input type="number" .value=${term.number_of_positions || ''} @input=${e => handleArrayChange('term', index, 'number_of_positions', e.target.value)} />
                  </label>
                  <label>
                    <strong>Term Limits:</strong>
                    <input type="text" .value=${term.term_limits || ''} @input=${e => handleArrayChange('term', index, 'term_limits', e.target.value)} />
                  </label>
                  <label>
                    <strong>Last Known Term End Date:</strong>
                    <input type="date" .value=${term.last_known_term_end_date || ''} @input=${e => handleArrayChange('term', index, 'last_known_term_end_date', e.target.value)} />
                  </label>
                  <button type="button" class="secondary" @click=${() => handleArrayRemove('term', index)}>Remove Term</button>
                </div>
              `)}
              <button 
                type="button" 
                class="secondary" 
                @click=${() => handleArrayAdd('term', { duration: '', term_description: '', number_of_positions: '', term_limits: '', last_known_term_end_date: '' })}>+ Add Term</button>

              <h4>Sourcing</h4>
              ${formData?.sourcing?.map((source, index) => html`
                <div class="sourcing-item">
                  <label>
                    <strong>Field:</strong>
                    <input type="text" .value=${source.field || ''} @input=${e => handleArrayChange('sourcing', index, 'field', e.target.value)} />
                  </label>
                  <label>
                    <strong>Source Name:</strong>
                    <input type="text" .value=${source.source_name || ''} @input=${e => handleArrayChange('sourcing', index, 'source_name', e.target.value)} />
                  </label>
                  <label>
                    <strong>Source URL:</strong>
                    <input type="url" .value=${source.source_url || ''} @input=${e => handleArrayChange('sourcing', index, 'source_url', e.target.value)} />
                  </label>
                  <label>
                    <strong>Source Type:</strong>
                    <input type="text" .value=${source.source_type || ''} @input=${e => handleArrayChange('sourcing', index, 'source_type', e.target.value)} />
                  </label>
                  <button type="button" class="secondary" @click=${() => handleArrayRemove('sourcing', index)}>Remove Source</button>
                </div>
              `)}
              <button type="button" class="secondary" @click=${() => handleArrayAdd('sourcing', { field: '', source_name: '', source_url: '', source_type: '' })}>+ Add Source</button>

              <h4>Metadata</h4>
              ${formData?.metadata?.urls?.map((url, index) => html`
                <div class="metadata-item">
                  <label>
                    <strong>URL:</strong>
                    <input type="url" .value=${url || ''} @input=${e => handleArrayChange('metadata', index, 'urls', e.target.value)} />
                  </label>
                  <button type="button" class="secondary" @click=${() => handleArrayRemove('metadata', index)}>Remove URL</button>
                </div>
              `)}
              <button type="button" class="secondary" @click=${() => handleArrayAdd('metadata', '')}>+ Add URL</button>

              <button type="submit" class="primary">Save</button>
            </form>
          `
        : html`
              <dl class="details-dl">
                <dt>Jurisdiction OCDID:</dt>
                <dd>${data.id}</dd>
                <dt>Website:</dt>
                <dd>
                  <a href="${data.url}" target="_blank">${data.url}</a>
                </dd>
                <dt>Geoid:</dt>
                <dd>${data.geoid || 'N/A'}</dd>
                <dt>Population:</dt>
                <dd>${data.population ? data.population.toLocaleString() : 'N/A'}</dd>
                <dt>Classification:</dt>
                <dd>${data.classification || 'N/A'}</dd>
                <dt>Accurate As Of:</dt>
                <dd>${data.accurate_asof ? new Date(data.accurate_asof).toLocaleDateString() : "N/A"}</dd>
                <dt>Last Updated:</dt>
                <dd>${data.last_updated ? new Date(data.last_updated).toLocaleDateString() : "N/A"}</dd>
              </dl>

              <h4>Term Information</h4>
              ${data.term && data.term.length > 0
                ? html`
                    <dl class="details-dl">
                      ${data.term.map(
                        term => html`
                          <dt>Duration:</dt>
                          <dd>${term.duration} years</dd>
                          <dt>Description:</dt>
                          <dd>${term.term_description}</dd>
                          <dt>Number of Positions:</dt>
                          <dd>${term.number_of_positions}</dd>
                          <dt>Term Limits:</dt>
                          <dd>${term.term_limits}</dd>
                          <dt>Last Known Term End Date:</dt>
                          <dd>${term.last_known_term_end_date || 'N/A'}</dd>
                        `
                      )}
                    </dl>
                  `
                : html`<p>No term information available.</p>`}

              <h4>Sourcing</h4>
              ${data.sourcing && data.sourcing.length > 0
                ? html`
                    <dl class="details-dl">
                      ${data.sourcing.map(
                        source => html`
                          <dt>Field:</dt>
                          <dd>${source.field}</dd>
                          <dt>Source Name:</dt>
                          <dd>${source.source_name || 'N/A'}</dd>
                          <dt>Source URL:</dt>
                          <dd>
                            <a href="${source.source_url}" target="_blank">${source.source_url}</a>
                          </dd>
                          <dt>Source Type:</dt>
                          <dd>${source.source_type || 'N/A'}</dd>
                        `
                      )}
                    </dl>
                  `
                : html`<p>No sourcing information available.</p>`}

              <h4>Metadata</h4>
              ${data.metadata && data.metadata.urls && data.metadata.urls.length > 0
                ? html`
                    <dl class="details-dl">
                      ${data.metadata.urls.map(
                        url => html`
                          <dt>URL:</dt>
                          <dd>
                            <a href="${url}" target="_blank">${url}</a>
                          </dd>
                        `
                      )}
                    </dl>
                  `
                : html`<p>No metadata URLs available.</p>`}
            </div>
          `}
  `;
}

customElements.define(
  "civ-jurisdiction-detail",
  component(JurisdictionDetail, {
    useShadowDOM: false,
    observedAttributes: ["data"]
  })
);