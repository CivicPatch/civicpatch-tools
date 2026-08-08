import { useEffect, useState } from "haunted";
import { fetchLocalStatus, fetchStateCoverageSummary } from "../../api.js";
import { getNeedsReviewCount } from "../../utils/coverage-utils.js";

// Both reads are keyed on the selected state and both reset when it clears, so they
// belong to one hook rather than two effects that must be kept in step.
export function useStateCoverage(selectedState: string) {
  const [localStatus, setLocalStatus] = useState<Record<string, unknown>>({});
  const [toReviewCount, setToReviewCount] = useState(0);

  useEffect(() => {
    if (!selectedState) {
      setLocalStatus({});
      setToReviewCount(0);
      return;
    }
    fetchLocalStatus(selectedState)
      .then((d: any) => setLocalStatus(d.data ?? {}))
      .catch(() => {});
    fetchStateCoverageSummary(selectedState)
      .then((d: any) => setToReviewCount(getNeedsReviewCount(d.data)))
      .catch(() => {});
  }, [selectedState]);

  return { localStatus, toReviewCount };
}
