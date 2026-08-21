import { useState, useEffect } from "haunted";

export interface AsyncData<T> {
  data: T | null;
  error: string | null;
  /** Re-run the load. Call after a write, so the view shows what was stored. */
  reload: () => void;
}

/** Load data on mount, and again whenever `deps` change or `reload()` is called.
 *
 * `data === null` with no error means still loading — the caller decides how to say so.
 *
 * The reload token is here rather than in each component so the intent has a name. Lit's own
 * answer is `@lit/task`, a ReactiveController with a `run()`; it is a separate dependency and
 * more than this needs. The stricter alternative is not to reload at all — apply the write's
 * result to local state — but that only works when the response carries everything the view
 * shows, and these reads compute fields (holders, `_verified`) that a write does not return.
 */
export function useAsyncData<T>(load: () => Promise<T>, deps: unknown[]): AsyncData<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState(0);

  useEffect(() => {
    let current = true;
    setError(null);
    load()
      // Guard against a resolved fetch from a superseded dep set overwriting a newer one.
      .then((result) => current && setData(result))
      .catch((cause) => current && setError(String(cause)));
    return () => {
      current = false;
    };
  }, [...deps, token]);

  return { data, error, reload: () => setToken((previous) => previous + 1) };
}
