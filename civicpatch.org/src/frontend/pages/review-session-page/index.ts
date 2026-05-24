import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { generatePersonId, batchResolvePeople } from "../../api.js";
import { buildOtherNames } from "../../utils/name-utils.js";
import { useLocalStorage } from "../../hooks/use-local-storage.js";
import { usePullRequestActions } from "../../hooks/use-pull-request-actions.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import { usePeopleState } from "../../components/edit-people/hooks/use-people-state.js";
import { useReviewSession, landingUrl, STATE_PARAM } from "./use-review-session.js";
import { StateKind } from "./review-state.js";
import "../review-page/review-session.js";
import "../../components/publish-log/index.js";
import "../review-page/review-page.css";

const DEFAULT_STATE_KEY = "app:default-state";

function getStateFromUrl() {
  return (new URLSearchParams(window.location.search).get(STATE_PARAM) || "").toLowerCase();
}

function ReviewSessionPage() {
  const [defaultState] = useLocalStorage(DEFAULT_STATE_KEY, "");
  const stateCode = (getStateFromUrl() || defaultState || "").toLowerCase();

  const { actionState, entries: publishLogEntries, trackMerge, trackClose } = usePullRequestActions();
  const { fsm, stats, advance, back, navigateTo, merge, closePr, endSession } = useReviewSession(stateCode, {
    trackMerge,
    trackClose,
  });

  const reviewing = fsm.kind === StateKind.REVIEWING ? fsm : null;
  const currentEntry = reviewing?.current_entry ?? null;
  const session = reviewing?.session ?? null;

  const [resolvedMatches, setResolvedMatches] = useState({});

  const {
    currentPeople,
    dirty,
    peopleToSubmit,
    selectedPeople,
    assignPeople,
    addPerson,
    updatePerson,
    handleTableDataChange,
    handleTableDataReorder,
    handleBulkDelete,
    handleMerge: handlePeopleMerge,
    handleResetAll,
  } = usePeopleState({ people: currentEntry?.pr_people?.proposed ?? [] });

  async function handleAdd() {
    const person_id = await generatePersonId();
    const people = currentEntry?.pr_people?.proposed ?? [];
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
      jurisdiction_ocdid: currentEntry?.jurisdiction?.ocdid,
      source_urls: last?.source_urls?.[0] ? [last.source_urls[0]] : [],
      updated_at: new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00"),
    });
  }

  function handleLinkPerson(e) {
    const { personId, proposedPerson, existingPeople } = e.detail;
    const existingPerson = existingPeople.find((p) => p.id === personId);
    const other_names = buildOtherNames(proposedPerson, existingPerson);
    updatePerson(proposedPerson.id, { id: personId, _isNew: false, other_names });
  }

  useEffect(() => {
    const people = currentEntry?.pr_people?.proposed ?? [];
    const jurisdictionOcdid = currentEntry?.jurisdiction?.ocdid;
    if (!people.length || !jurisdictionOcdid) {
      assignPeople([]);
      setResolvedMatches({});
      return;
    }
    const cleanPeople = people.map(({ _isNew, _dirty, _changes, _selected, _deleted, ...p }) => p);
    batchResolvePeople(jurisdictionOcdid, cleanPeople)
      .then((resolved) => {
        const matchMap = {};
        const tagged = people.map((p, i) => {
          const r = resolved.data[i];
          matchMap[p.id] = r;
          return { ...p, _isNew: !r?.person };
        });
        assignPeople(tagged);
        setResolvedMatches(matchMap);
      })
      .catch(() => {
        assignPeople(people);
        setResolvedMatches({});
      });
  }, [currentEntry?.pr_people]);

  const handleMerge = () => merge(dirty ? peopleToSubmit : null);

  const prNumber = currentEntry?.pr?.number;
  const isClosingPr = prNumber != null && actionState[prNumber]?.status === PULL_REQUEST_STATUS.LOADING_CLOSE;

  const progress = reviewing
    ? {
        entryNumber: reviewing.entry_number,
        hasPrev: reviewing.entry_number > 1,
        resolvedEntryNumbers: reviewing.resolved_entry_numbers,
        frontierEntry: reviewing.frontier_entry,
        goal: session?.daily_goal ? session.daily_goal - (stats.today_resolved ?? 0) : 1,
      }
    : null;

  const renderBody = () => {
    if (fsm.kind === StateKind.LOADING) {
      return html`<main class="review-page"><p>Loading...</p></main>`;
    }
    if (fsm.kind === StateKind.ERROR) {
      return html`<main class="review-page">
        <p class="review-page__error">${fsm.message}</p>
        <a class="btn btn-sm" href=${landingUrl(stateCode)}>Back to review</a>
      </main>`;
    }
    return html`<review-session
      .currentEntry=${currentEntry}
      .hasSession=${session != null}
      .progress=${progress}
      .error=${null}
      .isDirty=${dirty}
      .currentPeople=${currentPeople}
      .selectedPeople=${selectedPeople}
      .onMerge=${handleMerge}
      .onClosePr=${closePr}
      .isClosingPr=${isClosingPr}
      .onAdvance=${advance}
      .onBack=${back}
      .onNavigateTo=${navigateTo}
      .onEndSession=${endSession}
      .onTableDataChange=${handleTableDataChange}
      .onTableReorder=${handleTableDataReorder}
      .onPeopleMerge=${handlePeopleMerge}
      .onBulkDelete=${handleBulkDelete}
      .onReset=${handleResetAll}
      .onAdd=${handleAdd}
      @link-person=${handleLinkPerson}
      .resolvedMatches=${resolvedMatches}
    ></review-session>`;
  };

  return html`
    ${renderBody()}
    <civ-publish-log .entries=${publishLogEntries}></civ-publish-log>
  `;
}

customElements.define("review-session-page", component(ReviewSessionPage, { useShadowDOM: false }));
