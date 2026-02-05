import { html, component } from 'haunted';

function PersonCard({ person, selected = false, onSelect, onChange, onDelete, onReset }) {
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

  const imageUrl = person.image || person.cdn_image || null;

  return html`
    <style>
    .person-card input,
    .person-card button,
    .person-card select,
    .person-card textarea {
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
    </style>
    <article class="person-card" style="border-width:2px; border-style:solid; border-color:${selected ? 'var(--pico-form-element-active-border-color)' : 'var(--pico-form-element-border-color)'}; border-radius:8px; padding:1rem;">
      <header style="display: flex; align-items: center; gap: 1rem;">
        <input
          type="checkbox"
          .checked=${selected}
          @change=${handleCheckboxChange}
          aria-label="Select ${person.name}"
        />
        <div style="margin-left: auto; display: flex; gap: 0.5rem;">
          <button class="contrast outline" title="Delete person" @click=${handleDeleteClick}>Delete</button>
          <button 
          class="outline" 
          title="Reset changes" 
          @click=${handleReset}
          ?disabled=${!person._dirty}
          >Reset</button>
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
            .value=${person.office?.name || ''}
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
            @input=${e => {
              const newOffice = { ...(person.office || {}), division_ocdid: e.target.value };
              if (onChange) onChange('office', newOffice);
            }}
            placeholder="Division"
            style="width: 100%; min-height: 2.5em; resize: vertical;"
            rows="2"
          >${person.office?.division_ocdid || ''}</textarea>
        </div>
        <label>Term</label>
        <div style="display: flex; gap: 0.5rem;">
          <input
            type="date"
            .value=${person.start_date || ''}
            @input=${e => handleFieldChange('start_date', e.target.value)}
            placeholder="Start"
          />
          <input
            type="date"
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
                type="tel"
                .value=${phone}
                @input=${e => handleArrayChange('phones', idx, e.target.value)}
                placeholder="(555) 123-4567"
              />
              <button
                class="outline"
                @click=${() => handleArrayRemove('phones', idx)}
                title="Remove phone"
                type="button"
              >✕</button>
            </div>
          `)}
          <button class="outline" type="button" @click=${() => handleArrayAdd('phones')}>+ Add Phone</button>
        </div>
      </section>

      <section>
        <label>Email Addresses</label>
        <div>
          ${(person.emails || []).map((email, idx) => html`
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              <input
                type="email"
                .value=${email}
                @input=${e => handleArrayChange('emails', idx, e.target.value)}
                placeholder="email@example.com"
              />
              <button
                class="outline"
                @click=${() => handleArrayRemove('emails', idx)}
                title="Remove email"
                type="button"
              >✕</button>
            </div>
          `)}
          <button class="outline" type="button" @click=${() => handleArrayAdd('emails')}>+ Add Email</button>
        </div>
      </section>

      <section>
        <label>Links</label>
        <div>
          ${(person.urls || []).map((url, idx) => html`
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              <input
                type="url"
                .value=${url}
                @input=${e => handleArrayChange('urls', idx, e.target.value)}
                placeholder="https://example.com"
              />
              <button
                class="outline"
                @click=${() => handleArrayRemove('urls', idx)}
                title="Remove link"
                type="button"
              >✕</button>
            </div>
          `)}
          <button class="outline" type="button" @click=${() => handleArrayAdd('urls')}>+ Add Link</button>
        </div>
      </section>

      <section>
        <label>Source URLs</label>
        <div>
          ${(person.source_urls || []).map((url, idx) => html`
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              <input
                type="url"
                .value=${url}
                @input=${e => handleArrayChange('source_urls', idx, e.target.value)}
                placeholder="https://source.com"
              />
              <button
                class="outline"
                @click=${() => handleArrayRemove('source_urls', idx)}
                title="Remove source URL"
                type="button"
              >✕</button>
            </div>
          `)}
          <button class="outline" type="button" @click=${() => handleArrayAdd('source_urls')}>+ Add Source</button>
        </div>
      </section>

      ${person._dirty
        ? html`
            <section>
              <strong>Unsaved changes:</strong>
              <ul>
                ${person._changes.map(change => html`<li>${change}</li>`)}
              </ul>
            </section>
          `
        : ""} 
    </article>
  `;
}

customElements.define('person-card', component(PersonCard, { observedAttributes: ['person'], useShadowDOM: false }));