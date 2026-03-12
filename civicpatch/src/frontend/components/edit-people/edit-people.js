import { html, component, useEffect, useState } from 'haunted';
import { ref } from 'lit-html/directives/ref.js';
import { keyed } from 'lit/directives/keyed.js';
import { getColumns } from "./table/columns.js"
import '../person-image.js';
import './person-card.js';
import '../basic/table/table.js';
import { useRovingFocusList } from '../../hooks/use-roving-focus-list.js';
import './action-buttons.js';
import './pull-request-tabs.js';
import { useCsrf } from '../../hooks/use-csrf.js';
import './review-table.js';
import './profile-modal.js';
import { config } from '../../assets/config.js';
import { usePeopleState } from './hooks/use-people-state.js';

const API_URL = config.apiUrl;

function EditablePeopleList({ jurisdiction_ocdid, people = [] }) {
  const {
    currentPeople,
    selectedPeople,
    dirty,
    peopleToSubmit,
    assignPeople,
    addPerson,
    updatePerson,
    toggleSelect,
    handleDelete,
    handleBulkDelete,
    handleMerge,
    handleReset,
    handleTableDataChange,
    handleTableDataReorder,
  } = usePeopleState({ people });

  const [reviewData, setReviewData] = useState(null);
  const [error, setError] = useState(null);
  const [selectedPullRequest, setSelectedPullRequest] = useState(null);
  const [notice, setNotice] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isMobile, setIsMobile] = useState(window.matchMedia('(max-width: 700px)').matches);
  const [profileModal, setProfileModal] = useState({ open: false, person: null });
  const csrfToken = useCsrf();

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 700px)');
    const handler = (e) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  const { refs: cardRefs, focusedIdx, setFocusedIdx, handleKeyDown } = useRovingFocusList(currentPeople.length);

  useEffect(() => {
    if (!selectedPullRequest) {
      assignPeople(people);
      setReviewData(null);
    } else {
      handleSelectedPullRequestData(selectedPullRequest);
    }
  }, [selectedPullRequest]);

  async function fetchPullRequestData(pullRequest) {
    if (!pullRequest) return null;
    const url = `${API_URL}/api/v1/pull_requests/data`
      + `?jurisdiction_ocdid=${encodeURIComponent(jurisdiction_ocdid)}`
      + `&request_id=${encodeURIComponent(pullRequest.request_id)}`;
    setIsLoading(true);
    const response = await fetch(url, { credentials: "include" });
    setIsLoading(false);
    if (!response.ok) throw new Error("Failed to fetch pull request data");
    return response.json();
  }

  async function handleSelectedPullRequestData(pullRequest) {
    if (!pullRequest) return;
    try {
      const data = await fetchPullRequestData(pullRequest);
      if (data?.data) assignPeople(data.data);
      setReviewData(data?.review || null);
    } catch (err) {
      setError("Failed to load pull request data.");
      console.error(err);
    }
  }

  async function generatePersonId() {
    const res = await fetch(`${API_URL}/api/v1/people/generate-id`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      credentials: "include",
    });
    if (!res.ok) throw new Error("Failed to generate person id");
    const data = await res.json();
    return data.data.person_id;
  }

  async function handleAdd() {
    const person_id = await generatePersonId();
    const last = people[people.length - 1] ?? null;
    addPerson({
      id: person_id,
      _changes: [],
      _selected: false,
      _deleted: false,
      _isNew: true,
      name: "",
      other_names: [],
      phones: [],
      emails: [],
      urls: last?.urls?.[0] ? [last.urls[0]] : [],
      start_date: null,
      end_date: null,
      office: {
        name: "Council Member",
        division_ocdid: people[0]?.office?.division_ocdid ?? null,
      },
      image: null,
      cdn_image: null,
      jurisdiction_ocdid,
      source_urls: last?.source_urls?.[0] ? [last.source_urls[0]] : [],
      updated_at: new Date().toISOString().replace(/\.\d{3}Z$/, '+00:00'),
    });
  }

  function submitChanges(branchName, data) {
    setIsLoading(true);
    const url = `${API_URL}/api/v1/pull_requests/${encodeURIComponent(branchName)}/data`;
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      body: JSON.stringify({ jurisdiction_ocdid, data }),
      credentials: "include",
    })
      .then(r => {
        if (!r.ok) throw new Error(`Failed to submit changes: ${r.status} ${r.statusText}`);
        return r.json();
      })
      .finally(() => setIsLoading(false));
  }

  function handleSubmit() {
    submitChanges(selectedPullRequest?.branch_name, peopleToSubmit)
      .then(() => {
        setNotice(selectedPullRequest
          ? `Changes submitted: <a href="${selectedPullRequest.url}">${selectedPullRequest.url}</a>`
          : "Changes submitted."
        );
      })
      .catch((e) => {
        console.error("Error submitting changes:", e);
        setError("Failed to submit changes.");
      });
  }

  function handleCardKeyDown(e, idx, key) {
    handleKeyDown(e, idx);
    if (e.target !== e.currentTarget) return;
    if ((e.key === ' ' || e.key === 'Enter') && key) {
      e.preventDefault();
      toggleSelect(key);
    }
  }

  function openProfileModal(person) {
    setProfileModal({ open: true, person });
  }

  function renderTableView() {
    return html`<civ-table
      .identifier=${"id"}
      .selectedIdentifiers=${selectedPeople}
      .canReorder=${true}
      .columns=${getColumns(openProfileModal)}
      .data=${currentPeople}
      @data-change=${handleTableDataChange}
      @reorder=${handleTableDataReorder}>
    </civ-table>`;
  }

  function renderCardView() {
    return html`<div class="grid" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:1rem; align-items:stretch; width:100%;">
      ${currentPeople.map((person, idx) => keyed(person.id, html`
        <div role="listitem">
          <person-card
            tabIndex=${focusedIdx === idx ? "0" : "-1"}
            ${ref(cardRefs[idx])}
            @focus=${() => setFocusedIdx(idx)}
            @keydown=${e => handleCardKeyDown(e, idx, person.id)}
            .person=${person}
            .onSelect=${() => toggleSelect(person.id)}
            .onDelete=${() => handleDelete([person.id])}
            .onChange=${(field, value) => updatePerson(person.id, { [field]: value })}
            .onReset=${() => handleReset(person.id)}
          ></person-card>
        </div>
      `))}
    </div>`;
  }

  return html`
    <civ-pull-request-tabs
      .jurisdiction_ocdid=${jurisdiction_ocdid}
      @selected-pull-request=${e => setSelectedPullRequest(e.detail.pullRequest)}
    ></civ-pull-request-tabs>

    ${selectedPullRequest ? html`
      <a href=${selectedPullRequest.url} target="_blank" class="contrast">View Pull Request</a>
      <hr />
      <civ-review-table
        .jurisdiction_ocdid=${jurisdiction_ocdid}
        .branch_name=${selectedPullRequest.branch_name}
        .reviewData=${reviewData}
        .currentPeople=${currentPeople}
      ></civ-review-table>
    ` : ""}

    <civ-people-action-buttons
      .onAdd=${handleAdd}
      .onMerge=${handleMerge}
      .onBulkDelete=${handleBulkDelete}
      .onReset=${() => selectedPullRequest
        ? handleSelectedPullRequestData(selectedPullRequest)
        : assignPeople(people)}
      .onSubmit=${handleSubmit}
      .selectedPeople=${selectedPeople}
      .dirty=${dirty}
      .isLoading=${isLoading}
      .notice=${notice}
    ></civ-people-action-buttons>

    ${notice ? html`<div style="margin-bottom:1rem; padding:0.75em; background:#e0ffe0; border-radius:6px; color:#155724;">${notice}</div>` : ""}
    ${error ? html`<div style="margin-bottom:1rem; padding:0.75em; background:#ffe0e0; border-radius:6px; color:#721c24;">${error}</div>` : ""}

    ${ isLoading ?
      html`<div style="margin-bottom:1rem; padding:0.75em; background:#e0e0ff; border-radius:6px; color:#0000b3;">Loading pull request data...</div>`
      : isMobile ? renderCardView() : renderTableView()
    }

    <profile-modal
      .open=${profileModal.open}
      .person=${profileModal.person}
      @close=${() => setProfileModal({ open: false, person: null, existingPerson: null })}
    ></profile-modal>
  `;
}

customElements.define('civ-editable-people-list', component(EditablePeopleList, { useShadowDOM: false, observedAttributes: ['jurisdiction_ocdid'] }));