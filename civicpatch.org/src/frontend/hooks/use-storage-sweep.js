import { useEffect } from "haunted";
import { sweepExpiredStorageDaily } from "../utils/storage-sweep.js";

// Call from a component that renders on every page — the sweep needs a frequent
// trigger, and the throttle inside it is what keeps that to one walk a day.
export function useStorageSweep() {
  useEffect(() => {
    sweepExpiredStorageDaily(localStorage, Date.now());
  }, []);
}
