import { component } from 'haunted';
import { html } from 'lit-html';

function PeopleActionButtons({
  onAdd,
  onMerge,
  onBulkDelete,
  onReset,
  onSubmit,
  selectedPeople,
  dirty,
  isLoading,
  notice,
  error,
}) {
  return html`
    <div style="margin-bottom: 1rem; min-height: 2.5em; display: flex; align-items: center;">
      <button @click=${onAdd} style="margin-right: 1rem;" class="secondary">
        Add
      </button>
      <button 
        @click=${onMerge} 
        style="margin-right: 1rem;" 
        ?disabled=${selectedPeople.length < 2}
        class="secondary"
      >
        Merge (${selectedPeople.length})
      </button>
      <button 
        @click=${onBulkDelete} 
        style="margin-right: 1rem;"
        ?disabled=${selectedPeople.length === 0}
        class="secondary"
      >
        Delete (${selectedPeople.length})
      </button>
      <button
        @click=${onReset}
        style="margin-left:auto; margin-right: 1rem;"
        ?disabled=${dirty === false}
        class="secondary"
      >
        Reset Form
      </button>
      <button
        @click=${onSubmit}
        style="margin-right: 0;"
        ?disabled=${dirty === false}
        class="primary"
      >
        Submit
      </button>
      ${isLoading ? html`
        <div style="margin-bottom:1rem; padding:0.75em; background:#e0e0ff; border-radius:6px; color:#0000b3;">
          Submitting changes...
        </div>
      ` : ""}
      ${notice ? html`
        <div style="margin-bottom:1rem; padding:0.75em; background:#e0ffe0; border-radius:6px; color:#155724;">
          ${notice}
        </div>
      ` : ""}
      ${error ? html`
        <div style="margin-bottom:1rem; padding:0.75em; background:#ffe0e0; border-radius:6px; color:#721c24;">
          ${error}
        </div>
      ` : ""}
    </div>
  `;
}

customElements.define('civ-people-action-buttons', component(PeopleActionButtons, {
  useShadowDOM: false,
  observedAttributes: ['jurisdiction_ocdid']
}));
