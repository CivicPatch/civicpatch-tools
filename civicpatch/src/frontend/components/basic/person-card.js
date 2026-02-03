import { html, component, useState } from 'haunted';

function PersonCard({ person, selected = false, onSelect, onChange, onDelete }) {
  const [isSelected, setIsSelected] = useState(selected);
  const [editPerson, setEditPerson] = useState({ ...person });

  // Helper for array fields
  const handleArrayChange = (field, idx, value) => {
    const arr = [...(editPerson[field] || [])];
    arr[idx] = value;
    setEditPerson({ ...editPerson, [field]: arr });
    if (onChange) onChange({ ...editPerson, [field]: arr });
  };
  const handleArrayAdd = (field) => {
    const arr = [...(editPerson[field] || [])];
    arr.push('');
    setEditPerson({ ...editPerson, [field]: arr });
  };
  const handleArrayRemove = (field, idx) => {
    const arr = [...(editPerson[field] || [])];
    arr.splice(idx, 1);
    setEditPerson({ ...editPerson, [field]: arr });
    if (onChange) onChange({ ...editPerson, [field]: arr });
  };

  // Helper for single fields
  const handleFieldChange = (field, value) => {
    setEditPerson({ ...editPerson, [field]: value });
    if (onChange) onChange({ ...editPerson, [field]: value });
  };

  const handleCheckboxChange = (e) => {
    e.stopPropagation();
    setIsSelected(e.target.checked);
    if (onSelect) onSelect(e.target.checked);
  };

  const handleDeleteClick = (e) => {
    e.stopPropagation();
    if (onDelete) onDelete();
  };

  const imageUrl = editPerson.image || editPerson.cdn_image || null;

  return html`
    <style>
      .person-card {
        background: white;
        border: 2px solid ${isSelected ? '#0066cc' : '#e5e7eb'};
        border-radius: 8px;
        padding: 16px;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
      }
      .person-card:hover {
        border-color: ${isSelected ? '#0052a3' : '#cbd5e1'};
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
      }
      
      /* Header */
      .card-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid #f3f4f6;
      }
      .card-checkbox {
        width: 20px;
        height: 20px;
        cursor: pointer;
        margin: 0;
      }
      .card-avatar {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        object-fit: cover;
        background: #f3f4f6;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        flex-shrink: 0;
      }
      .card-name-input {
        flex: 1;
        font-size: 18px;
        font-weight: 600;
        border: 1px solid transparent;
        padding: 6px 10px;
        border-radius: 4px;
        background: transparent;
        transition: all 0.2s;
      }
      .card-name-input:hover {
        background: #f9fafb;
        border-color: #e5e7eb;
      }
      .card-name-input:focus {
        background: white;
        border-color: #0066cc;
        outline: none;
      }
      

      /* Form sections */
      .form-section {
        margin-bottom: 16px;
      }
      .form-section:last-child {
        margin-bottom: 0;
      }
      .section-label {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #6b7280;
        margin-bottom: 8px;
        display: block;
      }

      /* Office and dates grid */
      .office-grid {
        display: grid;
        grid-template-columns: 2fr 1fr 1fr;
        gap: 8px;
      }

      /* Input styling */
      input[type="text"],
      input[type="date"],
      input[type="tel"],
      input[type="email"],
      input[type="url"] {
        width: 100%;
        padding: 8px 12px;
        border: 1px solid #e5e7eb;
        border-radius: 4px;
        font-size: 14px;
        transition: all 0.2s;
        box-sizing: border-box;
      }
      input:hover {
        border-color: #cbd5e1;
      }
      input:focus {
        border-color: #0066cc;
        outline: none;
        box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.1);
      }
      input::placeholder {
        color: #9ca3af;
      }

      /* Array items (phones, emails, etc) */
      .array-items {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .array-item {
        display: flex;
        gap: 6px;
        align-items: stretch; /* Changed from center */
      }
      .array-item input {
        flex: 1;
      }
      .remove-btn {
        padding: 0 10px;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 4px;
        color: #6b7280;
        cursor: pointer;
        font-size: 16px;
        transition: all 0.2s;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        height: 34px; /* Match the input height (8px top + 8px bottom padding + ~18px line height) */
      } 
      .remove-btn:hover {
        background: #fee2e2;
        border-color: #fecaca;
        color: #ef4444;
      }
      .add-btn {
        padding: 8px 12px;
        background: white;
        border: 1px dashed #cbd5e1;
        border-radius: 4px;
        color: #6b7280;
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
        transition: all 0.2s;
        width: 100%;
        margin-top: 2px;
      }
      .add-btn:hover {
        background: #f9fafb;
        border-color: #0066cc;
        color: #0066cc;
      }
    </style>

    <article class="person-card" tabindex="0">
      <!-- Header with name and controls -->
      <div class="card-header">
        <!-- Split into two columns: checkbox on left, delete button on right -->
        <div class="card-header-left">
          <input
            type="checkbox"
            class="card-checkbox"
            .checked=${isSelected}
            @change=${handleCheckboxChange}
            aria-label="Select ${editPerson.name}"
          />
        </div>
        <div class="card-header-right" style="margin-left: auto; display: flex; align-items: center; gap: 8px;">
          
          <button class="delete-btn contrast outline" title="Delete person" @click=${handleDeleteClick}>Delete</button>
        </div>

      </div>

      <!-- Name input and avatar -->
      <div class="card-header">
        <div class="card-avatar">
          ${imageUrl
            ? html`<img src=${imageUrl} alt="Avatar of ${editPerson.name}" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover;" />`
            : html`${editPerson.name ? editPerson.name.charAt(0).toUpperCase() : '?'}`}
        </div>
        <input
          type="text"
          class="card-name-input"
          .value=${editPerson.name || ''}
          @input=${e => handleFieldChange('name', e.target.value)}
          placeholder="Full Name"
        />
      </div>

      <!-- Office and dates -->
      <div class="form-section">
        <span class="section-label">Office & Term</span>
        <div class="office-grid">
          <input
            type="text"
            value=${editPerson.office?.name || ''}
            @input=${e => {
              setEditPerson({
                ...editPerson,
                office: { ...(editPerson.office || {}), name: e.target.value }
              });
              if (onChange) onChange({
                ...editPerson,
                office: { ...(editPerson.office || {}), name: e.target.value }
              });
            }}
            placeholder="Office"
          />
          <input
            type="date"
            value=${editPerson.start_date || ''}
            @input=${e => handleFieldChange('start_date', e.target.value)}
            placeholder="Start"
          />
          <input
            type="date"
            value=${editPerson.end_date || ''}
            @input=${e => handleFieldChange('end_date', e.target.value)}
            placeholder="End"
          />
        </div>
      </div>

      <!-- Phones -->
      <div class="form-section">
        <span class="section-label">Phone Numbers</span>
        <div class="array-items">
          ${(editPerson.phones || []).map((phone, idx) => html`
            <div class="array-item">
              <input
                type="tel"
                value=${phone}
                @input=${e => handleArrayChange('phones', idx, e.target.value)}
                placeholder="(555) 123-4567"
              />
              <button
                class="remove-btn"
                @click=${() => handleArrayRemove('phones', idx)}
                title="Remove phone"
              >✕</button>
            </div>
          `)}
          <button class="add-btn" @click=${() => handleArrayAdd('phones')}>+ Add Phone</button>
        </div>
      </div>

      <!-- Emails -->
      <div class="form-section">
        <span class="section-label">Email Addresses</span>
        <div class="array-items">
          ${(editPerson.emails || []).map((email, idx) => html`
            <div class="array-item">
              <input
                type="email"
                value=${email}
                @input=${e => handleArrayChange('emails', idx, e.target.value)}
                placeholder="email@example.com"
              />
              <button
                class="remove-btn"
                @click=${() => handleArrayRemove('emails', idx)}
                title="Remove email"
              >✕</button>
            </div>
          `)}
          <button class="add-btn" @click=${() => handleArrayAdd('emails')}>+ Add Email</button>
        </div>
      </div>

      <!-- Links -->
      <div class="form-section">
        <span class="section-label">Links</span>
        <div class="array-items">
          ${(editPerson.urls || []).map((url, idx) => html`
            <div class="array-item">
              <input
                type="url"
                value=${url}
                @input=${e => handleArrayChange('urls', idx, e.target.value)}
                placeholder="https://example.com"
              />
              <button
                class="remove-btn"
                @click=${() => handleArrayRemove('urls', idx)}
                title="Remove link"
              >✕</button>
            </div>
          `)}
          <button class="add-btn" @click=${() => handleArrayAdd('urls')}>+ Add Link</button>
        </div>
      </div>

      <!-- Source URLs -->
      <div class="form-section">
        <span class="section-label">Source URLs</span>
        <div class="array-items">
          ${(editPerson.source_urls || []).map((url, idx) => html`
            <div class="array-item">
              <input
                type="url"
                value=${url}
                @input=${e => handleArrayChange('source_urls', idx, e.target.value)}
                placeholder="https://source.com"
              />
              <button
                class="remove-btn"
                @click=${() => handleArrayRemove('source_urls', idx)}
                title="Remove source URL"
              >✕</button>
            </div>
          `)}
          <button class="add-btn" @click=${() => handleArrayAdd('source_urls')}>+ Add Source</button>
        </div>
      </div>
    </article>
  `;
}

customElements.define('person-card', component(PersonCard, { observedAttributes: ['person'], useShadowDOM: false }));