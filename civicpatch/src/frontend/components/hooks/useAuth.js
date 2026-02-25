import { useState, useEffect } from "haunted";

/**
 * useAuth - Haunted hook for authentication state.
 * Returns: { user, loading }
 */
export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function checkAuth() {
      setLoading(true);
      try {
        // Replace with your actual REST API endpoint
        const res = await fetch("/api/auth/status");
        if (!cancelled) {
          if (res.ok) {
            const data = await res.json();
            setUser(data.user || null);
          } else {
            setUser(null);
          }
        }
      } catch (e) {
        if (!cancelled) setUser(null);
      }
      if (!cancelled) setLoading(false);
    }
    checkAuth();
    return () => { cancelled = true; };
  }, []);

  return { user, loading };
}