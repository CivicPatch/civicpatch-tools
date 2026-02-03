import { html, component, useEffect, useState } from 'haunted';
import './basic/person-card.js';

// Helper to generate a random key
function genKey() {
  return Math.random().toString(36).substr(2, 9) + Date.now();
}

function EditablePeopleList({ jurisdiction_ocdid }) {
  const [people, setPeople] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState([]);
  
  useEffect(() => {
    if (!jurisdiction_ocdid) return;
    setLoading(true);
    fetch(`/api/api_proxy/people?jurisdiction_ocdid=${encodeURIComponent(jurisdiction_ocdid)}`)
      .then(r => r.json())
      .then(data => {
        // Assign a temporary key to each person
        const withKeys = (data.data || []).map(person => ({
          ...person,
          _tempKey: genKey(),
        }));
        setPeople(withKeys);
        setLoading(false);
      })
      .catch(e => {
        setError(e);
        setLoading(false);
      });
  }, [jurisdiction_ocdid]);

  function toggleSelect(key) {
    console.log("toggling", key);
    setSelected(sel =>
      sel.includes(key) ? sel.filter(x => x !== key) : [...sel, key]
    );
  }

  function handleAddPerson() {
    const name = prompt('Enter name for new person:');
    if (!name) return;
    // Replace with your actual API call
    fetch('/api/api_proxy/people', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, jurisdiction_ocdid }),
    })
      .then(r => r.json())
      .then(newPerson => setPeople(p => [...p, { ...newPerson, _tempKey: genKey() }]))
      .catch(e => alert('Failed to add person'));
  }

  function handleDelete(key) {
    if (!confirm('Delete this person?')) return;
    setPeople(p => p.filter(person => person._tempKey !== key));
    // Optionally, call your API here if you can identify the person another way
  }

  function handleMerge() {
    const selectedPeople = getSelectedPeople();
    alert(`Merging people:\n${selectedPeople.map(p => p.name).join(', ')}`);
    setSelected([]);
  }

  // Example usage in handleBulkDelete:
  function handleBulkDelete() {
    if (!confirm(`Delete ${selected.length} people?`)) return;
    setPeople(p => p.filter(person => !selected.includes(person._tempKey)));
    setSelected([]);
  }

  function selectActions() {
    return html`
      <div>
        <button @click=${handleMerge}>Merge (${selected.length})</button>
        <button @click=${handleBulkDelete}>Delete (${selected.length})</button>
      </div>
    `;
  }

  if (loading) return html`<p>Loading people...</p>`;
  if (error) return html`<p>Error loading people.</p>`;

  return html`
    
    <div style="margin-bottom: 1rem;">
      <!-- <button @click=${handleAddPerson}>Add Person</button> -->
      ${selected.length > 1
        ? html`<button @click=${handleMerge} style="margin-left:1rem;">Merge (${selected.length})</button>`
        : ''}
    </div>
    <div
      class="grid"
      style="
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
        gap: 1rem;
        align-items: stretch;
        width: 100%;
      "
    >
      ${people.map(
        person => html`
          <person-card
            .person=${person}
            .selected=${selected.includes(person._tempKey)}
            .onSelect=${() => toggleSelect(person._tempKey)}
            .onDelete=${() => handleDelete(person._tempKey)}
          ></person-card>
        `
      )}
    </div>
  `;
}

customElements.define(
  'civ-editable-people-list', 
  component(
    EditablePeopleList, { 
      useShadowDOM: false, observedAttributes: ['jurisdiction_ocdid'] 
    }
  )
);
