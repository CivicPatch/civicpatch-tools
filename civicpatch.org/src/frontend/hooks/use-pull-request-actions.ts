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

  const trackMerge = async (
    pullRequestNumber: number,
    requestId: string,
    jurisdictionOcdid: string,
    people: any[] | null,
    jurisdictionName: string,
  ): Promise<void> => {
    setActionState((prev) => ({
      ...prev,
      [pullRequestNumber]: { status: PULL_REQUEST_STATUS.LOADING_MERGE, jurisdiction_name: jurisdictionName },
    }));
    try {
      await saveAndMerge(pullRequestNumber, requestId, jurisdictionOcdid, people);
      setActionState((prev) => ({
        ...prev,
        [pullRequestNumber]: { status: PULL_REQUEST_STATUS.MERGED, jurisdiction_name: jurisdictionName },
      }));
    } catch (err: any) {
      setActionState((prev) => ({
        ...prev,
        [pullRequestNumber]: {
          status: PULL_REQUEST_STATUS.ERROR,
          jurisdiction_name: jurisdictionName,
          error: err?.message ?? String(err),
        },
      }));
    }
  };

  const trackClose = async (
    pullRequestNumber: number,
    requestId: string,
    jurisdictionName: string,
  ): Promise<void> => {
    setActionState((prev) => ({
      ...prev,
      [pullRequestNumber]: { status: PULL_REQUEST_STATUS.LOADING_CLOSE, jurisdiction_name: jurisdictionName },
    }));
    try {
      await closePullRequest(requestId, pullRequestNumber);
      setActionState((prev) => ({
        ...prev,
        [pullRequestNumber]: { status: PULL_REQUEST_STATUS.CLOSED, jurisdiction_name: jurisdictionName },
      }));
    } catch (err: any) {
      setActionState((prev) => ({
        ...prev,
        [pullRequestNumber]: {
          status: PULL_REQUEST_STATUS.ERROR,
          jurisdiction_name: jurisdictionName,
          error: err?.message ?? String(err),
        },
      }));
    }
  };

  const entries: PublishLogEntry[] = Object.entries(actionState)
    .filter(([, s]) => PUBLISH_LOG_STATUSES.includes(s.status))
    .map(([prNumber, s]) => ({
      pull_request_number: parseInt(prNumber, 10),
      jurisdiction_name: s.jurisdiction_name,
      status: s.status,
    }));

  return { actionState, entries, trackMerge, trackClose };
}
