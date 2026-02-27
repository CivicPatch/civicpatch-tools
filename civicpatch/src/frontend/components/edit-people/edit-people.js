import { html, component, useEffect, useState, useRef } from 'haunted';
import { ref } from 'lit-html/directives/ref.js';
import { keyed } from 'lit/directives/keyed.js';

import './person-card.js';
import '../basic/table/table.js';
import yaml from 'js-yaml';
import { useRovingFocusList } from '../../hooks/use-roving-focus-list.js';
import './diff-preview.js';
import './pull-request-tabs.js';
import { useCsrf } from '../../hooks/use-csrf.js';
import './review-table.js';
const API_URL = __API_URL__;

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
  const [reviewData, setReviewData] = useState(null);
  const [error, setError] = useState(null);
  const [selectedPullRequest, setSelectedPullRequest] = useState(null);
  const [notice, setNotice] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isMobile, setIsMobile] = useState(window.matchMedia('(max-width: 700px)').matches);
  const csrfToken = useCsrf();


  useEffect(() => {
    const mq = window.matchMedia('(max-width: 700px)');
    const handler = (e) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  const selectedPeople = currentPeople.filter(p => p._selected).map(p => p._tempKey);
  const dirty = currentPeople.some(person => person._dirty);

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
    if (!selectedPullRequest) {
      // Use default people
      assignPeople(people)
      setReviewData(null);
    } else {
      getSelectedPullRequestData(selectedPullRequest);
    }
  }, [selectedPullRequest])

  function toggleSelect(key) {
    setCurrentPeople(currentPeople =>
      currentPeople.map(person =>
        person._tempKey === key
          ? { ...person, _selected: !person._selected }
          : person
      )
    );
  }

  function setSelected(key, selected) {
    setCurrentPeople(currentPeople =>
      currentPeople.map(person =>
        person._tempKey === key
          ? { ...person, _selected: selected }
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

  function getSelectedPullRequestData(pullRequest) {
    if (!pullRequest) return;

    const url = [
      `${API_URL}/api/v1/jobs/people/pull_request/`,
      encodeURIComponent(pullRequest.branch_name),
      `/data`,
      `?jurisdiction_ocdid=${encodeURIComponent(jurisdiction_ocdid)}`
    ].join("");
    fetch(url, { credentials: "include" })
      .then(r => r.json())
      .then(data => {
        if (data.data) {
          assignPeople(data.data);
          // TODO: handle error
        }
        if (data.review) {
          setReviewData(data.review)
        } else {
          setReviewData(null);
        }
      })
  } 

  function handleDelete(keys) {
    keys.forEach(key => {
      // If it's a new person that hasn't been submitted yet, just remove it from the list
      const person = currentPeople.find(p => p._tempKey === key);
      if (person?._isNew) {
        setCurrentPeople(currentPeople => currentPeople.filter(p => p._tempKey !== key));
        return;
      }

      updatePerson(key, { _deleted: true });
      reorderPersonToBottom(key);
    });
  }

  function handleBulkDelete() {
    handleDelete(selectedPeople);
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
      if (selectedPullRequest) {
        getSelectedPullRequestData(selectedPullRequest);
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
      `${API_URL}/api/v1/jobs/people/pull_request/`,
      encodeURIComponent(branchName),
      `/data`,
    ]
      .join("");

    console.log("Submitting to URL:", url, csrfToken);
    
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken
      },
      body: JSON.stringify({ jurisdiction_ocdid, data }),
      credentials: "include"
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
    submitChanges(
      selectedPullRequest?.branch_name, // TODO: if not available needs to open a new PR instead
      peopleToSubmit
    )
      .then(() => {
        setNotice(
         selectedPullRequest
            ? `Changes submitted: ${selectedPullRequest?.url}`
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
    const { identifier, field, value } = e.detail;
    console.log("Data change:", identifier, field, value);



    if (field == "_selected") {
      setSelected(identifier, value);
    } else {
      // Handle nested field, ex: office.name
      updatePerson(identifier, { [field]: value });
    }
  }

  function handleTableDataReorder(e) {
    const { newOrder } = e.detail;
    setCurrentPeople(currentPeople => {
      const peopleById = currentPeople.reduce((acc, person) => {
        person._dirty = true;
        acc[person._tempKey] = person;

        return acc;
      }, {});
      return newOrder.map(id => peopleById[id] || peopleById[parseInt(id)]);
    });
  }

  function renderActionButtons() {
    return html`
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
          @click=${() => handleReset(null)}
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
    `
  } 

  function customCssForPerson(person, field) {
    if (person._deleted) {
      return "opacity: 0.5; text-decoration: line-through; background-color: var(--pico-del-color);";
    } else if (person._changes?.includes(field)) {
      return "background-color: var(--pico-ins-color);";
    }
    return "";
  }

  function renderTableView() {
    return html`<civ-table 
      .identifier=${"_tempKey"}
      .selectedIdentifiers=${selectedPeople}
      .canReorder=${true}
      .columns=${[
        {
          field: "_selected",
          editable: true,
          type: "checkbox",
        },
        {
          type: "drag-row",
          editable: false,
          renderCell: (person) => html`
              <div style="display:flex;align-items:center;justify-content:center; height:100%;">
                <span class="drag-handle" style="display: flex; align-items: center; justify-content: center; cursor: grab; font-size: 1.2rem; height: 100%;" title="Drag to reorder">
                  <i class="fas fa-grip-vertical" style="display: flex; align-items: center; justify-content: center; height: 100%;"></i>
                </span>
              </div>
          `
        },
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
          customCss: customCssForPerson,
        },
        {
          field: "phones",
          label: "Phones",
          editable: true,
          format: "phone",
          type: "multiple",
          customCss: customCssForPerson,
        },
        {
          field: "emails",
          label: "Emails",
          editable: true,
          format: "email",
          type: "multiple",
          customCss: customCssForPerson,
        },
        {
          field: "urls",
          label: "URLs",
          editable: true,
          type: "multiple",
          customCss: customCssForPerson,
        },
        {
          field: "start_date",
          label: "Start Date",
          editable: true,
          type: "date",
          customCss: customCssForPerson,
        },
        {
          field: "end_date",
          label: "End Date",
          editable: true,
          type: "date",
          customCss: customCssForPerson,
        },
        {
          field: "office.name",
          label: "Office Name",
          editable: true,
          type: "single",
          customCss: customCssForPerson,
        },
        {
          field: "office.division_ocdid",
          label: "Division",
          editable: true,
          type: "single",
          customCss: customCssForPerson,
        },
        {
          field: "source_urls",
          label: "Source URLs",
          editable: true,
          type: "multiple",
          customCss: customCssForPerson,
        }
      ]}
      .data=${currentPeople}
      @data-change=${handleTableDataChange}
      @reorder=${handleTableDataReorder}></civ-table>
    `;
  }

  function renderCardView() {
    return html`<div
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
                .onDelete=${() => handleDelete([person._tempKey])}
                .onChange=${(field, value) => updatePerson(person._tempKey, { [field]: value })}
                .onReset=${() => handleReset(person._tempKey)}
              ></person-card>
            </div>
          `)
        )}
      </div>`;
  }

  // if (loading) return html`<p>Loading people...</p>`;

  const diffPreview = html`
  <div style="margin-top:2rem;">
    <label for="diff-table" style="font-weight:600;">YAML Diff</label>
    <diff-preview
      .original=${yaml.dump(originalPeople.map(({ _tempKey, ...person }) => person))}
      .updated=${yaml.dump(
        peopleToSubmit
      )}></diff-preview>
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
    <civ-pull-request-tabs
      .jurisdiction_ocdid=${jurisdiction_ocdid}
      @selected-pull-request=${e => {
        setSelectedPullRequest(e.detail.pullRequest)
      }}
    ></civ-pull-request-tabs>
    <section class="selected-pr">
      ${!selectedPullRequest
        ? html`
            <p>Use existing data for this jurisdiction.</p>
        `
        : html`
          <a href=${selectedPullRequest?.url} target="_blank" class="contrast">
            View Pull Request
          </a>
        `}
    </section>
  
  <civ-review-table
    .jurisdiction_ocdid=${jurisdiction_ocdid}
    .branch_name=${selectedPullRequest?.branch_name}
    .reviewData=${reviewData}
    .currentPeople=${currentPeople}
  ></civ-review-table>

  ${renderActionButtons()}

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

  ${ isMobile ? renderCardView() : renderTableView()}

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
