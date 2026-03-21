import { html, component, useEffect, useState } from "haunted";
import { ref } from "lit-html/directives/ref.js";
import { keyed } from "lit/directives/keyed.js";
import { getColumns } from "./table/columns.js";
import "../person-image.js";
import "./person-card.js";
import "../basic/table/table.js";
import { useRovingFocusList } from "../../hooks/use-roving-focus-list.js";
import "./action-buttons.js";
import "./pull-request-tabs.js";
import "./profile-modal.js";
import "../review-panel/review-panel.js";
import { usePeopleState } from "./hooks/use-people-state.js";
import { updatePullRequestData, fetchPullRequestData, fetchPullRequests, generatePersonId, batchResolvePeople, fetchReview, searchPeople, mergePullRequest, closePullRequest } from "../../api.js";
import "../diff-panel/diff-panel.js";

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

  const [pullRequests, setPullRequests] = useState([]);
  const [pullRequestsLoading, setPullRequestsLoading] = useState(false);
  const [reviewData, setReviewData] = useState(null);
  const [error, setError] = useState(null);
  const [selectedPullRequest, setSelectedPullRequest] = useState(undefined);
  const [notice, setNotice] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [prStatus, setPrStatus] = useState(null);
  const [isMobile, setIsMobile] = useState(
    window.matchMedia("(max-width: 700px)").matches,
  );
  const [profileModal, setProfileModal] = useState({
    open: false,
    person: null,
    searchSuggestions: [],
  });
  const [resolvedMatches, setResolvedMatches] = useState({});
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
      setSelectedPullRequest(prs.length > 0 ? prs[0] : null);
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

  useEffect(() => {
    if (selectedPullRequest === undefined) return;
    setPrStatus(null);
    if (!selectedPullRequest) {
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

      const resolved = await batchResolvePeople(jurisdiction_ocdid, scrapedPeople);
      const matchMap = {};
      const updatedPeople = scrapedPeople.map((p, i) => {
        const r = resolved.data[i];
        matchMap[p.id] = r;
        return { ...p, _isNew: !r?.person };
      });
      if (updatedPeople.length) assignPeople(updatedPeople);
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
      updated_at: new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00"),
    });
  }

  async function handlePublish() {
    const prNumber = selectedPullRequest?.pull_request_url?.split("/").pop();
    if (!prNumber) return;
    setPrStatus("loading_merge");
    try {
      await mergePullRequest(prNumber);
      setPrStatus("merged");
      setNotice("Pull request published.");
    } catch {
      setPrStatus("error");
      setError("Failed to publish pull request.");
    }
  }

  async function handleClosePR() {
    const prNumber = selectedPullRequest?.pull_request_url?.split("/").pop();
    if (!prNumber) return;
    setPrStatus("loading_close");
    try {
      await closePullRequest(prNumber);
      setPrStatus("closed");
    } catch {
      setPrStatus("error");
      setError("Failed to close pull request.");
    }
  }

  async function handleSubmit() {
    setIsLoading(true);
    const response = await updatePullRequestData(
      selectedPullRequest.request_id,
      selectedPullRequest.jurisdiction_ocdid,
      peopleToSubmit,
    );
    if (!response) {
      setError("Failed to submit changes.");
    } else {
      setNotice("Changes submitted.");
    }
    setIsLoading(false);
    return response;
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

    setProfileModal({ open: true, person, existingPerson, nameMatches, searchSuggestions: [] });

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
    const currentOtherNames = proposedPerson.other_names || [];
    const other_names = Array.from(new Set([
      ...currentOtherNames,
      ...(existingPerson?.name && existingPerson.name !== proposedPerson.name ? [existingPerson.name] : []),
    ]));
    updatePerson(proposedPerson.id, { id: personId, _isNew: false, other_names });
    setProfileModal(prev => ({
      ...prev,
      person: { ...prev.person, id: personId, _isNew: false, other_names },
      existingPerson,
      nameMatches: [],
      searchSuggestions: [],
    }));
  }

  function renderTableView() {
    return html`<civ-table
      .identifier=${"id"}
      .selectedIdentifiers=${selectedPeople}
      .canReorder=${true}
      .columns=${getColumns(openProfileModal)}
      .data=${currentPeople}
      @data-change=${handleTableDataChange}
      @reorder=${handleTableDataReorder}
    >
    </civ-table>`;
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

  return html`
    <civ-pull-request-tabs
      .pullRequests=${pullRequests}
      .selectedPullRequest=${selectedPullRequest}
      .loading=${pullRequestsLoading}
      .onTabClick=${(pr) => setSelectedPullRequest(pr)}
    ></civ-pull-request-tabs>

    ${selectedPullRequest
      ? html`
          <a href=${selectedPullRequest.pull_request_url} target="_blank" class="contrast"
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
      .onReset=${() =>
        selectedPullRequest
          ? handleSelectedPullRequestData(selectedPullRequest)
          : assignPeople(people)}
      .onSubmit=${handleSubmit}
      .onPublish=${handlePublish}
      .onClosePR=${handleClosePR}
      .selectedPeople=${selectedPeople}
      .dirty=${dirty}
      .isLoading=${isLoading}
      .notice=${notice}
      .hasPullRequest=${!!selectedPullRequest}
      .prStatus=${prStatus}
    ></civ-people-action-buttons>

    ${notice
      ? html`<div
          style="margin-bottom:1rem; padding:0.75em; background:#e0ffe0; border-radius:6px; color:#155724;"
        >
          ${notice}
        </div>`
      : ""}
    ${error
      ? html`<div
          style="margin-bottom:1rem; padding:0.75em; background:#ffe0e0; border-radius:6px; color:#721c24;"
        >
          ${error}
        </div>`
      : ""}
    ${isLoading
      ? html`<div
          style="margin-bottom:1rem; padding:0.75em; background:#e0e0ff; border-radius:6px; color:#0000b3;"
        >
          Loading pull request data...
        </div>`
      : isMobile
        ? renderCardView()
        : renderTableView()}

    <profile-modal
      .open=${profileModal.open}
      .person=${profileModal.person}
      .existingPerson=${profileModal.existingPerson}
      .nameMatches=${profileModal.nameMatches ?? []}
      .searchSuggestions=${profileModal.searchSuggestions ?? []}
      @link-person=${handleLinkPerson}
      @close=${() =>
        setProfileModal({ open: false, person: null, existingPerson: null, searchSuggestions: [] })}
    ></profile-modal>
  `;
}

customElements.define(
  "civ-editable-people-list",
  component(EditablePeopleList, {
    useShadowDOM: false,
    observedAttributes: ["jurisdiction_ocdid"],
  }),
);
