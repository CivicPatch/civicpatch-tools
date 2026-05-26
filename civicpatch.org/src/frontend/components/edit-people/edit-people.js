import { html, component, useEffect, useState } from "haunted";
import { ref } from "lit-html/directives/ref.js";
import { keyed } from "lit/directives/keyed.js";
import { getColumns } from "./table/columns.js";
import "../person-image.js";
import "./person-card.js";
import "./people-table.js";
import { useRovingFocusList } from "../../hooks/use-roving-focus-list.js";
import "./action-buttons.js";
import "./people-tabs.js";
import "./profile-modal.js";
import "../basic/modal.js";
import "../review-panel/review-panel.js";
import { usePeopleState } from "./hooks/use-people-state.js";
import { fetchPullRequestData, fetchPullRequests, generatePersonId, fetchReview, searchPeople, saveAndMerge, closePullRequest, fetchPeopleDirectory, deletePerson, patchPeopleData } from "../../api.js";
import { buildOtherNames } from "../../utils/name-utils.js";
import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import { blankPerson, resolvePeopleMatches } from "./people-editing.js";
import "../diff-panel/diff-panel.js";

const TAB = {
  directory: 'directory',
  current: 'current',
  pull_request: 'pull_request',
};

function activeTabFromSelection(selectedPullRequest) {
  if (selectedPullRequest === 'directory') return TAB.directory;
  if (selectedPullRequest) return TAB.pull_request;
  return TAB.current;
}

function updateTabParam(tab) {
  const p = new URLSearchParams(window.location.search);
  if (tab === 'directory') p.set('tab', 'directory');
  else if (tab == null) p.set('tab', 'current');
  else p.set('tab', tab.request_id);
  history.replaceState(null, '', `?${p}`);
}

function EditablePeopleList({ jurisdiction_ocdid, people = [], canDeletePeople = false, onSourceUrlsChange = () => {}, onPublished = () => {} }) {
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

  const [pullRequests, setPullRequests] = useState([]);
  const [pullRequestsLoading, setPullRequestsLoading] = useState(false);
  const [reviewData, setReviewData] = useState(null);
  const [error, setError] = useState(null);
  const [selectedPullRequest, setSelectedPullRequest] = useState(undefined);
  const [isLoading, setIsLoading] = useState(false);
  const [prStatus, setPrStatus] = useState(null);

  useEffect(() => {
    const status = selectedPullRequest?.pr?.status;
    if (status === "merged" || status === "closed") setPrStatus(status);
    else setPrStatus(null);
  }, [selectedPullRequest]);
  const [isMobile, setIsMobile] = useState(
    window.matchMedia("(max-width: 700px)").matches,
  );
  const [profileModal, setProfileModal] = useState({
    open: false,
    person: null,
    searchSuggestions: [],
  });
  const [resolvedMatches, setResolvedMatches] = useState({});
  const [directoryPeople, setDirectoryPeople] = useState([]);
  const [directoryLoading, setDirectoryLoading] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 700px)");
    const handler = (e) => setIsMobile(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  async function handleFetchPullRequests() {
    setPullRequestsLoading(true);
    try {
      const data = await fetchPullRequests(jurisdiction_ocdid);
      const prs = (data.data || []).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      setPullRequests(prs);
      const tabParam = new URLSearchParams(window.location.search).get('tab');
      if (tabParam === 'directory') {
        setSelectedPullRequest('directory');
      } else if (tabParam === 'current') {
        setSelectedPullRequest(null);
      } else if (tabParam) {
        setSelectedPullRequest(prs.find(pr => pr.request_id === tabParam) ?? (prs.length > 0 ? prs[0] : null));
      } else {
        setSelectedPullRequest(prs.length > 0 ? prs[0] : null);
      }
    } catch {
      setSelectedPullRequest(null);
    } finally {
      setPullRequestsLoading(false);
    }
  }

  useEffect(() => {
    handleFetchPullRequests();
  }, []);

  const {
    refs: cardRefs,
    focusedIdx,
    setFocusedIdx,
    handleKeyDown,
  } = useRovingFocusList(currentPeople.length);

  const activeTab = activeTabFromSelection(selectedPullRequest);

  useEffect(() => {
    if (selectedPullRequest === undefined) return;
    setPrStatus(null);
    onSourceUrlsChange(activeTab === TAB.pull_request ? selectedPullRequest.sources ?? [] : []);
    if (activeTab === TAB.directory) {
      handleFetchDirectory();
    } else if (activeTab === TAB.current) {
      assignPeople(people);
      setReviewData(null);
      setResolvedMatches({});
    } else {
      handleSelectedPullRequestData(selectedPullRequest);
    }
  }, [selectedPullRequest]);

  async function handleConfirmDelete() {
    const person = deleteConfirm;
    setDeleteConfirm(null);
    try {
      await deletePerson(person._id);
      setDirectoryPeople(prev => prev.filter(p => p._id !== person._id));
    } catch (err) {
      setError("Failed to delete person.");
      console.error(err);
    }
  }

  async function handleFetchDirectory() {
    setDirectoryLoading(true);
    try {
      const data = await fetchPeopleDirectory(jurisdiction_ocdid);
      setDirectoryPeople(data.data ?? []);
    } catch (err) {
      setError("Failed to load directory.");
      console.error(err);
    } finally {
      setDirectoryLoading(false);
    }
  }

  async function handleSelectedPullRequestData(pullRequest) {
    if (!pullRequest) return;
    try {
      setIsLoading(true);
      const [data, review] = await Promise.all([
        fetchPullRequestData(jurisdiction_ocdid, pullRequest.request_id),
        fetchReview(pullRequest.request_id),
      ]);
      const scrapedPeople = data?.data ?? [];
      setReviewData(review?.data || null);

      const { tagged, matchMap } = await resolvePeopleMatches(jurisdiction_ocdid, scrapedPeople);
      if (tagged.length) assignPeople(tagged);
      setResolvedMatches(matchMap);
    } catch (err) {
      setError("Failed to load pull request data.");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleAdd() {
    const person_id = await generatePersonId();
    addPerson(blankPerson(person_id, jurisdiction_ocdid, people));
  }

  async function handlePublish() {
    const request_id = selectedPullRequest?.request_id;
    const prNumber = selectedPullRequest?.pr?.number;
    if (!prNumber) return;
    setPrStatus("loading_merge");
    try {
      await saveAndMerge(prNumber, request_id, jurisdiction_ocdid, dirty ? peopleToSubmit : null);
      setPrStatus("merged");
      onPublished();
    } catch {
      setPrStatus("error");
      setError("Failed to merge pull request.");
    }
  }

  async function handleOpenPR() {
    setPrStatus("loading_merge");
    try {
      const { data } = await patchPeopleData(jurisdiction_ocdid, peopleToSubmit);
      await saveAndMerge(data.pr_number, data.request_id, jurisdiction_ocdid, null);
      setPrStatus("merged");
      onPublished();
    } catch (err) {
      setPrStatus("error");
      setError(err.message || "Failed to publish.");
    }
  }

  async function handleClosePR() {
    const request_id = selectedPullRequest?.request_id;
    const prNumber = selectedPullRequest?.pr?.number;
    if (!prNumber) return;
    setPrStatus("loading_close");
    try {
      await closePullRequest(request_id, prNumber);
      setPrStatus("closed");
    } catch {
      setPrStatus("error");
      setError("Failed to close pull request.");
    }
  }

function handleCardKeyDown(e, idx, key) {
    handleKeyDown(e, idx);
    if (e.target !== e.currentTarget) return;
    if ((e.key === " " || e.key === "Enter") && key) {
      e.preventDefault();
      toggleSelect(key);
    }
  }

  async function openProfileModal(person) {
    const resolved = resolvedMatches[person.id];
    let existingPerson = people.find(p => p.id === person.id) ?? resolved?.person ?? null;
    let nameMatches = [];

    if (resolved && resolved.id !== person.id) {
      if (resolved.ambiguous) {
        nameMatches = resolved.person;
      } else {
        existingPerson = resolved.person;
        nameMatches = [resolved.person];
      }
    }

    setProfileModal({ open: true, person, existingPerson, nameMatches, searchSuggestions: [], jurisdictionOcdid: jurisdiction_ocdid });

    if (person._isNew && person.name) {
      try {
        const result = await searchPeople(jurisdiction_ocdid, person.name);
        setProfileModal(prev => ({ ...prev, searchSuggestions: result.data ?? [] }));
      } catch {
        // non-blocking
      }
    }
  }

  function handleLinkPerson(e) {
    const { personId } = e.detail;
    const existingPerson = people.find(p => p.id === personId);
    const proposedPerson = profileModal.person;
    const other_names = buildOtherNames(proposedPerson, existingPerson);
    updatePerson(proposedPerson.id, { id: personId, _isNew: false, other_names });
    setProfileModal(prev => ({
      ...prev,
      person: { ...prev.person, id: personId, _isNew: false, other_names },
      existingPerson,
      nameMatches: [],
      searchSuggestions: [],
    }));
  }

  function formatDate(isoString) {
    if (!isoString) return "—";
    return isoString.slice(0, 10);
  }

  function renderDirectoryView() {
    if (directoryLoading) return html`<p>Loading directory...</p>`;
    if (!directoryPeople.length) return html`<p>No people found.</p>`;
    return html`
      <table>
        <thead>
          <tr>
            <th></th>
            <th></th>
            <th>Name</th>
            <th>Office</th>
            <th>Division</th>
            <th>Updated</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${directoryPeople.map(p => html`
            <tr>
              <td>
                <button
                  type="button"
                  class="secondary btn-sm"
                  @click=${() => setProfileModal({ open: true, person: p, existingPerson: null, nameMatches: [], searchSuggestions: [] })}
                >View</button>
              </td>
              <td @click=${() => setProfileModal({ open: true, person: p, existingPerson: null, nameMatches: [], searchSuggestions: [] })} style="cursor:pointer;">
                <person-image .person=${p}></person-image>
              </td>
              <td>${p.name}</td>
              <td>${p.office?.name ?? "—"}</td>
              <td>${p.office?.division_ocdid ?? "—"}</td>
              <td>${formatDate(p.updated_at)}</td>
              <td>
                <span class="status-badge status-badge--${p.status ?? 'current'}">
                  ${p.status ?? 'current'}
                </span>
              </td>
              ${canDeletePeople ? html`
                <td>
                  <button
                    type="button"
                    class="destructive btn-sm"
                    @click=${() => setDeleteConfirm(p)}
                  >Delete</button>
                </td>
              ` : html`<td></td>`}
            </tr>
          `)}
        </tbody>
      </table>
    `;
  }

  const activeSourceUrlMap = activeTab === TAB.pull_request
    ? buildSourceUrlMap(selectedPullRequest.sources ?? [])
    : new Map();

  function renderTableView() {
    return html`<civ-people-table
      .data=${currentPeople}
      .columns=${getColumns(openProfileModal, activeSourceUrlMap, { showOtherNames: activeTab === TAB.current })}
      @data-change=${handleTableDataChange}
      @reorder=${handleTableDataReorder}
    ></civ-people-table>`;
  }

  function renderCardView() {
    return html`<div
      class="grid"
      style="display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:1rem; align-items:stretch; width:100%;"
    >
      ${currentPeople.map((person, idx) =>
        keyed(
          person.id,
          html`
            <div role="listitem">
              <person-card
                tabIndex=${focusedIdx === idx ? "0" : "-1"}
                ${ref(cardRefs[idx])}
                @focus=${() => setFocusedIdx(idx)}
                @keydown=${(e) => handleCardKeyDown(e, idx, person.id)}
                .person=${person}
                .onSelect=${() => toggleSelect(person.id)}
                .onDelete=${() => handleDelete([person.id])}
                .onChange=${(field, value) =>
                  updatePerson(person.id, { [field]: value })}
                .onReset=${() => handleReset(person.id)}
              ></person-card>
            </div>
          `,
        ),
      )}
    </div>`;
  }

  function renderContent() {
    if (activeTab === TAB.directory) {
      return renderDirectoryView();
    }
    return html`
      ${activeTab === TAB.pull_request
        ? html`
            <a href=${selectedPullRequest.pr.url} target="_blank" class="contrast"
              >View Pull Request</a
            >
            <hr />
            <civ-review-panel
              .reviewData=${reviewData}
              .existing=${people}
              .pullRequest=${currentPeople}
            ></civ-review-panel>
          `
        : ""}
      <civ-people-action-buttons
        .onAdd=${handleAdd}
        .onMerge=${handleMerge}
        .onBulkDelete=${handleBulkDelete}
        .onReset=${activeTab === TAB.pull_request ? () => handleSelectedPullRequestData(selectedPullRequest) : handleReset}
        .onPublish=${activeTab === TAB.pull_request ? handlePublish : handleOpenPR}
        .onClosePR=${handleClosePR}
        .selectedPeople=${selectedPeople}
        .dirty=${dirty}
        .isLoading=${isLoading}
        .hasPullRequest=${activeTab === TAB.pull_request}
        .prStatus=${prStatus}
      ></civ-people-action-buttons>
      ${isLoading
        ? html`<div
            style="margin-bottom:1rem; padding:0.75em; background:#e0e0ff; border-radius:6px; color:#0000b3;"
          >
            Loading pull request data...
          </div>`
        : isMobile
          ? renderCardView()
          : renderTableView()}
    `;
  }

  return html`
    <civ-people-tabs
      .pullRequests=${pullRequests}
      .selectedPullRequest=${selectedPullRequest}
      .loading=${pullRequestsLoading}
      .onTabClick=${(pr) => { setSelectedPullRequest(pr); updateTabParam(pr); }}
    ></civ-people-tabs>


    ${error
      ? html`<div
          style="margin-bottom:1rem; padding:0.75em; background:#ffe0e0; border-radius:6px; color:#721c24;"
        >
          ${error}
        </div>`
      : ""}

    ${renderContent()}

    <profile-modal
      .open=${profileModal.open}
      .person=${profileModal.person}
      .existingPerson=${profileModal.existingPerson}
      .nameMatches=${profileModal.nameMatches ?? []}
      .searchSuggestions=${profileModal.searchSuggestions ?? []}
      .jurisdictionOcdid=${profileModal.jurisdictionOcdid ?? jurisdiction_ocdid}
      .readOnly=${activeTab === TAB.directory}
      @link-person=${handleLinkPerson}
      @close=${() =>
        setProfileModal({ open: false, person: null, existingPerson: null, searchSuggestions: [] })}
    ></profile-modal>

    <civ-modal
      .title=${"Delete person?"}
      .content=${deleteConfirm ? html`
        <div style="display:flex; align-items:center; gap:1rem;">
          <person-image .person=${deleteConfirm}></person-image>
          <span>${deleteConfirm.name}</span>
        </div>
        <p style="margin-top:1rem;">This cannot be undone.</p>
      ` : null}
      .footer=${html`
        <button type="button" class="secondary btn-sm" @click=${() => setDeleteConfirm(null)}>Cancel</button>
        <button type="button" class="destructive btn-sm" @click=${handleConfirmDelete}>Delete</button>
      `}
      .modalProps=${{ open: !!deleteConfirm, onClose: () => setDeleteConfirm(null) }}
    ></civ-modal>
  `;
}

customElements.define(
  "civ-editable-people-list",
  component(EditablePeopleList, {
    useShadowDOM: false,
    observedAttributes: ["jurisdiction_ocdid"],
  }),
);
