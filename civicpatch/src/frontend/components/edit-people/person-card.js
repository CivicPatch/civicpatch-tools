import { html, component } from 'haunted';

function PersonCard({ person, onSelect, onChange, onDelete, onReset }) {
  // Remove useState for isSelected and editPerson

  // Helper for array fields
  const handleArrayChange = (field, idx, value) => {
    const arr = [...(person[field] || [])];
    arr[idx] = value;
    if (onChange) onChange(field, arr);
  };

  const handleArrayAdd = (field) => {
    const arr = [...(person[field] || [])];
    arr.push('');
    if (onChange) onChange(field, arr);
  };

  const handleArrayRemove = (field, idx) => {
    const arr = [...(person[field] || [])];
    arr.splice(idx, 1);
    if (onChange) onChange(field, arr);
  };

  // Helper for single fields
  const handleFieldChange = (field, value) => {
    if (onChange) onChange(field, value);
  };

  const handleCheckboxChange = (e) => {
    e.stopPropagation();
    if (onSelect) onSelect(e.target.checked);
  };

  const handleDeleteClick = (e) => {
    e.stopPropagation();
    if (onDelete) onDelete();
  };

  const handleReset = () => {
    if (onReset) onReset();
  };

    // Inside the person-card or where the name field is rendered
  const isNameChanged = person._changes?.includes('name');
  const isOfficeChanged = person._changes?.includes('office');
  const isStartDateChanged = person._changes?.includes('start_date');
  const isEndDateChanged = person._changes?.includes('end_date');
  const isPhonesChanged = person._changes?.includes('phones');
  const isEmailsChanged = person._changes?.includes('emails');
  const isUrlsChanged = person._changes?.includes('urls');
  const isSourceUrlsChanged = person._changes?.includes('source_urls');

  const imageUrl = person.image || person.cdn_image || null;

  return html`
    <style>
    .person-card header [type="checkbox"] {
      --pico-form-element-border-color: rgb(var(--pico-color));
    }
    .person-card section input,
    .person-card section button,
    .person-card section select,
    .person-card section textarea {
      --pico-form-element-spacing-vertical: 0.25rem;
      --pico-form-element-spacing-horizontal: 0.5rem;
      font-size: 0.75rem;
    }
    .person-card-avatar-row {
      display: flex;
      justify-content: center;
      align-items: center;
      margin-bottom: 1rem;
    }
    .person-card-avatar-row figure {
      margin: 0;
      display: flex;
      justify-content: center;
      align-items: center;
      width: 100%;
    }
    .person-card-avatar-row img,
    .person-card-avatar-row span {
      width: 72px;
      height: 72px;
      border-radius: 50%;
      object-fit: cover;
      font-size: 32px;
      background: var(--muted-bg, #e5e7eb);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .person-card {
      position: relative;
    }
    .person-card.selected::after {
      content: ''; 
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(var(--pico-primary-hover), 0.5);
      pointer-events: none; /* Ensure it doesn't block interactions */
    }
    .person-card.deleted::after {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(var(--catppuccin-red), 0.2);
      pointer-events: none; /* Ensure it doesn't block interactions */
    }

    .field-added {
      background: rgba(var(--catppuccin-green), 0.3); /* Green color filter */
    }

    </style>
    <article 
      class="person-card 
        ${person._selected ? 'selected' : ''}
        ${person._deleted ? 'deleted' : ''} 
      "  
      style="padding:1rem;"
      .onSelect=${() => toggleSelect(person._tempKey)}
    >
      <header style="display: flex; align-items: center; gap: 1rem;">
        <input
          type="checkbox"
          .checked=${person._selected}
          @change=${handleCheckboxChange}
          aria-label="Select ${person.name}" 
          ?disabled=${person._deleted}
          />
        <div style="margin-left: auto; display: flex; gap: 0.5rem;">
          <button 
            class="contrast" 
            title="Delete person" 
            @click=${handleDeleteClick}
            ?disabled=${person._deleted}
          >
            Delete
          </button>
          <button 
            title="Reset changes" 
            @click=${handleReset}
            ?disabled=${(!person._changes || person._changes.length === 0) && !person._deleted}
          >
            Reset
          </button>
        </div>
      </header>

      <div class="person-card-avatar-row">
        <figure>
          ${imageUrl
            ? html`<img src=${imageUrl} alt="Avatar of ${person.name}" />`
            : html`<span>${person.name ? person.name.charAt(0).toUpperCase() : '?'}</span>`
          }
        </figure>
      </div>

      <section style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
        <input
          type="text"
          class=${isNameChanged ? 'field-added' : ''}
          @keydown=${e => e.stopPropagation()}
          .value=${person.name || ''}
          @input=${e => handleFieldChange('name', e.target.value)}
          placeholder="Full Name"
          style="flex: 1;"
        />
      </section>

      <section>
        <label>Office</label>
        <div style="margin-bottom: 0.5rem;">
          <input
            type="text"
            class=${isOfficeChanged ? 'field-added' : ''}
            .value=${person.office?.name || ''}
            @keydown=${e => e.stopPropagation()}
            @input=${e => {
              const newOffice = { ...(person.office || {}), name: e.target.value };
              if (onChange) onChange('office', newOffice);
            }}
            placeholder="Office"
            style="width: 100%;"
          />
        </div>
        <div style="margin-bottom: 0.5rem;">
          <textarea
            class=${isOfficeChanged ? 'field-added' : ''}
            @input=${e => {
              const newOffice = { ...(person.office || {}), division_ocdid: e.target.value };
              if (onChange) onChange('office', newOffice);
            }}
            @keydown=${e => e.stopPropagation()}
            placeholder="Division"
            style="width: 100%; min-height: 2.5em; resize: vertical;"
            rows="2"
          >${person.office?.division_ocdid || ''}</textarea>
        </div>
        <label>Term</label>
        <div style="display: flex; gap: 0.5rem;">
          <input
            type="date"
            class=${(isStartDateChanged ? 'field-added' : '')}
            @keydown=${e => e.stopPropagation()}
            .value=${person.start_date || ''}
            @input=${e => handleFieldChange('start_date', e.target.value)}
            placeholder="Start"
          />
          <input
            type="date"
            class=${isEndDateChanged ? 'field-added' : ''}
            @keydown=${e => e.stopPropagation()}
            .value=${person.end_date || ''}
            @input=${e => handleFieldChange('end_date', e.target.value)}
            placeholder="End"
          />
        </div>
      </section>

      <section>
        <label>Phone Numbers</label>
        <div>
          ${(person.phones || []).map((phone, idx) => html`
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              <input
                class=${isPhonesChanged ? 'field-added' : ''}
                type="tel"
                @keydown=${e => e.stopPropagation()}
                .value=${phone}
                @input=${e => handleArrayChange('phones', idx, e.target.value)}
                placeholder="(555) 123-4567"
              />
              <button
                @click=${() => handleArrayRemove('phones', idx)}
                title="Remove phone"
                type="button"
              >✕</button>
            </div>
          `)}
          <button type="button" @click=${() => handleArrayAdd('phones')}>+ Add Phone</button>
        </div>
      </section>

      <section>
        <label>Email Addresses</label>
        <div>
          ${(person.emails || []).map((email, idx) => html`
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              <input
                class=${isEmailsChanged ? 'field-added' : ''}
                type="email"
                @keydown=${e => e.stopPropagation()}
                .value=${email}
                @input=${e => handleArrayChange('emails', idx, e.target.value)}
                placeholder="email@example.com"
              />
              <button
                @click=${() => handleArrayRemove('emails', idx)}
                title="Remove email"
                type="button"
              >✕</button>
            </div>
          `)}
          <button type="button" @click=${() => handleArrayAdd('emails')}>+ Add Email</button>
        </div>
      </section>

      <section>
        <label>Links</label>
        <div>
          ${(person.urls || []).map((url, idx) => html`
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              <input
                class=${isUrlsChanged ? 'field-added' : ''}
                type="url"
                .value=${url}
                @keydown=${e => e.stopPropagation()}
                @input=${e => handleArrayChange('urls', idx, e.target.value)}
                placeholder="https://example.com"
              />
              <button
                @click=${() => handleArrayRemove('urls', idx)}
                title="Remove link"
                type="button"
              >✕</button>
            </div>
          `)}
          <button type="button" @click=${() => handleArrayAdd('urls')}>+ Add Link</button>
        </div>
      </section>

      <section>
        <label>Source URLs</label>
        <div>
          ${(person.source_urls || []).map((url, idx) => html`
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              <input
                class=${isSourceUrlsChanged ? 'field-added' : ''}
                type="url"
                @keydown=${e => e.stopPropagation()}
                .value=${url}
                @input=${e => handleArrayChange('source_urls', idx, e.target.value)}
                placeholder="https://source.com"
              />
              <button
                @click=${() => handleArrayRemove('source_urls', idx)}
                title="Remove source URL"
                type="button"
              >✕</button>
            </div>
          `)}
          <button type="button" @click=${() => handleArrayAdd('source_urls')}>+ Add Source</button>
        </div>
      </section>
      ${person._changes && person._changes.length > 0 ? html`
        <footer>
          <strong>Unsaved changes:</strong>
          <ul>
            ${person._changes?.map(change => html`<li>${change}</li>`)}
          </ul>
        </footer>
      ` : ''}
    </article>
  `;
}

customElements.define('person-card', component(PersonCard, { observedAttributes: ['person'], useShadowDOM: false }));