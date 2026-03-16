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
}) {
  return html`
    <div class="action-buttons">
      <button @click=${onAdd} class="secondary btn-sm">Add</button>
      <button @click=${onMerge} ?disabled=${selectedPeople.length < 2} class="secondary btn-sm">
        Merge (${selectedPeople.length})
      </button>
      <button @click=${onBulkDelete} ?disabled=${selectedPeople.length === 0} class="secondary btn-sm">
        Delete (${selectedPeople.length})
      </button>
      <button @click=${onReset} ?disabled=${dirty === false} class="secondary btn-sm action-buttons__reset">
        Reset
      </button>
      <button @click=${onSubmit} ?disabled=${dirty === false} class="btn-sm">
        Submit
      </button>
    </div>
  `;
}

customElements.define('civ-people-action-buttons', component(PeopleActionButtons, {
  useShadowDOM: false,
  observedAttributes: ['jurisdiction_ocdid']
}));
