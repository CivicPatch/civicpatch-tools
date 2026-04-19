import { useState, useEffect } from "haunted";
import { fetchSummary } from "../api.js";

const summaryCache = new Map();

export function useSummary(enabled, stateCode = "") {
  const [summary, setSummary] = useState(summaryCache.get(stateCode) ?? null);

  useEffect(() => {
    if (!enabled) return;
    const cached = summaryCache.get(stateCode);
    if (cached) {
      setSummary(cached);
      return;
    }
    fetchSummary(stateCode)
      .then((data) => {
        summaryCache.set(stateCode, data);
        setSummary(data);
      })
      .catch(() => {});
  }, [enabled, stateCode]);

  return summary;
}
