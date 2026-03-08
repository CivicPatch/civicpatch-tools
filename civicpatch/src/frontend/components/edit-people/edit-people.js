import { html, component, useEffect, useState, useRef } from 'haunted';
import { ref } from 'lit-html/directives/ref.js';
import { keyed } from 'lit/directives/keyed.js';

import './person-card.js';
import '../basic/table/table.js';
import yaml from 'js-yaml';
import { useRovingFocusList } from '../../hooks/use-roving-focus-list.js';
import './action-buttons.js';
import './pull-request-tabs.js';
import { useCsrf } from '../../hooks/use-csrf.js';
import './review-table.js';
import './profile-modal.js';
import { config } from '../../assets/config.js';
const API_URL = config.apiUrl;

const TRACKED_FIELDS = [
  "name", "other_names", "phones", "emails", "urls", "start_date", "end_date", "office", "source_urls",
  "image", "cdn_image", "updated_at"
];

function EditablePeopleList({ jurisdiction_ocdid, people = [] }) {
  // Assign id to people if not present
  const [currentPeople, setCurrentPeople] = useState(
    people.map(person => ({
      ...person,
    }))
  );
  const [originalPeople, setOriginalPeople] = useState([]);
  const [reviewData, setReviewData] = useState(null);
  const [error, setError] = useState(null);
  const [selectedPullRequest, setSelectedPullRequest] = useState(null);
  const [notice, setNotice] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isMobile, setIsMobile] = useState(window.matchMedia('(max-width: 700px)').matches);
  const [profileModal, setProfileModal] = useState({ open: false, person: null });
  const [resolvedPeople, setResolvedPeople] = useState({}); // [{ id, name, email }]
  const selectedPeople = currentPeople.filter(p => p._selected).map(p => p.id);
  const dirty = currentPeople.some(person => person._dirty);

  const peopleToSubmit = currentPeople
    .filter(p => !p._deleted)
    .map(({ _dirty, _changes, _selected, _deleted, _isNew, ...person }) => person);
  const csrfToken = useCsrf();


  useEffect(() => {
    const mq = window.matchMedia('(max-width: 700px)');
    const handler = (e) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

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
      handleSelectedPullRequestData(selectedPullRequest)
    }
  }, [selectedPullRequest])

  async function fetchPullRequestData(pullRequest, jurisdiction_ocdid) {
    if (!pullRequest) return null;
    const url = [
      `${API_URL}/api/v1/jobs/people/pull_request/`,
      encodeURIComponent(pullRequest.branch_name),
      `/data`,
      `?jurisdiction_ocdid=${encodeURIComponent(jurisdiction_ocdid)}`
    ].join("");
    const response = await fetch(url, { credentials: "include" });
    if (!response.ok) throw new Error("Failed to fetch pull request data");
    return response.json();
  }

  async function batchResolvePeople(people, jurisdiction_ocdid) {
    if (!people?.length) return null;
    const formattedPeople = people.map(person => ({
      id: person.id,
      name: person.name,
      email: person.emails?.[0] || null,
    }));

    const res = await fetch(`${API_URL}/api/v1/people/batch-resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      credentials: "include",
      body: JSON.stringify({ people: formattedPeople, jurisdiction_ocdid })
    });
    if (!res.ok) throw new Error("Batch resolve failed");
    return res.json();
  }

  async function handleSelectedPullRequestData(pullRequest) {
    if (!pullRequest) return;
    try {
      const data = await fetchPullRequestData(pullRequest, jurisdiction_ocdid);
      if (data?.data) {
        assignPeople(data.data);
        //try {
        //  const response = await batchResolvePeople(data.data, jurisdiction_ocdid);
        //  const formatted_people = response?.data?.map(d => d.person) || [];
        //  setResolvedPeople(formatted_people.reduce((acc, person) => {
        //    acc[person.id] = person;
        //    return acc;
        //  }, {}));
        //} catch (err) {
        //  console.error("Batch resolve failed", err);
        //}
      }
      setReviewData(data?.review || null);
    } catch (err) {
      setError("Failed to load pull request data.");
      console.error(err);
    }
  }

  function toggleSelect(key) {
    setCurrentPeople(currentPeople =>
      currentPeople.map(person =>
        person.id === key
          ? { ...person, _selected: !person._selected }
          : person
      )
    );
  }

  function setSelected(key, selected) {
    setCurrentPeople(currentPeople =>
      currentPeople.map(person =>
        person.id === key
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
    // Build a Set of canonical ids for fast lookup
    const canonicalIds = new Set((people || []).map(p => p.id).filter(Boolean));

    const peopleWithKeys = peopleToAssign.map(person => {
      const isNew = !person.id || !canonicalIds.has(person.id);
      return {
        ...person,
        id: person.id,
        _isNew: isNew,
      };
    });
    setCurrentPeople(peopleWithKeys);
    setOriginalPeople(peopleWithKeys); // Save as baseline for change tracking
  }

  function handleDelete(keys) {
    keys.forEach(key => {
      // If it's a new person that hasn't been submitted yet, just remove it from the list
      const person = currentPeople.find(p => p.id === key);
      if (person?._isNew) {
        setCurrentPeople(currentPeople => currentPeople.filter(p => p.id !== key));
        return;
      }

      updatePerson(key, { _deleted: true });
      reorderPersonToBottom(key);
    });
  }

  function handleBulkDelete() {
    handleDelete(selectedPeople);
  }

  async function resolvePerson({ name, email, jurisdiction_ocdid }) {
    const res = await fetch(`${API_URL}/api/v1/people/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ name, email, jurisdiction_ocdid }),
    });
    if (!res.ok) throw new Error("Failed to resolve person");
    const data = await res.json();
    return data.data; // { person_id, person, ambiguous }
  }

  async function generatePersonId() {
    const res = await fetch(`${API_URL}/api/v1/people/generate-id`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken
       },
      credentials: "include",
    });
    if (!res.ok) throw new Error("Failed to generate person id");
    const data = await res.json();
    return data.data.person_id;
  }

  async function handleAdd() {
    const default_office_name = "Council Member";
    const last_person = originalPeople.length > 0 ? originalPeople[originalPeople.length - 1] : null;
    const default_office_division_ocdid = originalPeople.length > 0 ? originalPeople[0].office?.division_ocdid : null;
    const default_link = last_person?.urls?.[0] || null;
    const default_source_url = last_person?.source_urls?.[0] || null;

    // You can prompt for name/email here, or leave blank for now
    const name = "";
    const email = "";

    // Call generatePersonId to get a new id
    let person_id;
    person_id = await generatePersonId();

    const newPerson = {
      id: person_id,
      _changes: [],
      _selected: false,
      _deleted: false,
      _isNew: true,
      name,
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
      updated_at: new Date().toISOString().replace(/\.\d{3}Z$/, '+00:00'),
    };
    setCurrentPeople(currentPeople => [newPerson, ...currentPeople]);
  }

  function reorderPersonToBottom(key) {
    setCurrentPeople(currentPeople => {
      const index = currentPeople.findIndex(p => p.id === key);
      if (index === -1) return currentPeople;
      const person = currentPeople[index];
      const without = currentPeople.filter(p => p.id !== key);
      return [...without, person];
    });
  }

  function handleReset(tempKey) {
    if (!tempKey) {
      if (selectedPullRequest) {
        handleSelectedPullRequestData(selectedPullRequest);
      } else {
        assignPeople(people);
      }
    } else {
      const originalPerson = originalPeople.find(p => p.id === tempKey);
      if (originalPerson) {
        setCurrentPeople(currentPeople =>
          currentPeople.map(person =>
            person.id === tempKey ? { ...originalPerson } : person
          )
        );
      }
    }
  }

  function handleMerge() {
    const singleValueFields = ["name", "image", "start_date", "end_date", "image", "cdn_image", "updated_at"];
    const arrayFields = ["other_names", "phones", "emails", "urls", "source_urls"];
    const peopleToMerge = currentPeople.filter(p => selectedPeople.includes(p.id));

    // Use the first selected person as the base for merging
    const basePersonIndex = currentPeople.findIndex(p => p.id === selectedPeople[0]);
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
      const withoutMerged = p.filter(person => !selectedPeople.includes(person.id) || person.id === basePerson.id);
      const withChanges = withoutMerged.map(person => person.id === basePerson.id ? { ...basePerson, _dirty: true, _changes: TRACKED_FIELDS } : person);
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
            ? `Changes submitted: <a href="${selectedPullRequest?.url}">${selectedPullRequest?.url}</a>`
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
        if (person.id === key) {
          const originalPerson = originalPeople.find(p => p.id === key);
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
        acc[person.id] = person;

        return acc;
      }, {});
      return newOrder.map(id => peopleById[id] || peopleById[parseInt(id)]);
    });
  }

  function customCssForPerson(person, field) {
    if (person._deleted) {
      return "opacity: 0.5; text-decoration: line-through; background-color: var(--pico-del-color);";
    } else if (person._changes?.includes(field)) {
      return "background-color: var(--pico-ins-color);";
    }
    return "";
  }

  function openProfileModal(person) {
    const existingPerson = resolvedPeople[person.id];
    setProfileModal({ open: true, person, existingPerson });
  }

  function renderImageCell(person) {
    const value = person?.cdn_image || person?.image;
    let initials = "?";
    if (person?.name) {
      const parts = person.name.trim().split(/\s+/);
      initials = parts.slice(0, 2).map(p => p[0].toUpperCase()).join("");
    }
    return html`
      <button
        type="button"
        style="
          all: unset;
          cursor: pointer;
          width: 100%;
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0.25rem;
          box-sizing: border-box;
        "
        @click=${() => openProfileModal(person)}
        title="Edit profile"
      >
        ${value
          ? html`<img src="${value}" alt="Profile image" style="
              width: min(100%, 100cqh, 4rem);
              height: min(100%, 100cqh, 4rem);
              border-radius: 50%;
              object-fit: cover;
              object-position: center;
              display: block;
              flex-shrink: 0;
            " />`
          : html`<div style="
              width: min(100%, 100cqh, 4rem);
              height: min(100%, 100cqh, 4rem);
              border-radius: 50%;
              display: flex;
              align-items: center;
              justify-content: center;
              flex-shrink: 0;
              font-size: 1.1rem;
              font-weight: bold;
              background: #f0f0f0;
              color: #888;
            ">${initials}</div>`
        }
      </button>
    `;
  }

  function renderTableView() {
    return html`<civ-table 
      .identifier=${"id"}
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
          renderCell: (person) => renderImageCell(person),
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
        },
        {
          field: "id",
          label: "ID",
          editable: false,
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
          (person, idx) => keyed(person.id, html`
            <div role="listitem">
              <person-card
                tabIndex=${focusedIdx === idx ? "0" : "-1"}
                ${ref(cardRefs[idx])}
                @focus=${() => setFocusedIdx(idx)}
                @keydown=${e => handleCardKeyDown(e, idx, person.id) }
                .person=${person}
                .onSelect=${() => toggleSelect(person.id)}
                .onDelete=${() => handleDelete([person.id])}
                .onChange=${(field, value) => updatePerson(person.id, { [field]: value })}
                .onReset=${() => handleReset(person.id)}
              ></person-card>
            </div>
          `)
        )}
      </div>`;
  }

  return html`
    <civ-pull-request-tabs
      .jurisdiction_ocdid=${jurisdiction_ocdid}
      @selected-pull-request=${e => {
        setSelectedPullRequest(e.detail.pullRequest)
      }}
    ></civ-pull-request-tabs>

  ${!!selectedPullRequest ? html`
    <a href=${selectedPullRequest?.url} target="_blank" class="contrast">
      View Pull Request
    </a>
    <hr />
    <civ-review-table
      .jurisdiction_ocdid=${jurisdiction_ocdid}
      .branch_name=${selectedPullRequest?.branch_name}
      .reviewData=${reviewData}
      .currentPeople=${currentPeople}
    ></civ-review-table>
  ` : ""}
  
  <civ-people-action-buttons
    .onAdd=${handleAdd}
    .onMerge=${handleMerge}
    .onBulkDelete=${handleBulkDelete}
    .onReset=${() => handleReset(null)}
    .onSubmit=${handleSubmit}
    .selectedPeople=${selectedPeople}
    .dirty=${dirty}
    .isLoading=${isLoading}
    .notice=${notice}
  ></civ-people-action-buttons>

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
  <profile-modal
    .open=${profileModal.open}
    .person=${profileModal.person}
    .existingPerson=${profileModal.existingPerson}
    @close=${() => setProfileModal({ open: false, person: null, existingPerson: null })}
  ></profile-modal>
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
