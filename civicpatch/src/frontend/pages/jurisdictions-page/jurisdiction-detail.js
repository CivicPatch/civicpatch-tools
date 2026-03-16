import { html } from 'lit-html';
import { component, useState } from 'haunted';

function JurisdictionDetail({ data, onSave }) {
  const [isEditMode, setIsEditMode] = useState(false);
  const [formData, setFormData] = useState(data);

  const toggleEditMode = () => setIsEditMode(!isEditMode);

  const handleInputChange = (field, value) => {
    setFormData({ ...formData, [field]: value });
  };

  const handleArrayChange = (field, index, key, value) => {
    const updated = [...formData[field]];
    updated[index] = { ...updated[index], [key]: value };
    setFormData({ ...formData, [field]: updated });
  };

  const handleArrayAdd = (field, defaultValue) => {
    setFormData({ ...formData, [field]: [...(formData[field] || []), defaultValue] });
  };

  const handleArrayRemove = (field, index) => {
    setFormData({ ...formData, [field]: formData[field].filter((_, i) => i !== index) });
  };

  const handleSave = () => {
    if (onSave) onSave(formData);
    setIsEditMode(false);
  };

  return html`
    <style>
      .jd-wrap {
        display: flex;
        flex-direction: column;
        gap: 1.75rem;
      }

      /* Section header row */
      .jd-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
      }
      .jd-header h3 {
        margin: 0;
        font-size: 1rem;
        font-weight: 700;
      }

      /* Section dividers */
      .jd-section {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
      }
      .jd-section-title {
        margin: 0;
        font-size: 0.8125rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--pico-muted-color);
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--pico-muted-border-color);
      }

      /* Empty state */
      .jd-empty {
        font-size: 0.875rem;
        color: var(--pico-muted-color);
        margin: 0;
      }

      /* Edit form */
      .jd-form {
        display: flex;
        flex-direction: column;
        gap: 1.5rem;
      }
      .jd-array-item {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        padding: 1rem;
        border: 1px solid var(--pico-muted-border-color);
        border-radius: var(--pico-border-radius);
        background: var(--pico-card-sectioning-background-color);
      }
      .jd-array-item button {
        align-self: flex-start;
        margin-top: 0.25rem;
      }

      /* Edit/View toggle button — small, unobtrusive */
      .btn-toggle {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        font-size: 0.8125rem;
        font-weight: 500;
        padding: 0.3rem 0.75rem;
        border-radius: var(--pico-border-radius);
        border: 1px solid var(--pico-muted-border-color);
        background: transparent;
        color: var(--pico-muted-color);
        cursor: pointer;
        transition: border-color 0.15s, color 0.15s;
        margin: 0;
      }
      .btn-toggle:hover {
        border-color: var(--pico-color);
        color: var(--pico-color);
      }
    </style>

    <div class="jd-wrap">
      <div class="jd-header">
        <h3>Jurisdiction Details</h3>
        <button class="btn-toggle" @click=${toggleEditMode}>
          <i class="fa-solid ${isEditMode ? 'fa-eye' : 'fa-pen'}"></i>
          ${isEditMode ? 'View' : 'Edit'}
        </button>
      </div>

      ${isEditMode ? html`
        <form class="jd-form" @submit=${e => { e.preventDefault(); handleSave(); }}>

          <div class="jd-section">
            <h4 class="jd-section-title">Core Fields</h4>
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
          </div>

          <div class="jd-section">
            <h4 class="jd-section-title">Term Information</h4>
            ${(formData?.term || []).map((term, index) => html`
              <div class="jd-array-item">
                <label><strong>Duration:</strong>
                  <input type="number" .value=${term.duration || ''} @input=${e => handleArrayChange('term', index, 'duration', e.target.value)} />
                </label>
                <label><strong>Description:</strong>
                  <textarea @input=${e => handleArrayChange('term', index, 'term_description', e.target.value)}>${term.term_description || ''}</textarea>
                </label>
                <label><strong>Number of Positions:</strong>
                  <input type="number" .value=${term.number_of_positions || ''} @input=${e => handleArrayChange('term', index, 'number_of_positions', e.target.value)} />
                </label>
                <label><strong>Term Limits:</strong>
                  <input type="text" .value=${term.term_limits || ''} @input=${e => handleArrayChange('term', index, 'term_limits', e.target.value)} />
                </label>
                <label><strong>Last Known Term End Date:</strong>
                  <input type="date" .value=${term.last_known_term_end_date || ''} @input=${e => handleArrayChange('term', index, 'last_known_term_end_date', e.target.value)} />
                </label>
                <button type="button" class="secondary outline" @click=${() => handleArrayRemove('term', index)}>Remove Term</button>
              </div>
            `)}
            <button type="button" class="secondary outline"
              @click=${() => handleArrayAdd('term', { duration: '', term_description: '', number_of_positions: '', term_limits: '', last_known_term_end_date: '' })}>
              + Add Term
            </button>
          </div>

          <div class="jd-section">
            <h4 class="jd-section-title">Sourcing</h4>
            ${(formData?.sourcing || []).map((source, index) => html`
              <div class="jd-array-item">
                <label><strong>Field:</strong>
                  <input type="text" .value=${source.field || ''} @input=${e => handleArrayChange('sourcing', index, 'field', e.target.value)} />
                </label>
                <label><strong>Source Name:</strong>
                  <input type="text" .value=${source.source_name || ''} @input=${e => handleArrayChange('sourcing', index, 'source_name', e.target.value)} />
                </label>
                <label><strong>Source URL:</strong>
                  <input type="url" .value=${source.source_url || ''} @input=${e => handleArrayChange('sourcing', index, 'source_url', e.target.value)} />
                </label>
                <label><strong>Source Type:</strong>
                  <input type="text" .value=${source.source_type || ''} @input=${e => handleArrayChange('sourcing', index, 'source_type', e.target.value)} />
                </label>
                <button type="button" class="secondary outline" @click=${() => handleArrayRemove('sourcing', index)}>Remove Source</button>
              </div>
            `)}
            <button type="button" class="secondary outline"
              @click=${() => handleArrayAdd('sourcing', { field: '', source_name: '', source_url: '', source_type: '' })}>
              + Add Source
            </button>
          </div>

          <div class="jd-section">
            <h4 class="jd-section-title">Metadata</h4>
            ${(formData?.metadata?.urls || []).map((url, index) => html`
              <div class="jd-array-item">
                <label><strong>URL:</strong>
                  <input type="url" .value=${url || ''} @input=${e => handleArrayChange('metadata', index, 'urls', e.target.value)} />
                </label>
                <button type="button" class="secondary outline" @click=${() => handleArrayRemove('metadata', index)}>Remove URL</button>
              </div>
            `)}
            <button type="button" class="secondary outline" @click=${() => handleArrayAdd('metadata', '')}>+ Add URL</button>
          </div>

          <button type="submit">Save Changes</button>
        </form>
      ` : html`
        <div class="jd-section">
          <h4 class="jd-section-title">Core Fields</h4>
          <dl class="details-dl">
            <dt>Jurisdiction OCDID:</dt><dd>${data.id}</dd>
            <dt>Website:</dt>
            <dd>${data.url ? html`<a href="${data.url}" target="_blank">${data.url}</a>` : 'N/A'}</dd>
            <dt>Geoid:</dt><dd>${data.geoid || 'N/A'}</dd>
            <dt>Population:</dt><dd>${data.population ? data.population.toLocaleString() : 'N/A'}</dd>
            <dt>Classification:</dt><dd>${data.classification || 'N/A'}</dd>
            <dt>Accurate As Of:</dt><dd>${data.accurate_asof ? new Date(data.accurate_asof).toLocaleDateString() : 'N/A'}</dd>
            <dt>Last Updated:</dt><dd>${data.last_updated ? new Date(data.last_updated).toLocaleDateString() : 'N/A'}</dd>
          </dl>
        </div>

        <div class="jd-section">
          <h4 class="jd-section-title">Term Information</h4>
          ${data.term && data.term.length > 0 ? html`
            <dl class="details-dl">
              ${data.term.map(term => html`
                <dt>Duration:</dt><dd>${term.duration} years</dd>
                <dt>Description:</dt><dd>${term.term_description}</dd>
                <dt>Positions:</dt><dd>${term.number_of_positions}</dd>
                <dt>Term Limits:</dt><dd>${term.term_limits}</dd>
                <dt>Last Term End:</dt><dd>${term.last_known_term_end_date || 'N/A'}</dd>
              `)}
            </dl>
          ` : html`<p class="jd-empty">No term information available.</p>`}
        </div>

        <div class="jd-section">
          <h4 class="jd-section-title">Sourcing</h4>
          ${data.sourcing && data.sourcing.length > 0 ? html`
            <dl class="details-dl">
              ${data.sourcing.map(source => html`
                <dt>Field:</dt><dd>${source.field}</dd>
                <dt>Source Name:</dt><dd>${source.source_name || 'N/A'}</dd>
                <dt>Source URL:</dt>
                <dd><a href="${source.source_url}" target="_blank">${source.source_url}</a></dd>
                <dt>Source Type:</dt><dd>${source.source_type || 'N/A'}</dd>
              `)}
            </dl>
          ` : html`<p class="jd-empty">No sourcing information available.</p>`}
        </div>

        <div class="jd-section">
          <h4 class="jd-section-title">Metadata</h4>
          ${data.metadata && data.metadata.urls && data.metadata.urls.length > 0 ? html`
            <dl class="details-dl">
              ${data.metadata.urls.map(url => html`
                <dt>URL:</dt>
                <dd><a href="${url}" target="_blank">${url}</a></dd>
              `)}
            </dl>
          ` : html`<p class="jd-empty">No metadata URLs available.</p>`}
        </div>
      `}
    </div>
  `;
}

customElements.define(
  "civ-jurisdiction-detail",
  component(JurisdictionDetail, {
    useShadowDOM: false,
    observedAttributes: ["data"]
  })
);