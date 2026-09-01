import { useState } from "haunted";
import { publishReview, dismissReview } from "../api.js";
import { REVIEW_ACTION } from "../components/review-card/review-action.js";

type ActionState = {
  status: string;
  jurisdiction_name: string;
  error?: string;
};

export type ReviewLogEntry = {
  changeset_id: string;
  jurisdiction_name: string;
  status: string;
};

const LOGGED_ACTIONS = [
  REVIEW_ACTION.APPROVING,
  REVIEW_ACTION.APPROVED,
  REVIEW_ACTION.ERROR,
];

export function useReviewActions() {
  // Keyed on changeset_id: there is no pull request behind a scrape any more.
  const [actionState, setActionState] = useState<Record<string, ActionState>>({});

  const setStatus = (changesetId: string, jurisdictionName: string, status: string, error?: string) =>
    setActionState((prev) => ({
      ...prev,
      [changesetId]: { status, jurisdiction_name: jurisdictionName, ...(error ? { error } : {}) },
    }));

  // Run a review action, recording its lifecycle (loading -> done, or error) for the publish log.
  const track = async (opts: {
    changesetId: string;
    jurisdictionName: string;
    loading: string;
    done: string;
    run: () => Promise<unknown>;
  }): Promise<void> => {
    const { changesetId, jurisdictionName, loading, done, run } = opts;
    setStatus(changesetId, jurisdictionName, loading);
    try {
      await run();
      setStatus(changesetId, jurisdictionName, done);
    } catch (err: any) {
      setStatus(changesetId, jurisdictionName, REVIEW_ACTION.ERROR, err?.message ?? String(err));
    }
  };

  // Approving is a single synchronous call: the server writes the roster and stamps
  // published_at before responding, so there is no background half to poll. Still resolves
  // {ok:false, error} rather than throwing, so the review session can keep the reviewer
  // on a failed entry.
  const trackApprove = async (
    changesetId: string,
    jurisdictionOcdid: string,
    people: any[] | null,
    jurisdictionName: string,
  ): Promise<{ ok: boolean; error?: string }> => {
    setStatus(changesetId, jurisdictionName, REVIEW_ACTION.APPROVING);
    try {
      await publishReview(changesetId, jurisdictionOcdid, people);
    } catch (err: any) {
      const error = err?.message ?? String(err);
      setStatus(changesetId, jurisdictionName, REVIEW_ACTION.ERROR, error);
      return { ok: false, error };
    }
    setStatus(changesetId, jurisdictionName, REVIEW_ACTION.APPROVED);
    return { ok: true };
  };

  const trackReject = (changesetId: string, jurisdictionName: string): Promise<void> =>
    track({
      changesetId,
      jurisdictionName,
      loading: REVIEW_ACTION.REJECTING,
      done: REVIEW_ACTION.REJECTED,
      run: () => dismissReview(changesetId),
    });

  const entries: ReviewLogEntry[] = Object.entries(actionState)
    .filter(([, s]) => LOGGED_ACTIONS.includes(s.status))
    .map(([changesetId, s]) => ({
      changeset_id: changesetId,
      jurisdiction_name: s.jurisdiction_name,
      status: s.status,
    }));

  return { actionState, entries, trackApprove, trackReject };
}
