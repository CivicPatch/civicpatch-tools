import { useState, useEffect } from "haunted";
const API_URL = __API_URL__;

const DEFAULT_PERMISSIONS = {
  JURISDICTION_PAGE: false,
  JURISDICTION_PAGE_SCRAPE: false
}

/**
 * useAuth - Haunted hook for authentication state.
 * Returns: { user, loading }
 */
export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [permissions, setPermissions] = useState(DEFAULT_PERMISSIONS)

  function teamsToPermissions(teams) {
    return {
      JURISDICTION_PAGE: teams.length > 0, // Any team under our org
      JURISDICTION_PAGE_SCRAPE: teams.includes("maintainers")
    }
  }

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
              setPermissions(teamsToPermissions(data.teams || []));
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

  return { user, loading, permissions };
}