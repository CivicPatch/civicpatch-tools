import { useState, useEffect } from "haunted";

// Fallback for an unreachable server only — signed-out users get real
// permissions, since some capabilities are public.
const DENY_ALL = {};

// Module-level cache
let cachedAuth = null;
let cachedPromise = null;

async function fetchAuth() {
  if (cachedAuth) return cachedAuth;
  if (cachedPromise) return cachedPromise;

  cachedPromise = fetch(`/api/permissions`, { credentials: "include" })
    .then(async res => {
      if (res.ok) {
        const data = await res.json();
        cachedAuth = {
          user: data.authenticated ? data.data : null,
          permissions: data.data.permissions,
        };
      } else {
        cachedAuth = { user: null, permissions: DENY_ALL };
      }
      return cachedAuth;
    })
    .catch(() => {
      cachedAuth = { user: null, permissions: DENY_ALL };
      return cachedAuth;
    })
    .finally(() => {
      cachedPromise = null;
    });

  return cachedPromise;
}

/**
 * useAuth - Haunted hook for authentication state.
 * Returns: { user, loading, permissions }
 */
export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [permissions, setPermissions] = useState(DENY_ALL);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchAuth().then(auth => {
      if (!cancelled) {
        setUser(auth.user);
        setPermissions(auth.permissions);
        setLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, []);

  return { user, loading, permissions };
}
