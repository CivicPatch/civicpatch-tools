import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { createReviewSession, generatePersonId } from "../../api.js";
import { useLocalStorage } from "../../hooks/use-local-storage.js";
import { useReviewSession, updateParams } from "./use-review-session.js";
import { usePeopleState } from "../../components/edit-people/hooks/use-people-state.js";
import "./review-landing.js";
import "./review-session.js";
import "./review-page.css";

const DEFAULT_STATE_KEY = "review_state_code";
const DEFAULT_GOAL_KEY = "review_daily_goal";
const DEFAULT_STATE = "tx";
const DEFAULT_GOAL = 10;

const PAGE_STATE = {
  LOADING: "loading",
  IDLE: "idle",
  REVIEWING: "reviewing",
};

function ReviewPage() {
  const [pageState, setPageState] = useState(PAGE_STATE.IDLE);
  const [stateCode, setStateCode] = useLocalStorage(DEFAULT_STATE_KEY, () => {
    const p = new URLSearchParams(window.location.search);
    return p.get("state") || DEFAULT_STATE;
  });
  const [dailyGoal, setDailyGoal] = useLocalStorage(DEFAULT_GOAL_KEY, DEFAULT_GOAL);

  const {
    session, setSession,
    pullRequestUrl, jurisdictionOcdid, jurisdictionName, reviewState, pullRequestStatus,
    currentPeople: prPeople,
    entryNumber,
    hasNext, hasPrev,
    prState, error, setError,
    stats,
    advance, back, pass, pause, merge, navigateTo,
    passedEntryNumbers, resolvedEntryNumbers, frontierEntry,
    sourceContentUrls, reviewData,
  } = useReviewSession(stateCode, {
    onReviewing: () => setPageState(PAGE_STATE.REVIEWING),
    onDone: () => setPageState(PAGE_STATE.IDLE),
    onIdle: () => setPageState(PAGE_STATE.IDLE),
  });

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
  } = usePeopleState({ people: prPeople?.pull_request ?? [] });

  async function handleAdd() {
    const person_id = await generatePersonId();
    const people = prPeople?.pull_request ?? [];
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
      jurisdiction_ocdid: jurisdictionOcdid,
      source_urls: last?.source_urls?.[0] ? [last.source_urls[0]] : [],
      updated_at: new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00"),
    });
  }

  function handleLinkPerson(proposedPerson, personId, existingPeople) {
    const existingPerson = existingPeople.find(p => p.id === personId);
    const currentOtherNames = proposedPerson.other_names || [];
    const other_names = Array.from(new Set([
      ...currentOtherNames,
      ...(existingPerson?.name && existingPerson.name !== proposedPerson.name ? [existingPerson.name] : []),
    ]));
    updatePerson(proposedPerson.id, { id: personId, _isNew: false, other_names });
  }

  useEffect(() => {
    assignPeople(prPeople?.pull_request ?? []);
  }, [prPeople]);

  const effectiveGoal = Math.max(
    stats.available_count > 0 ? Math.min(dailyGoal, stats.available_count) : dailyGoal,
    stats.claimed_count ?? 0
  );

  const handleStateChange = (e) => {
    const newState = e.detail.state;
    setStateCode(newState);
    updateParams({ state: newState });
  };

  const handleGoalChange = (n) => {
    const clamped = stats.available_count > 0 ? Math.min(n, stats.available_count) : n;
    setDailyGoal(clamped);
  };

  const handleStartReview = async () => {
    setPageState(PAGE_STATE.LOADING);
    setError(null);
    try {
      const sessionRes = await createReviewSession(stateCode, effectiveGoal);
      const newSession = sessionRes.data;
      setSession(newSession);
      updateParams({ state: stateCode });
      await advance(newSession.id);
    } catch (err) {
      setError(err.message);
      setPageState(PAGE_STATE.IDLE);
    }
  };

  const handleMerge = () => merge(dirty ? peopleToSubmit : null);

  if (pageState === PAGE_STATE.LOADING) {
    return html`<main class="review-page"><p>Loading...</p></main>`;
  }

  if (pageState === PAGE_STATE.IDLE) {
    return html`<review-landing
      .stateCode=${stateCode}
      .stats=${stats}
      .error=${error}
      .dailyGoal=${dailyGoal}
      .effectiveGoal=${effectiveGoal}
      .onStateChange=${handleStateChange}
      .onGoalChange=${handleGoalChange}
      .onStartReview=${handleStartReview}
    ></review-landing>`;
  }

  return html`<review-session
    .goal=${session.daily_goal}
    .entryNumber=${entryNumber}
    .hasNext=${hasNext}
    .hasPrev=${hasPrev}
    .prState=${prState}
    .error=${error}
    .isDirty=${dirty}
    .currentPeople=${prPeople}
    .tableData=${currentPeople}
    .selectedPeople=${selectedPeople}
    .reviewData=${reviewData}
    .sourceContentUrls=${sourceContentUrls}
    .passedEntryNumbers=${passedEntryNumbers}
    .resolvedEntryNumbers=${resolvedEntryNumbers}
    .frontierEntry=${frontierEntry}
    .pullRequestUrl=${pullRequestUrl}
    .jurisdictionOcdid=${jurisdictionOcdid}
    .jurisdictionName=${jurisdictionName}
    .reviewState=${reviewState}
    .pullRequestStatus=${pullRequestStatus}

    .onMerge=${handleMerge}
    .onAdvance=${advance}
    .onBack=${back}
    .onPass=${pass}
    .onNavigateTo=${navigateTo}
    .onPause=${pause}
    .onTableDataChange=${handleTableDataChange}
    .onTableReorder=${handleTableDataReorder}
    .onPeopleMerge=${handlePeopleMerge}
    .onBulkDelete=${handleBulkDelete}
    .onReset=${handleResetAll}
    .onAdd=${handleAdd}
    .onLinkPerson=${handleLinkPerson}
  ></review-session>`;
}

customElements.define("review-page", component(ReviewPage, { useShadowDOM: false }));
