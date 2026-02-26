import { useState, useEffect } from "haunted";
const API_URL = __API_URL__;

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
        const res = await fetch(`${API_URL}/api/v1/me`, {
          credentials: "include"
        });
        if (!cancelled) {
          if (res.ok) {
            // Response: {"authenticated":true,"provider":"github","provider_user_id":"1234","email":"test@example.com","display_name":null,"first_name":null,"teams":null}
            const data = await res.json();
            if (data.authenticated) {
              setUser(data);
            }
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