import { html, component, useEffect, useState } from 'haunted';
import './basic/person-card.js';
import yaml from 'js-yaml';

// Helper to generate a random key
function genKey() {
  return Math.random().toString(36).substr(2, 9) + Date.now();
}

const TRACKED_FIELDS = [
  "name", "other_names", "phones", "emails", "urls", "start_date", "end_date", "office", "source_urls"
];

function EditablePeopleList({ jurisdiction_ocdid, people = [] }) {
  // Assign _tempKey to people if not present
  const [localPeople, setPeople] = useState(
    people.map(person => ({
      ...person,
      _tempKey: person._tempKey || genKey(),
    }))
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState([]);
  const [openPullRequests, setOpenPullRequests] = useState([]);
  const [selectedOpenPullRequest, setSelectedOpenPullRequest] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [originalPeople, setOriginalPeople] = useState([]);
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    if (!jurisdiction_ocdid) return;
    setLoading(true);
    fetch(`/api/api_proxy/jobs/people/pull_request/open?jurisdiction_ocdid=${encodeURIComponent(jurisdiction_ocdid)}`)
      .then(r => r.json())
      .then(data => {
        setOpenPullRequests(data.data || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedOpenPullRequest) {
      // Use default people
      assignPeople(people)
    }
    else {
      getSelectedOpenPullRequestData(selectedOpenPullRequest);
    }
  }, [selectedOpenPullRequest])
  
  
  function toggleSelect(key) {
    setSelected(sel =>
      sel.includes(key) ? sel.filter(x => x !== key) : [...sel, key]
    );
  }

  function assignPeople(peopleToAssign) {
    const peopleWithKeys = peopleToAssign.map(person => ({
      ...person,
      _tempKey: person._tempKey || genKey(),
    }));
    setPeople(peopleWithKeys);
    setOriginalPeople(peopleWithKeys); // Save as baseline for change tracking
  }

  function getSelectedOpenPullRequestData(branchName) {
    if (!branchName) return;

    const url = [
      `/api/api_proxy/jobs/people/pull_request/`,
      encodeURIComponent(branchName),
      `/data`,
      `?jurisdiction_ocdid=${encodeURIComponent(jurisdiction_ocdid)}`
    ].join("");
    fetch(url)
      .then(r => r.json())
      .then(data => {
        if (data.data) {
          assignPeople(data.data);
        }
      })
  } 

  function submitChanges(branchName, data) {

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
    setDirty(true)
    // Optionally, call your API here if you can identify the person another way
  }

  function handleReset(tempKey) {
    console.log('Resetting person with key:', tempKey);
    if (!tempKey) {
      if (selectedOpenPullRequest) {
        getSelectedOpenPullRequestData(selectedOpenPullRequest);
      } else {
        assignPeople(people);
      }
      setSelected([]);
      setDirty(false);
    } else {
      const originalPerson = originalPeople.find(p => p._tempKey === tempKey);
      if (originalPerson) {
        setPeople(localPeople =>
          localPeople.map(person =>
            person._tempKey === tempKey ? { ...originalPerson } : person
          )
        );
      }
    }
  }

  function handleMerge() {
    if (selected.length < 2) return;
    const selectedPeople = localPeople.filter(p => selected.includes(p._tempKey));
    if (selectedPeople.length < 2) return;

    const singleValueFields = ["name", "image", "start_date", "end_date"];
    const arrayFields = ["other_names", "phones", "emails", "urls", "source_urls"];

    // Use the first selected person as the base for merging
    const basePersonIndex = localPeople.findIndex(p => p._tempKey === selected[0]);
    if (basePersonIndex === -1) return;
    const basePerson = { ...localPeople[basePersonIndex] };

    // Merge single value fields (pick first non-null)
    for (const field of singleValueFields) {
      basePerson[field] = selectedPeople.map(p => p[field]).find(v => v != null && v !== "");
    }
    // Merge array fields (combine, dedupe)
    for (const field of arrayFields) {
      basePerson[field] = Array.from(
        new Set(
          selectedPeople
            .flatMap(p => Array.isArray(p[field]) ? p[field] : (p[field] ? [p[field]] : []))
            .filter(Boolean)
        )
      );
    }

    // Special merge for office.name
    const officeNames = selectedPeople
      .map(p => p.office?.name)
      .filter(Boolean);
    if (officeNames.length > 0) {
      basePerson.office = {
        ...(basePerson.office || {}),
        name: officeNames.join(" - ")
      };
    }

    basePerson.jurisdiction_ocdid = selectedPeople[0].jurisdiction_ocdid;
    // Keep the original _tempKey of the base person

    // Remove all selected except the base, and replace base with merged
    setPeople(p => {
      const filtered = p.filter(person => !selected.includes(person._tempKey) || person._tempKey === basePerson._tempKey);
      filtered[basePersonIndex] = basePerson;
      return filtered;
    });
    setSelected([]);
    setDirty(true);
  }

  // Example usage in handleBulkDelete:
  function handleBulkDelete() {
    if (!confirm(`Delete ${selected.length} people?`)) return;
    setPeople(p => p.filter(person => !selected.includes(person._tempKey)));
    setSelected([]);
  }

  function handleSubmit() {
    setSelected([]);
    setDirty(false);
    setPeople([]);
    setNotice(
      selectedOpenPullRequest
        ? `Changes submitted to ${openPullRequests.find(pr => pr.branch_name === selectedOpenPullRequest)?.url || selectedOpenPullRequest}`
        : "Changes submitted."
    );
  }

  function selectActions() {
    return html`
      <div>
        <button @click=${handleMerge}>Merge (${selected.length})</button>
        <button @click=${handleBulkDelete}>Delete (${selected.length})</button>
      </div>
    `;
  }

  function updatePerson(key, updates) {
    setPeople(localPeople =>
      localPeople.map(person => {
        if (person._tempKey === key) {
          const originalPerson = originalPeople.find(p => p._tempKey === key);
          const nextPerson = { ...person, ...updates };
          const changedFields = TRACKED_FIELDS.filter(
            field => JSON.stringify(nextPerson[field]) !== JSON.stringify(originalPerson?.[field])
          );
          return {
            ...nextPerson,
            _dirty: changedFields.length > 0,
            _changes: changedFields,
          };
        }
        return person;
      })
    );
    setDirty(true);
  }

  if (loading) return html`<p>Loading people...</p>`;
  if (error) return html`<p>Error loading people.</p>`;

  return html`
  <div style="margin-bottom: 2rem;">
    <h3>Data Source</h3>
    <div role="radiogroup">
      ${loading
        ? html`<div style="margin: 1em 0;"><progress></progress> Loading pull requests...</div>`
        : html`
            <label style="display:block; margin-bottom:0.5em;">
              <input
                type="radio"
                name="pr"
                value=""
                .checked=${!selectedOpenPullRequest}
                @change=${() => setSelectedOpenPullRequest(null)}
              />
              Existing Data
            </label>
            ${openPullRequests.map(
              pr => html`
                <label style="display:block; margin-bottom:0.5em;">
                  <input
                    type="radio"
                    name="pr"
                    value=${pr.branch_name}
                    .checked=${selectedOpenPullRequest === pr.branch_name}
                    @change=${() => setSelectedOpenPullRequest(pr.branch_name)}
                  />
                  ${pr.branch_name}
                  <a href=${pr.url} target="_blank" style="margin-left:0.5em;">View PR</a>
                </label>
              `
            )}
          `}
    </div>
  </div>

  <div style="margin-bottom: 1rem; min-height: 2.5em; display: flex; align-items: center;">
    <button 
      @click=${handleMerge} 
      style="margin-right: 1rem;" 
      ?disabled=${selected.length < 2}
    >
      Merge (${selected.length})
    </button>
    <button 
      @click=${handleBulkDelete} 
      style="margin-right: 1rem;"
      ?disabled=${selected.length === 0}
    >
      Delete (${selected.length})
    </button>
    <button
      @click=${() => handleReset()}
      style="margin-left:auto; margin-right: 0.5rem;"
      ?disabled=${dirty === false}
    >
      Reset Form
    </button>
    <button
      @click=${handleSubmit}
      style="margin-right: 0;"
      ?disabled=${dirty === false}
    >
      Submit
    </button>
  </div>

  ${notice ? html`
    <div style="margin-bottom:1rem; padding:0.75em; background:#e0ffe0; border-radius:6px; color:#155724;">
      ${notice}
    </div>
  ` : ""}

  <div
    class="grid"
    style="
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 1rem;
      align-items: stretch;
      width: 100%;
    "
  >
    ${localPeople.map(
      person => html`
        <person-card
          .person=${person}
          .selected=${selected.includes(person._tempKey)}
          .onSelect=${() => toggleSelect(person._tempKey)}
          .onDelete=${() => handleDelete(person._tempKey)}
          .onChange=${(field, value) => updatePerson(person._tempKey, { [field]: value })}
          .onReset=${() => handleReset(person._tempKey)}
        ></person-card>
      `
    )}
  </div>

  <div style="margin-top:2rem;">
    <label for="final-yml" style="font-weight:600;">Final YAML Output</label>
    <textarea
      id="final-yml"
      readonly
      style="width:100%;height:300px;font-family:monospace;font-size:14px;resize:vertical;"
    >${yaml.dump(localPeople.map(({ ...person }) => person))}</textarea>
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
