import { useState, useEffect } from "haunted";
const API_URL = __API_URL__;

const DEFAULT_PERMISSIONS = {
  JURISDICTION_PAGE: false,
  JURISDICTION_PAGE_SCRAPE_REMOTE: false,
  JURISDICTION_PAGE_SCRAPE_LOCAL: false
}

/**
 * useAuth - Haunted hook for authentication state.
 * Returns: { user, loading }
 */
export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [permissions, setPermissions] = useState(DEFAULT_PERMISSIONS)

  function toPermissions(permissions) {
    return {
      JURISDICTION_PAGE: permissions["can_view_jurisdiction_page"],
      JURISDICTION_PAGE_SCRAPE_REMOTE: permissions["can_scrape_remote"],
      JURISDICTION_PAGE_SCRAPE_LOCAL: permissions["can_scrape_local"]
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function checkAuth() {
      setLoading(true);
      try {
        const res = await fetch(`/api/permissions`, {
          credentials: "include"
        });

        if (!cancelled) {
          if (res.ok) {
            // Response: {"authenticated":true,"provider":"github","provider_user_id":"1234","email":"test@example.com","display_name":null,"first_name":null,"teams":null}
            const data = await res.json();
            if (data.authenticated) {
              setUser(data.data);
              setPermissions({
                ...DEFAULT_PERMISSIONS,
                ...toPermissions(data.permissions)
              });
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
