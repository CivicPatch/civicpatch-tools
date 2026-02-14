import { html, component, useEffect, useState, useRef } from 'haunted';
import { ref } from 'lit-html/directives/ref.js';
import './person-card.js';
import yaml from 'js-yaml';
import { useRovingFocusList } from '../../hooks/use-roving-focus-list.js';
import './diff-preview.js';

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
  const [originalPeople, setOriginalPeople] = useState([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openPullRequests, setOpenPullRequests] = useState([]);
  const [selectedOpenPullRequest, setSelectedOpenPullRequest] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [notice, setNotice] = useState(null);

  const {
    refs: cardRefs,
    focusedIdx,
    setFocusedIdx,
    handleKeyDown,
  } = useRovingFocusList(localPeople.length);

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
    setPeople(localPeople =>
      localPeople.map(person =>
        person._tempKey === key
          ? { ...person, _selected: !person._selected }
          : person
      )
    );
  }

  function handleCardKeyDown(e, idx, tempKey) {
    handleKeyDown(e, idx);

    if (e.target !== e.currentTarget) return; // Only handle if event is on the card itself

    if ((e.key === ' ' || e.key === 'Enter') && tempKey) {
      e.preventDefault();
      toggleSelect(tempKey);
    }
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

  function markAsDeleted(keys) {
    keys.forEach(key => {
      updatePerson(key, { _deleted: true });
    });
  }

  function handleBulkDelete() {
    markAsDeleted(selected);
  }

  function handleDelete(key) {
    // If it's a new person that hasn't been submitted yet, just remove it from the list
    const person = localPeople.find(p => p._tempKey === key);
    if (person?._isNew) {
      setPeople(localPeople => localPeople.filter(p => p._tempKey !== key));
      return;
    }

    markAsDeleted([key]);
    // Move person to bottom of the list
    reorderPersonToBottom(key);
  }

  function handleAdd() {
    const default_office_name = "Council Member";
    const default_office_division_ocdid = originalPeople.length > 0 ? originalPeople[0].office?.division_ocdid : null;

    const newPerson = {
      _tempKey: genKey(),
      _changes: [],
      _selected: false,
      _deleted: false,
      _isNew: true,
      name: '',
      office: {
        name: default_office_name,
        division_ocdid: default_office_division_ocdid,
      },
      phones: [],
      emails: [],
      urls: [],
      source_urls: [],
      start_date: '',
      end_date: '',
    };
    setPeople(localPeople => [newPerson, ...localPeople]);
  }

  function reorderPersonToBottom(key) {
    setPeople(localPeople => {
      const index = localPeople.findIndex(p => p._tempKey === key);
      if (index === -1) return localPeople;
      const person = localPeople[index];
      const without = localPeople.filter(p => p._tempKey !== key);
      return [...without, person];
    });
  }

  function handleReset(tempKey) {
    if (!tempKey) {
      if (selectedOpenPullRequest) {
        getSelectedOpenPullRequestData(selectedOpenPullRequest);
      } else {
        assignPeople(people);
      }
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
    setDirty(true);
  }

  function submitChanges(branchName, data) {
    const url = [
      `/api/api_proxy/jobs/people/pull_request/`,
      encodeURIComponent(branchName),
      `/data`,
    ]
      .join("");
    
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ jurisdiction_ocdid, data }),
    })
      .then(r => {
        console.log("Submit response:", r);
        if (!r.ok) {
          console.log("rethrowing...")
          throw new Error(`Failed to submit changes: ${r.status} ${r.statusText}`);
        } 
        return r.json();
      })
      .catch(e => {
        console.error("Error submitting changes:", e);
        throw e;
      })
  }

  function handleSubmit() {
    setDirty(false);
    setPeople([]);
    
    submitChanges(
      selectedOpenPullRequest, // TODO: if not available needs to open a new PR instead
      localPeople.map(({ _dirty, _changes, _tempKey, _selected, _deleted, ...person }) => person)
    )
      .then(() => {
        setNotice(
          selectedOpenPullRequest
            ? `Changes submitted to ${openPullRequests.find(pr => pr.branch_name === selectedOpenPullRequest)?.url || selectedOpenPullRequest}`
            : "Changes submitted."
        );
      })
      .catch((e) => {
        console.error("Error submitting changes:", e);
        setError("Failed to submit changes.");
      });
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
          _dirty: changedFields.length > 0 || updates._deleted === true,
          _changes: changedFields,
        };
      }
      return person;
    })
  );
  setDirty(true);
}

  const selected = localPeople.filter(p => p._selected).map(p => p._tempKey);

  const updatedPeople = localPeople.map(({ _dirty, _changes, _tempKey, _selected, _deleted, ...person }) => person);

  if (loading) return html`<p>Loading people...</p>`;

  const diffPreview = html`
  <div style="margin-top:2rem;">
    <label for="diff-table" style="font-weight:600;">YAML Diff</label>
    <diff-preview
      .original=${yaml.dump(originalPeople.map(({ _tempKey, ...person }) => person))}
      .updated=${yaml.dump(
        updatedPeople
      )}
    ></diff-preview>
    <div style="margin-top:2rem;">
      <label for="final-yml" style="font-weight:600;">Final YAML Output</label>
      <pre id="final-yml" style="
        background: var(--pico-code-background, #f6f8fa);
        border-radius: 6px;
        padding: 1em;
        font-family: var(--pico-font-monospace, monospace);
        white-space: pre-wrap;
        max-height: 300px;
        overflow: auto;
      ">${yaml.dump(
        updatedPeople
      )}</pre>
    </div>
  </div>
`;

  return html`
  <style>
    .grid > [role="listitem"] person-card:focus article {
        outline: none;
        box-shadow: 0 0 0 2px rgba(0,0,0,0.12);
        z-index: 1;
    }
  </style>
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
    <button @click=${handleAdd} style="margin-right: 1rem;">
      Add
    </button>
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
      style="margin-left:auto; margin-right: 1rem;"
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

  ${error ? html`
    <div style="margin-bottom:1rem; padding:0.75em; background:#ffe0e0; border-radius:6px; color:#721c24;">
      ${error}
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
      (person, idx) => html`
        <div role="listitem">
          <person-card
            tabIndex=${focusedIdx === idx ? "0" : "-1"}
            ${ref(cardRefs[idx])}
            @focus=${() => setFocusedIdx(idx)}
            @keydown=${e => handleCardKeyDown(e, idx, person._tempKey) }
            .person=${person}
            .selected=${selected.includes(person._tempKey)}
            .onSelect=${() => toggleSelect(person._tempKey)}
            .onDelete=${() => handleDelete(person._tempKey)}
            .onChange=${(field, value) => updatePerson(person._tempKey, { [field]: value })}
            .onReset=${() => handleReset(person._tempKey)}
          ></person-card>
        </div>
      `
    )}
  </div>
  ${!notice ? diffPreview : ""}
  `;
}

customElements.define(
  'civ-editable-people-list',
  component(
    EditablePeopleList,
    {
      useShadowDOM: false, observedAttributes: ['jurisdiction_ocdid']
    }
  )
);
