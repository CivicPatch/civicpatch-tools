import { useState } from "haunted";
import { publishReview, dismissReview } from "../api.js";
import { PULL_REQUEST_STATUS } from "../components/pull-request-card/pull-request-status.js";

type ActionState = {
  status: string;
  jurisdiction_name: string;
  error?: string;
};

export type PublishLogEntry = {
  request_id: string;
  jurisdiction_name: string;
  status: string;
};

const PUBLISH_LOG_STATUSES = [
  PULL_REQUEST_STATUS.LOADING_MERGE,
  PULL_REQUEST_STATUS.MERGED,
  PULL_REQUEST_STATUS.ERROR,
];

export function usePullRequestActions() {
  // Keyed on request_id, not a pull request number: a scrape that published straight to
  // open-data never had one, and those are the majority now.
  const [actionState, setActionState] = useState<Record<string, ActionState>>({});

  const setStatus = (requestId: string, jurisdictionName: string, status: string, error?: string) =>
    setActionState((prev) => ({
      ...prev,
      [requestId]: { status, jurisdiction_name: jurisdictionName, ...(error ? { error } : {}) },
    }));

  // Run a review action, recording its lifecycle (loading -> done, or error) for the publish log.
  const track = async (opts: {
    requestId: string;
    jurisdictionName: string;
    loading: string;
    done: string;
    run: () => Promise<unknown>;
  }): Promise<void> => {
    const { requestId, jurisdictionName, loading, done, run } = opts;
    setStatus(requestId, jurisdictionName, loading);
    try {
      await run();
      setStatus(requestId, jurisdictionName, done);
    } catch (err: any) {
      setStatus(requestId, jurisdictionName, PULL_REQUEST_STATUS.ERROR, err?.message ?? String(err));
    }
  };

  // Publishing is a single synchronous call now — the server writes the roster and stamps
  // published_at before responding, so there is no background half to poll. Still resolves
  // {ok:false, error} rather than throwing, so the review session can keep the reviewer
  // on a failed entry.
  const trackMerge = async (
    requestId: string,
    jurisdictionOcdid: string,
    people: any[] | null,
    jurisdictionName: string,
  ): Promise<{ ok: boolean; error?: string }> => {
    setStatus(requestId, jurisdictionName, PULL_REQUEST_STATUS.LOADING_MERGE);
    try {
      await publishReview(requestId, jurisdictionOcdid, people);
    } catch (err: any) {
      const error = err?.message ?? String(err);
      setStatus(requestId, jurisdictionName, PULL_REQUEST_STATUS.ERROR, error);
      return { ok: false, error };
    }
    setStatus(requestId, jurisdictionName, PULL_REQUEST_STATUS.MERGED);
    return { ok: true };
  };

  const trackClose = (requestId: string, jurisdictionName: string): Promise<void> =>
    track({
      requestId,
      jurisdictionName,
      loading: PULL_REQUEST_STATUS.LOADING_CLOSE,
      done: PULL_REQUEST_STATUS.CLOSED,
      run: () => dismissReview(requestId),
    });

  const entries: PublishLogEntry[] = Object.entries(actionState)
    .filter(([, s]) => PUBLISH_LOG_STATUSES.includes(s.status))
    .map(([requestId, s]) => ({
      request_id: requestId,
      jurisdiction_name: s.jurisdiction_name,
      status: s.status,
    }));

  return { actionState, entries, trackMerge, trackClose };
}
