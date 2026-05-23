import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { createReviewSession, fetchActiveReviewSession, generatePersonId, batchResolvePeople } from "../../api.js";
import { buildOtherNames } from "../../utils/name-utils.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { useReviewSession, updateParams } from "./use-review-session.js";
import { usePullRequestActions } from "../../hooks/use-pull-request-actions.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import { usePeopleState } from "../../components/edit-people/hooks/use-people-state.js";
import "./review-landing.js";
import "./review-session.js";
import "../../components/publish-log/index.js";
import "./review-page.css";

const DEFAULT_STATE_KEY = "app:default-state";
const DEFAULT_GOAL_KEY = "review_daily_goal";
const DEFAULT_GOAL = 10;

const PAGE_STATE = {
  LOADING: "loading",
  IDLE: "idle",
  REVIEWING: "reviewing",
};

function getStateFromUrl() {
  return (new URLSearchParams(window.location.search).get("state") || "").toLowerCase();
}

function ReviewPage() {
  const [pageState, setPageState] = useState(PAGE_STATE.IDLE);
  const [defaultState] = useLocalStorage(DEFAULT_STATE_KEY, "");
  const stateCode = (getStateFromUrl() || defaultState || "").toLowerCase();
  const [dailyGoal, setDailyGoal] = useLocalStorage(DEFAULT_GOAL_KEY, DEFAULT_GOAL, { ttl: PERSIST_FOREVER });

  const { actionState, entries: publishLogEntries, trackMerge, trackClose } = usePullRequestActions();

  const {
    session, setSession,
    jurisdiction, pr, progress,
    prPeople, requestId,
    error, setError,
    stats,
    advance, back, endSession, merge, navigateTo, loadDirectPr, initSession,
    isReadOnly,
    sourceContentUrls, reviewData,
  } = useReviewSession(stateCode, {
    onReviewing: () => setPageState(PAGE_STATE.REVIEWING),
    onDone: () => setPageState(PAGE_STATE.IDLE),
    onIdle: () => setPageState(PAGE_STATE.IDLE),
    onMerge: trackMerge,
  });

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const prNumber = p.get("pull_request_number");
    if (prNumber) {
      setPageState(PAGE_STATE.LOADING);
      setError(null);
      loadDirectPr(parseInt(prNumber, 10))
        .then(() => fetchActiveReviewSession())
        .then((res) => {
          const active = res?.data;
          if (active && active.session_pull_request_numbers?.includes(parseInt(prNumber))) {
            initSession(active.session_id, active.daily_goal, active.resolved_entry_numbers ?? [], active.current_entry_number);
          }
        })
        .catch(() => {});
      return;
    }
    fetchActiveReviewSession()
      .then((res) => {
        const active = res?.data;
        if (!active) return;
        initSession(active.session_id, active.daily_goal, active.resolved_entry_numbers ?? [], active.current_entry_number);
        return advance(active.session_id, active.current_entry_number);
      })
      .catch(() => {});
  }, []);

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
  } = usePeopleState({ people: prPeople?.proposed ?? [] });

  async function handleAdd() {
    const person_id = await generatePersonId();
    const people = prPeople?.proposed ?? [];
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
      jurisdiction_ocdid: jurisdiction.ocdid,
      source_urls: last?.source_urls?.[0] ? [last.source_urls[0]] : [],
      updated_at: new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00"),
    });
  }

  function handleLinkPerson(e) {
    const { personId, proposedPerson, existingPeople } = e.detail;
    const existingPerson = existingPeople.find(p => p.id === personId);
    const other_names = buildOtherNames(proposedPerson, existingPerson);
    updatePerson(proposedPerson.id, { id: personId, _isNew: false, other_names });
  }

  useEffect(() => {
    const people = prPeople?.proposed ?? [];
    if (!people.length) {
      assignPeople([]);
      setResolvedMatches({});
      return;
    }
    const cleanPeople = people.map(({ _isNew, _dirty, _changes, _selected, _deleted, ...p }) => p);
    batchResolvePeople(jurisdiction.ocdid, cleanPeople)
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
  }, [prPeople]);

  // Cap at total reviewable today (already-resolved + still-available), not just remaining.
  // today_resolved can exceed available_count as merged PRs drop out of the pool.
  const maxReviewable = (stats.today_resolved ?? 0) + (stats.available_count ?? 0);
  const effectiveGoal = Math.max(
    maxReviewable > 0 ? Math.min(dailyGoal, maxReviewable) : dailyGoal,
    stats.claimed_count ?? 0
  );

  const handleGoalChange = (n) => {
    const clamped = maxReviewable > 0 ? Math.min(n, maxReviewable) : n;
    setDailyGoal(clamped);
  };

  const handleStartReview = async () => {
    setPageState(PAGE_STATE.LOADING);
    setError(null);
    try {
      const sessionRes = await createReviewSession(stateCode, effectiveGoal);
      const newSession = sessionRes.data;
      setSession(newSession);
      updateParams({ pull_request_number: null });
      await advance(newSession.id, newSession.next_entry_number);
    } catch (err) {
      setError(err.message);
      setPageState(PAGE_STATE.IDLE);
    }
  };

  const handleMerge = () => merge(dirty ? peopleToSubmit : null);

  const handleClosePr = async () => {
    if (!pr?.number || !requestId) return;
    trackClose(pr.number, requestId, jurisdiction?.name ?? `#${pr.number}`);
    await advance();
  };

  const isClosingPr = pr?.number != null && actionState[pr.number]?.status === PULL_REQUEST_STATUS.LOADING_CLOSE;

  const renderBody = () => {
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
        .onGoalChange=${handleGoalChange}
        .onStartReview=${handleStartReview}
      ></review-landing>`;
    }
    return html`<review-session
      .isReadOnly=${isReadOnly}
      .hasSession=${!!session}
      .progress=${{ ...progress, goal: session?.daily_goal ? session.daily_goal - (stats.today_resolved ?? 0) : 1 }}
      .jurisdiction=${jurisdiction}
      .pr=${pr}
      .error=${error}
      .isDirty=${dirty}
      .prPeople=${prPeople}
      .currentPeople=${currentPeople}
      .selectedPeople=${selectedPeople}
      .reviewData=${reviewData}
      .sourceContentUrls=${sourceContentUrls}

      .onMerge=${handleMerge}
      .onClosePr=${handleClosePr}
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

customElements.define("review-page", component(ReviewPage, { useShadowDOM: false }));
