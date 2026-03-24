import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import {
  getTodayReviewSession,
  createReviewSession,
  advanceReviewSession,
  mergePullRequest,
  closePullRequest,
} from "../../api.js";
import { pullRequestUrlToNumber } from "../../components/pull-request-card/pr-utils.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import "../../components/pull-request-card/index.js";
import "../../components/search-jurisdictions/select-state.js";

const DEFAULT_STATE_KEY = "review_state_code";
const DEFAULT_GOAL_KEY = "review_daily_goal";
const DEFAULT_STATE = "tx";
const DEFAULT_GOAL = 10;

const PAGE_STATE = {
  LOADING: "loading",
  IDLE: "idle",
  REVIEWING: "reviewing",
  DONE: "done",
};

function ReviewPage() {
  const [pageState, setPageState] = useState(PAGE_STATE.LOADING);
  const [stateCode, setStateCode] = useState(
    localStorage.getItem(DEFAULT_STATE_KEY) || DEFAULT_STATE
  );
  const [dailyGoal, setDailyGoal] = useState(
    parseInt(localStorage.getItem(DEFAULT_GOAL_KEY), 10) || DEFAULT_GOAL
  );
  const [session, setSession] = useState(null);
  const [currentJob, setCurrentJob] = useState(null);
  const [currentPeople, setCurrentPeople] = useState(null);
  const [entryNumber, setEntryNumber] = useState(0);
  const [prState, setPrState] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getTodayReviewSession(stateCode)
      .then((res) => {
        const data = res?.data;
        if (!data) {
          setPageState(PAGE_STATE.IDLE);
          return;
        }
        setSession(data.session);
        if (data.current_entry) {
          setCurrentJob(data.current_entry.job);
          setCurrentPeople({ existing: data.current_entry.existing, pull_request: data.current_entry.pull_request });
          setPageState(PAGE_STATE.REVIEWING);
        } else {
          setPageState(PAGE_STATE.IDLE);
        }
      })
      .catch(() => setPageState(PAGE_STATE.IDLE));
  }, []);

  const handleStateChange = (e) => {
    const newState = e.detail.state;
    setStateCode(newState);
    localStorage.setItem(DEFAULT_STATE_KEY, newState);
  };

  const handleGoalInput = (e) => {
    const val = parseInt(e.target.value, 10);
    if (!isNaN(val) && val > 0) {
      setDailyGoal(val);
      localStorage.setItem(DEFAULT_GOAL_KEY, String(val));
    }
  };

  const handleStartReview = async () => {
    setPageState(PAGE_STATE.LOADING);
    setError(null);
    try {
      const sessionRes = await createReviewSession(stateCode, dailyGoal);
      const newSession = sessionRes.data;
      setSession(newSession);
      await advance(newSession.id);
    } catch (err) {
      setError(err.message);
      setPageState(PAGE_STATE.IDLE);
    }
  };

  const advance = async (sessionId) => {
    const sid = sessionId ?? session?.id;
    setPrState(null);
    try {
      const res = await advanceReviewSession(sid);
      const data = res?.data;
      if (!data) {
        setPageState(PAGE_STATE.DONE);
        return;
      }
      setCurrentJob(data.job);
      setCurrentPeople({ existing: data.existing, pull_request: data.pull_request });
      setEntryNumber(data.entry_number);
      if (data.daily_goal && !session?.daily_goal) {
        setSession((s) => ({ ...s, daily_goal: data.daily_goal }));
      }
      setPageState(PAGE_STATE.REVIEWING);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleNext = () => advance();

  const handleMerge = async (event) => {
    const pullRequestNumber = event.detail.pullRequestNumber;
    setPrState({ status: PULL_REQUEST_STATUS.LOADING_MERGE });
    try {
      await mergePullRequest(pullRequestNumber);
      setPrState({ status: PULL_REQUEST_STATUS.MERGED });
      await advance();
    } catch (err) {
      setPrState({ status: PULL_REQUEST_STATUS.ERROR, error: err.message });
    }
  };

  const handleClose = async (event) => {
    const pullRequestNumber = event.detail.pullRequestNumber;
    setPrState({ status: PULL_REQUEST_STATUS.LOADING_CLOSE });
    try {
      await closePullRequest(pullRequestNumber);
      setPrState({ status: PULL_REQUEST_STATUS.CLOSED });
      await advance();
    } catch (err) {
      setPrState({ status: PULL_REQUEST_STATUS.ERROR, error: err.message });
    }
  };

  if (pageState === PAGE_STATE.LOADING) {
    return html`<main class="review-page"><p>Loading...</p></main>`;
  }

  if (pageState === PAGE_STATE.DONE) {
    return html`
      <main class="review-page">
        <p class="review-page__done">All caught up for ${stateCode.toUpperCase()} today.</p>
      </main>
    `;
  }

  if (pageState === PAGE_STATE.IDLE) {
    return html`
      <main class="review-page">
        ${error ? html`<p class="review-page__error">${error}</p>` : ""}
        <div class="review-page__setup">
          <div class="review-page__field-label">
            State
            <civ-select-state
              .selected=${stateCode}
              @state-change=${handleStateChange}
            ></civ-select-state>
          </div>
          <label class="review-page__field-label" for="review-daily-goal">
            Daily goal
            <input
              id="review-daily-goal"
              class="review-page__goal-input"
              type="number"
              min="1"
              .value=${String(dailyGoal)}
              @input=${handleGoalInput}
            />
          </label>
          <button class="btn review-page__start-btn" @click=${handleStartReview}>Start Session</button>
        </div>
      </main>
    `;
  }

  // REVIEWING
  const goal = session?.daily_goal ?? dailyGoal;
  const pullRequestNumber = pullRequestUrlToNumber(currentJob?.pull_request_url);

  return html`
    <main class="review-page" @onMerge=${handleMerge} @onClose=${handleClose}>
      <div class="review-page__toolbar">
        <span class="review-page__progress">${entryNumber} of ${goal}</span>
        <button class="btn-sm" @click=${handleNext}>Next →</button>
      </div>
      ${error ? html`<p class="review-page__error">${error}</p>` : ""}
      <pr-card
        .pr=${currentJob}
        .data=${currentPeople}
        .state=${prState}
      ></pr-card>
    </main>
  `;
}

customElements.define("review-page", component(ReviewPage, { useShadowDOM: false }));
