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
    <div class="container">
      <header class="d-flex align-items-center justify-content-between">
        <h2>Jurisdiction Details</h2>
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
            <div class="responsive-grid">
              <p>
                <strong>Jurisdiction OCDID:</strong> ${data.id} <br />
                <strong>Website:</strong> 
                <a href="${data.url}" target="_blank">${data.url}</a> <br />
                <strong>Geoid:</strong> ${data.geoid || 'N/A'} <br />
                <strong>Population:</strong> ${data.population ? data.population.toLocaleString() : 'N/A'} <br />
                <strong>Classification:</strong> ${data.classification || 'N/A'} <br />
                <strong>Accurate As Of:</strong> ${data.accurate_asof ? new Date(data.accurate_asof).toLocaleDateString() : "N/A"} <br />
                <strong>Last Updated:</strong> ${data.last_updated ? new Date(data.last_updated).toLocaleDateString() : "N/A"} <br />
              </p>
              <h4>Term Information</h4>
              ${data.term && data.term.length > 0
                ? html`
                    <ul>
                      ${data.term.map(
                        term => html`
                          <li>
                            <strong>Duration:</strong> ${term.duration} years <br />
                            <strong>Description:</strong> ${term.term_description} <br />
                            <strong>Number of Positions:</strong> ${term.number_of_positions} <br />
                            <strong>Term Limits:</strong> ${term.term_limits} <br />
                            <strong>Last Known Term End Date:</strong> ${term.last_known_term_end_date || 'N/A'}
                          </li>
                        `
                      )}
                    </ul>
                  `
                : html`<p>No term information available.</p>`}
              <h4>Sourcing</h4>
              ${data.sourcing && data.sourcing.length > 0
                ? html`
                    <ul>
                      ${data.sourcing.map(
                        source => html`
                          <li>
                            <strong>Field:</strong> ${source.field} <br />
                            <strong>Source Name:</strong> ${source.source_name || 'N/A'} <br />
                            <strong>Source URL:</strong> 
                            <a href="${source.source_url}" target="_blank">${source.source_url}</a> <br />
                            <strong>Source Type:</strong> ${source.source_type || 'N/A'}
                          </li>
                        `
                      )}
                    </ul>
                  `
                : html`<p>No sourcing information available.</p>`}
              <h4>Metadata</h4>
              ${data.metadata && data.metadata.urls && data.metadata.urls.length > 0
                ? html`
                    <ul>
                      ${data.metadata.urls.map(
                        url => html`
                          <li>
                            <a href="${url}" target="_blank">${url}</a>
                          </li>
                        `
                      )}
                    </ul>
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