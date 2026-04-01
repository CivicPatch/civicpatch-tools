import { useState, useEffect } from "haunted";

const DEFAULT_PERMISSIONS = {
  JURISDICTION_PAGE: false,
  JURISDICTION_PAGE_SCRAPE_REMOTE: false,
  JURISDICTION_PAGE_SCRAPE_LOCAL: false,
  DIRECTORY_DELETE: false,
};

// Module-level cache
let cachedAuth = null;
let cachedPromise = null;

function toPermissions(permissions) {
  return {
    JOBS_PAGE: permissions["can_view_jobs_page"],
    JOBS_PAGE_ERRORS: permissions["can_view_jobs_page_errors"],
    ISSUES_PAGE: permissions["can_view_issues_page"],
    JURISDICTION_PAGE: permissions["can_view_jurisdiction_page"],
    JURISDICTION_PAGE_SCRAPE_REMOTE: permissions["can_scrape_remote"],
    JURISDICTION_PAGE_SCRAPE_LOCAL: permissions["can_scrape_local"],
    DIRECTORY_DELETE: permissions["can_delete_directory_person"],
  }
}

async function fetchAuth() {
  if (cachedAuth) return cachedAuth;
  if (cachedPromise) return cachedPromise;

  cachedPromise = fetch(`/api/permissions`, { credentials: "include" })
    .then(async res => {
      if (res.ok) {
        const data = await res.json();
        if (data.authenticated) {
          cachedAuth = {
            user: data.data,
            permissions: {
              ...DEFAULT_PERMISSIONS,
              ...toPermissions(data.permissions)
            }
          };
        } else {
          cachedAuth = { user: null, permissions: DEFAULT_PERMISSIONS };
        }
      } else {
        cachedAuth = { user: null, permissions: DEFAULT_PERMISSIONS };
      }
      return cachedAuth;
    })
    .catch(() => {
      cachedAuth = { user: null, permissions: DEFAULT_PERMISSIONS };
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
  const [permissions, setPermissions] = useState(DEFAULT_PERMISSIONS);

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
