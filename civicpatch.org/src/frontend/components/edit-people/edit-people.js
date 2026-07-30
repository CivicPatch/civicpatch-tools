import { html, component, useEffect, useState } from "haunted";
import { getColumns } from "./table/columns.js";
import "./people-table.js";
import "./person-edit-modal.ts";
import "./action-buttons.js";
import "./people-tabs.js";
import "../basic/modal.js";
import "../review-panel/review-panel.js";
import { usePeopleState } from "./hooks/use-people-state.js";
import { fetchPullRequestData, fetchPullRequests, generatePersonId, fetchReview, searchPeople, saveAndEnqueueMerge, closePullRequest, patchPeopleData } from "../../api.js";
import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import { emptyPerson, resolvePeopleMatches } from "./people-editing.js";
import "../diff-panel/diff-panel.js";

const TAB = {
  current: 'current',
  pull_request: 'pull_request',
};

function activeTabFromSelection(selectedPullRequest) {
  if (selectedPullRequest) return TAB.pull_request;
  return TAB.current;
}

function updateTabParam(tab) {
  const p = new URLSearchParams(window.location.search);
  if (tab == null) p.set('tab', 'current');
  else p.set('tab', tab.request_id);
  history.replaceState(null, '', `?${p}`);
}

function EditablePeopleList({ jurisdiction_ocdid, people = [], canClosePr = false, canEditCurrent = false, onSourceUrlsChange = () => {}, onPublished = () => {} }) {
  const {
    currentPeople,
    selectedPeople,
    changesById,
    removedIds,
    dirty,
    peoplePatch,
    assignPeople,
    addPerson,
    updatePerson,
    handleBulkRemove,
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
  const [resolvedMatches, setResolvedMatches] = useState({});
  const [editingPerson, setEditingPerson] = useState(null);
  const [editingCandidates, setEditingCandidates] = useState([]);

  function closeEdit() {
    setEditingPerson(null);
    setEditingCandidates([]);
  }

  function handlePersonSave(e) {
    updatePerson(e.detail.id, e.detail.updates);
    closeEdit();
  }

  // Existing-record candidates to offer for linking: ambiguous auto-matches, or
  // name-search hits for new people. Nothing for confident or no-match people.
  async function openEdit(person) {
    setEditingPerson(person);
    setEditingCandidates([]);
    const resolved = resolvedMatches[person.id];
    if (resolved?.ambiguous) {
      setEditingCandidates(resolved.person ?? []);
    } else if (person._isNew && person.name) {
      try {
        const result = await searchPeople(jurisdiction_ocdid, person.name);
        setEditingCandidates(result.data ?? []);
      } catch {
        // non-blocking
      }
    }
  }

  async function handleFetchPullRequests() {
    setPullRequestsLoading(true);
    try {
      const data = await fetchPullRequests(jurisdiction_ocdid);
      const prs = (data.data || []).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      setPullRequests(prs);
      const tabParam = new URLSearchParams(window.location.search).get('tab');
      if (tabParam === 'current') {
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

  const activeTab = activeTabFromSelection(selectedPullRequest);

  useEffect(() => {
    if (selectedPullRequest === undefined) return;
    setPrStatus(null);
    onSourceUrlsChange(activeTab === TAB.pull_request ? selectedPullRequest.sources ?? [] : []);
    if (activeTab === TAB.current) {
      assignPeople(people);
      setReviewData(null);
      setResolvedMatches({});
    } else {
      handleSelectedPullRequestData(selectedPullRequest);
    }
  }, [selectedPullRequest]);

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
    addPerson(emptyPerson(person_id, jurisdiction_ocdid));
  }

  async function handlePublish() {
    const request_id = selectedPullRequest?.request_id;
    const prNumber = selectedPullRequest?.pr?.number;
    if (!prNumber) return;
    setPrStatus("loading_merge");
    try {
      await saveAndEnqueueMerge(prNumber, request_id, jurisdiction_ocdid, dirty ? peoplePatch : null);
      setPrStatus("merged");
      onPublished();
    } catch (err) {
      setPrStatus("error");
      setError(err.message || "Failed to merge pull request.");
    }
  }

  async function handleOpenPR() {
    setPrStatus("loading_merge");
    try {
      const { data } = await patchPeopleData(jurisdiction_ocdid, peoplePatch);
      await saveAndEnqueueMerge(data.pr_number, data.request_id, jurisdiction_ocdid, null);
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


  const activeSourceUrlMap = activeTab === TAB.pull_request
    ? buildSourceUrlMap(selectedPullRequest.sources ?? [])
    : new Map();

  // Editing published data (the Current tab) opens a manual-edit PR, so it is
  // gated to maintainers. PR tabs stay open to anyone reviewing that PR.
  const canEdit = activeTab === TAB.pull_request || canEditCurrent;

  function renderTableView() {
    return html`<civ-people-table
      .data=${currentPeople}
      .columns=${getColumns(activeSourceUrlMap, { showOtherNames: activeTab === TAB.current, readOnly: true, onEdit: canEdit ? openEdit : null, changesById, removedIds })}
      @data-change=${handleTableDataChange}
      @reorder=${handleTableDataReorder}
    ></civ-people-table>`;
  }

  function renderContent() {
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
      ${canEdit ? html`<civ-people-action-buttons
        .onAdd=${handleAdd}
        .onMerge=${handleMerge}
        .onBulkDelete=${handleBulkRemove}
        .onReset=${activeTab === TAB.pull_request ? () => handleSelectedPullRequestData(selectedPullRequest) : handleReset}
        .onPublish=${activeTab === TAB.pull_request ? handlePublish : handleOpenPR}
        .onClosePR=${handleClosePR}
        .selectedPeople=${selectedPeople}
        .dirty=${dirty}
        .isLoading=${isLoading}
        .hasPullRequest=${activeTab === TAB.pull_request}
        .canClosePr=${canClosePr}
        .prStatus=${prStatus}
      ></civ-people-action-buttons>` : ""}
      ${isLoading
        ? html`<div
            style="margin-bottom:1rem; padding:0.75em; background:#e0e0ff; border-radius:6px; color:#0000b3;"
          >
            Loading pull request data...
          </div>`
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

    ${editingPerson ? html`
      <civ-person-edit-modal
        .person=${editingPerson}
        .jurisdictionOcdid=${jurisdiction_ocdid}
        .candidates=${editingCandidates}
        @save=${handlePersonSave}
        @cancel=${closeEdit}
      ></civ-person-edit-modal>
    ` : ""}
  `;
}

customElements.define(
  "civ-editable-people-list",
  component(EditablePeopleList, {
    useShadowDOM: false,
    observedAttributes: ["jurisdiction_ocdid"],
  }),
);
