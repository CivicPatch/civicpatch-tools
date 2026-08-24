import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import { dateStringToFriendly, durationBetween } from "../../../utils/date-utils.js";
import { fetchTemporalWorkflowState } from "../../../api.js";
import "../../../components/status-badge.js";

// Temporal state only matters when something is wrong: a run on attempt 1 says nothing the
// progress bar does not. So a healthy run is checked rarely — often enough to notice it going
// bad — and a retrying one is followed closely, because that is when the answer changes and
// when someone is actually watching it.
const HEALTHY_POLL_MS = 30000;
const RETRYING_POLL_MS = 5000;

// A page left open in a background tab is nobody watching. Resumes on the next visible tick.
const isVisible = () => document.visibilityState !== "hidden";

type TemporalWorkflowState = {
  activity: string | null;
  attempt: number;
  retrying: boolean;
  next_retry_seconds: number | null;
  last_failure: string | null;
};

type ScrapeInProgressProps = {
  scrape: any;
  canCancel: boolean;
  canViewTemporalWorkflowState: boolean;
  onCancel: (requestId: string) => void;
  temporalUrl: string | null;
};

// "trigger_github_action, attempt 7, next in 42s — 503 from GitHub" — the shape a stuck run
// takes. A healthy run is just the activity and its attempt, which is why the retry clause
// and the failure are appended only when they exist.
const describeTemporalWorkflow = (state: TemporalWorkflowState): string => {
  const parts = [`${state.activity ?? "starting"}, attempt ${state.attempt}`];
  if (state.retrying && state.next_retry_seconds != null) {
    parts[0] += `, next in ${state.next_retry_seconds}s`;
  }
  if (state.last_failure) parts.push(state.last_failure);
  return parts.join(" — ");
};

function ScrapeInProgress({ scrape, canCancel, canViewTemporalWorkflowState, onCancel, temporalUrl }: ScrapeInProgressProps) {
  const [temporal, setTemporal] = useState<TemporalWorkflowState | null>(null);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    // Admin-only, so non-admins never poll: the server would reject it anyway, and a
    // rejected request every few seconds is noise in everyone else's console.
    if (!scrape?.request_id || !canViewTemporalWorkflowState) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    // setTimeout rather than setInterval: the delay depends on the answer, so it can only be
    // chosen after each response.
    const scheduleNext = (state: TemporalWorkflowState | null) => {
      if (cancelled) return;
      timer = setTimeout(poll, state?.retrying ? RETRYING_POLL_MS : HEALTHY_POLL_MS);
    };

    const poll = () => {
      if (!isVisible()) return scheduleNext(temporal);
      fetchTemporalWorkflowState(scrape.request_id)
        .then((state: TemporalWorkflowState | null) => {
          if (cancelled) return;
          setTemporal(state);
          scheduleNext(state);
        })
        .catch(() => scheduleNext(null));
    };

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [scrape?.request_id, canViewTemporalWorkflowState]);

  if (!scrape) return html``;

  const handleCancel = () => {
    setCancelling(true);
    onCancel(scrape.request_id);
  };

  return html`
    <style>
      .sip-section {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
      }
      .sip-title {
        margin: 0;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--pico-muted-color);
        padding-bottom: 0.4rem;
        border-bottom: 1px solid var(--pico-muted-border-color);
      }
      .sip-head {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.5rem;
        --badge-font-size: 0.72rem;
      }
      .sip-timing {
        font-size: 0.72rem;
        color: var(--pico-muted-color);
      }
      .sip-progress {
        display: block;
        width: 100%;
        height: 0.3rem;
        margin: 0;
      }
      /* Supporting detail, not a headline: it only matters when something is wrong. */
      .sip-foot {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.68rem;
        color: var(--pico-muted-color);
      }
      .sip-temporal {
        font-family: var(--pico-font-family-monospace, monospace);
        overflow-wrap: anywhere;
      }
      .sip-cancel {
        font-size: 0.68rem;
        padding: 0.12rem 0.45rem;
        cursor: pointer;
      }
    </style>

    <div class="sip-section">
      <h4 class="sip-title">In progress</h4>

      <div class="sip-head">
        <civ-status-badge
          label="${scrape.pipeline_run_status}"
          bg="var(--pico-info-background)"
          color="var(--pico-info-color)"
        ></civ-status-badge>
        <span class="sip-timing">
          started ${dateStringToFriendly(scrape.created_at)} —
          running ${durationBetween(scrape.created_at, scrape.updated_at)}
        </span>
      </div>

      <progress class="sip-progress" value=${scrape.pipeline_run_progress ?? 0} max="100"></progress>

      <div class="sip-foot">
        ${canCancel
          ? html`<button class="sip-cancel" ?disabled=${cancelling} @click=${handleCancel}>
              ${cancelling ? "Cancelling…" : "Cancel"}
            </button>`
          : null}
        ${temporal ? html`<span class="sip-temporal">${describeTemporalWorkflow(temporal)}</span>` : null}
        ${temporalUrl
          ? html`<a href=${temporalUrl} target="_blank" rel="noopener">Temporal ↗</a>`
          : null}
      </div>
    </div>
  `;
}

customElements.define(
  "civ-scrape-in-progress",
  component(ScrapeInProgress as any, { useShadowDOM: false }),
);
