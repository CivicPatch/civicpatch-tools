import { useState, useEffect } from "haunted";
import { fetchSummary } from "../api.js";

let cachedSummary = null;

export function useSummary(enabled) {
  const [summary, setSummary] = useState(cachedSummary);

  useEffect(() => {
    if (!enabled) return;
    if (cachedSummary) {
      setSummary(cachedSummary);
      return;
    }
    fetchSummary()
      .then((data) => {
        cachedSummary = data;
        setSummary(data);
      })
      .catch(() => {});
  }, [enabled]);

  return summary;
}
