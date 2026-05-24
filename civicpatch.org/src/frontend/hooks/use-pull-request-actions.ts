import { useState } from "haunted";
import { saveAndMerge, closePullRequest } from "../api.js";
import { PULL_REQUEST_STATUS } from "../components/pull-request-card/pull-request-status.js";

type ActionState = {
  status: string;
  jurisdiction_name: string;
  error?: string;
};

export type PublishLogEntry = {
  pull_request_number: number;
  jurisdiction_name: string;
  status: string;
};

const PUBLISH_LOG_STATUSES = [
  PULL_REQUEST_STATUS.LOADING_MERGE,
  PULL_REQUEST_STATUS.MERGED,
  PULL_REQUEST_STATUS.ERROR,
];

export function usePullRequestActions() {
  const [actionState, setActionState] = useState<Record<number, ActionState>>({});

  const setStatus = (pullRequestNumber: number, jurisdictionName: string, status: string, error?: string) =>
    setActionState((prev) => ({
      ...prev,
      [pullRequestNumber]: { status, jurisdiction_name: jurisdictionName, ...(error ? { error } : {}) },
    }));

  // Run a PR action, recording its lifecycle (loading -> done, or error) for the publish log.
  const track = async (opts: {
    pullRequestNumber: number;
    jurisdictionName: string;
    loading: string;
    done: string;
    run: () => Promise<unknown>;
  }): Promise<void> => {
    const { pullRequestNumber, jurisdictionName, loading, done, run } = opts;
    setStatus(pullRequestNumber, jurisdictionName, loading);
    try {
      await run();
      setStatus(pullRequestNumber, jurisdictionName, done);
    } catch (err: any) {
      setStatus(pullRequestNumber, jurisdictionName, PULL_REQUEST_STATUS.ERROR, err?.message ?? String(err));
    }
  };

  const trackMerge = (
    pullRequestNumber: number,
    requestId: string,
    jurisdictionOcdid: string,
    people: any[] | null,
    jurisdictionName: string,
  ): Promise<void> =>
    track({
      pullRequestNumber,
      jurisdictionName,
      loading: PULL_REQUEST_STATUS.LOADING_MERGE,
      done: PULL_REQUEST_STATUS.MERGED,
      run: () => saveAndMerge(pullRequestNumber, requestId, jurisdictionOcdid, people),
    });

  const trackClose = (
    pullRequestNumber: number,
    requestId: string,
    jurisdictionName: string,
  ): Promise<void> =>
    track({
      pullRequestNumber,
      jurisdictionName,
      loading: PULL_REQUEST_STATUS.LOADING_CLOSE,
      done: PULL_REQUEST_STATUS.CLOSED,
      run: () => closePullRequest(requestId, pullRequestNumber),
    });

  const entries: PublishLogEntry[] = Object.entries(actionState)
    .filter(([, s]) => PUBLISH_LOG_STATUSES.includes(s.status))
    .map(([prNumber, s]) => ({
      pull_request_number: parseInt(prNumber, 10),
      jurisdiction_name: s.jurisdiction_name,
      status: s.status,
    }));

  return { actionState, entries, trackMerge, trackClose };
}
