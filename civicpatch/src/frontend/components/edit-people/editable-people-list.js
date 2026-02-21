import { html, component, useEffect, useState, useRef } from 'haunted';
import { ref } from 'lit-html/directives/ref.js';
import { keyed } from 'lit/directives/keyed.js';

import './person-card.js';
import '../basic/table/table.js';
import yaml from 'js-yaml';
import { useRovingFocusList } from '../../hooks/use-roving-focus-list.js';
import './diff-preview.js';

// Helper to generate a random key
function genKey() {
  return Math.random().toString(36).substr(2, 9) + Date.now();
}

const TRACKED_FIELDS = [
  "name", "other_names", "phones", "emails", "urls", "start_date", "end_date", "office", "source_urls",
  "image", "cdn_image", "updated_at"
];

function EditablePeopleList({ jurisdiction_ocdid, people = [] }) {
  // Assign _tempKey to people if not present
  const [currentPeople, setCurrentPeople] = useState(
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
  const [notice, setNotice] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const selectedPeople = currentPeople.filter(p => p._selected).map(p => p._tempKey);
  const dirty = currentPeople.some(person => person._dirty);
  const element = this;

  const peopleToSubmit = currentPeople
    .filter(p => !p._deleted)
    .map(({ _dirty, _changes, _tempKey, _selected, _deleted, _isNew, ...person }) => person);

  const {
    refs: cardRefs,
    focusedIdx,
    setFocusedIdx,
    handleKeyDown,
  } = useRovingFocusList(currentPeople.length);

  useEffect(() => {
    if (!jurisdiction_ocdid) return;
    setLoading(true);
    fetch(`/api/api_proxy/jobs/people/pull_request/open?jurisdiction_ocdid=${encodeURIComponent(jurisdiction_ocdid)}`)
      .then(r => r.json())
      .then(data => {
        const pullRequests = data.data || [];
        setOpenPullRequests(pullRequests);

        // Automatically select the first PR or default to "Existing Data"
        if (pullRequests.length > 0) {
          setSelectedOpenPullRequest(pullRequests[0].branch_name);
        } else {
          setSelectedOpenPullRequest(null);
        }

        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedOpenPullRequest) {
      // Use default people
      assignPeople(people)
    } else {
      getSelectedOpenPullRequestData(selectedOpenPullRequest);
    }
  }, [selectedOpenPullRequest])
  
  
  function toggleSelect(key) {
    setCurrentPeople(currentPeople =>
      currentPeople.map(person =>
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
    setCurrentPeople(peopleWithKeys);
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
      // Move person to bottom of the list
      reorderPersonToBottom(key);
    });
  }

  function handleBulkDelete() {
    markAsDeleted(selectedPeople);
  }

  function handleDelete(key) {
    // If it's a new person that hasn't been submitted yet, just remove it from the list
    const person = currentPeople.find(p => p._tempKey === key);
    if (person?._isNew) {
      setCurrentPeople(currentPeople => currentPeople.filter(p => p._tempKey !== key));
      return;
    }

    markAsDeleted([key]);
  }

  function handleAdd() {
    const default_office_name = "Council Member";
    //const first_person = originalPeople.lenggth > 0 ? originalPeople[0] : null;
    const last_person = originalPeople.length > 0 ? originalPeople[originalPeople.length - 1] : null;
    const default_office_division_ocdid = originalPeople.length > 0 ? originalPeople[0].office?.division_ocdid : null;
    const default_link = last_person?.urls?.[0] || null;
    const default_source_url = last_person?.source_urls?.[0] || null;

    const newPerson = {
      _tempKey: genKey(),
      _changes: [],
      _selected: false,
      _deleted: false,
      _isNew: true,
      name: '',
      other_names: [], 
      phones: [],
      emails: [],
      urls: default_link ? [default_link] : [],
      start_date: null,
      end_date: null,
      office: {
        name: default_office_name,
        division_ocdid: default_office_division_ocdid,
      },
      image: null,
      jurisdiction_ocdid: jurisdiction_ocdid,
      cdn_image: null,
      source_urls: [default_source_url],
      updated_at: new Date().toISOString().replace(/\.\d{3}Z$/, '+00:00'), // Correctly formatted updated_at
    };
    setCurrentPeople(currentPeople => [newPerson, ...currentPeople]);
  }

  function reorderPersonToBottom(key) {
    setCurrentPeople(currentPeople => {
      const index = currentPeople.findIndex(p => p._tempKey === key);
      if (index === -1) return currentPeople;
      const person = currentPeople[index];
      const without = currentPeople.filter(p => p._tempKey !== key);
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
    } else {
      const originalPerson = originalPeople.find(p => p._tempKey === tempKey);
      if (originalPerson) {
        setCurrentPeople(currentPeople =>
          currentPeople.map(person =>
            person._tempKey === tempKey ? { ...originalPerson } : person
          )
        );
      }
    }
  }

  function handleMerge() {
    const singleValueFields = ["name", "image", "start_date", "end_date", "image", "cdn_image", "updated_at"];
    const arrayFields = ["other_names", "phones", "emails", "urls", "source_urls"];
    const peopleToMerge = currentPeople.filter(p => selectedPeople.includes(p._tempKey));

    // Use the first selected person as the base for merging
    const basePersonIndex = currentPeople.findIndex(p => p._tempKey === selectedPeople[0]);
    if (basePersonIndex === -1) return;
    const basePerson = { ...currentPeople[basePersonIndex] };

    // Merge single value fields (pick first non-null, fallback to null)
    for (const field of singleValueFields) {
      basePerson[field] = peopleToMerge.map(p => p[field]).find(v => v != null && v !== "") || null;
    }

    // Merge array fields (combine, dedupe)
    for (const field of arrayFields) {
      basePerson[field] = Array.from(
        new Set(
          peopleToMerge
            .flatMap(p => Array.isArray(p[field]) ? p[field] : (p[field] ? [p[field]] : []))
            .filter(Boolean)
        )
      );
    }

    // Special merge for office.name
    const officeNames = peopleToMerge
      .map(p => p.office?.name)
      .filter(Boolean);
    if (officeNames.length > 0) {
      const uniqueOfficeNames = Array.from(new Set(officeNames));
      basePerson.office = {
        ...(basePerson.office || {}),
        name: uniqueOfficeNames.join(" - ")
      };
    }

    // Remove all selected except the base (keep merged in same position), and replace base with merged
    setCurrentPeople(p => {
      const withoutMerged = p.filter(person => !selectedPeople.includes(person._tempKey) || person._tempKey === basePerson._tempKey);
      const withChanges = withoutMerged.map(person => person._tempKey === basePerson._tempKey ? { ...basePerson, _dirty: true, _changes: TRACKED_FIELDS } : person);
      const resetSelected = withChanges.map(person => ({ ...person, _selected: false }));
      return resetSelected;
    });
  }

  function submitChanges(branchName, data) {
    setIsLoading(true);

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
        if (!r.ok) {
          throw new Error(`Failed to submit changes: ${r.status} ${r.statusText}`);
        } 
        return r.json();
      })
      .catch(e => {
        console.error("Error submitting changes:", e);
        throw e;
      })
      .finally(() => setIsLoading(false));
  }

  function handleSubmit() {
    setCurrentPeople([]);
    
    submitChanges(
      selectedOpenPullRequest, // TODO: if not available needs to open a new PR instead
      peopleToSubmit
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
    setCurrentPeople(currentPeople =>
      currentPeople.map(person => {
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
  }

  function handleTableDataChange(e) {
    // Find the person by index or key and update your state
    console.log("Data change event:", e.detail);
    const { identifier, key, value } = e.detail;
    updatePerson(identifier, { [key]: value }); 
  }

  if (loading) return html`<p>Loading people...</p>`;

  function truncateBranchName(branchName, maxLength = 24) {
    if (branchName.length > maxLength) {
      return branchName.substring(0, maxLength);
    }
    return branchName;
  } 

  const diffPreview = html`
  <div style="margin-top:2rem;">
    <label for="diff-table" style="font-weight:600;">YAML Diff</label>
    <diff-preview
      .original=${yaml.dump(originalPeople.map(({ _tempKey, ...person }) => person))}
      .updated=${yaml.dump(
        peopleToSubmit
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
        peopleToSubmit
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
    .tabs {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 1rem;
    }
    .tabs ul {
      list-style: none;
      padding: 0;
      margin: 0;
      display: flex;
      gap: 0.5rem;
    }
    .tabs li {
      margin: 0;
    }
    .tabs a {
      display: block;
      padding: 0.5rem 1rem;
      border: 1px solid #ccc;
      background: rgb(var(--catppuccin-crust));
      text-decoration: none;
      color: inherit;
      cursor: pointer;
    }
    .tabs a.active {
      background: rgb(var(--catppuccin-sapphire));
      color: white;
    }
    .tab-content {
      padding: 1rem;
      border: 1px solid #ccc;
      background: rgb(var(--catppuccin-crust));
    }
  </style>
  <div style="margin-bottom: 2rem;">
    <h3>Data Sources</h3>
    <nav class="tabs">
      <ul>
        ${openPullRequests.map(
          pr => html`
            <li>
              <a 
                href="#" 
                class=${selectedOpenPullRequest === pr.branch_name ? 'active' : ''} 
                @click=${(e) => {
                  e.preventDefault();
                  setSelectedOpenPullRequest(pr.branch_name);
                }}
              >
                [open] ${truncateBranchName(pr.branch_name)}
              </a>
            </li>
          `
        )}
        <li>
          <a 
            href="#" 
            class=${!selectedOpenPullRequest ? 'active' : ''} 
            @click=${(e) => {
              e.preventDefault();
              setSelectedOpenPullRequest(null);
            }}
          >
            Existing Data (TBD)
          </a>
        </li>
      </ul>
    </nav>
    <section class="selected-pr">
      ${!selectedOpenPullRequest
        ? html`
            <p>Use the existing data for this jurisdiction.</p>
        `
        : html`
          <a href=${openPullRequests.find(pr => pr.branch_name === selectedOpenPullRequest)?.url} target="_blank" class="contrast">
            View Pull Request
          </a>
        `}
    </section>
  </div>

  <div style="margin-bottom: 1rem; min-height: 2.5em; display: flex; align-items: center;">
    <button @click=${handleAdd} style="margin-right: 1rem;">
      Add
    </button>
    <button 
      @click=${handleMerge} 
      style="margin-right: 1rem;" 
      ?disabled=${selectedPeople.length < 2}
    >
      Merge (${selectedPeople.length})
    </button>
    <button 
      @click=${handleBulkDelete} 
      style="margin-right: 1rem;"
      ?disabled=${selectedPeople.length === 0}
    >
      Delete (${selectedPeople.length})
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

  <civ-table 
  .identifier=${"_tempKey"}
  .columns=${[
    {
      field: "cdn_image",
      label: "Image",
      editable: false,
      type: "image",
    },
    {
      field: "name",
      label: "Name",
      editable: true,
      type: "single",
    },
    {
      field: "phones",
      label: "Phones",
      editable: true,
      format: "phone",
      type: "multiple",
    },
    {
      field: "emails",
      label: "Emails",
      editable: true,
      format: "email",
      type: "multiple",
    },
    {
      field: "urls",
      label: "URLs",
      editable: true,
      type: "multiple",
    },
    {
      field: "start_date",
      label: "Start Date",
      editable: true,
      type: "date",
    },
    {
      field: "end_date",
      label: "End Date",
      editable: true,
      type: "date",
    },
    {
      field: "office.name",
      label: "Office Name",
      editable: true,
      type: "single",
    },
    {
      field: "office.division_ocdid",
      label: "Division",
      editable: true,
      type: "single"
    },
    {
      field: "source_urls",
      label: "Source URLs",
      editable: true,
      type: "multiple",
    }
  ]} 
  .data=${currentPeople} 
  @data-change=${handleTableDataChange}></civ-table>

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
    ${currentPeople.map(
      (person, idx) => keyed(person._tempKey, html`
        <div role="listitem">
          <person-card
            tabIndex=${focusedIdx === idx ? "0" : "-1"}
            ${ref(cardRefs[idx])}
            @focus=${() => setFocusedIdx(idx)}
            @keydown=${e => handleCardKeyDown(e, idx, person._tempKey) }
            .person=${person}
            .onSelect=${() => toggleSelect(person._tempKey)}
            .onDelete=${() => handleDelete(person._tempKey)}
            .onChange=${(field, value) => updatePerson(person._tempKey, { [field]: value })}
            .onReset=${() => handleReset(person._tempKey)}
          ></person-card>
        </div>
      `)
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
