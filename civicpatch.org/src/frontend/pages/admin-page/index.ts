import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { fetchAdminUsers, setUserRoles } from "../../api.js";
import { useAuth } from "../../hooks/useAuth.js";
import "./admin-page.css";

const SELF_LOCK_TOOLTIP = "To change your own roles, use `mise run grant_role`.";

// Mirror of schemas/common.py:Role — keep in sync if roles are added/removed.
const ROLES = ["default", "contributors", "maintainers", "admins"] as const;

type RoleName = (typeof ROLES)[number];

type AdminUser = {
  id: string;
  email: string | null;
  display_name: string | null;
  provider: string;
  provider_user_id: string;
  roles: string[];
};

type RowStatus = "idle" | "saving" | "saved" | "error";

type RowState = {
  pending: Set<RoleName>;
  status: RowStatus;
  error?: string;
};

function buildInitialRowState(users: AdminUser[]): Record<string, RowState> {
  const out: Record<string, RowState> = {};
  for (const u of users) {
    out[u.id] = { pending: new Set(u.roles as RoleName[]), status: "idle" };
  }
  return out;
}

function isDirty(user: AdminUser, row: RowState): boolean {
  if (row.pending.size !== user.roles.length) return true;
  for (const r of user.roles) {
    if (!row.pending.has(r as RoleName)) return true;
  }
  return false;
}

function AdminPage() {
  const { user: currentUser } = useAuth();
  const currentUserId: string | null = currentUser?.user_id ?? null;
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [rowState, setRowState] = useState<Record<string, RowState>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setLoadError(null);
    fetchAdminUsers()
      .then((result: { data: AdminUser[] }) => {
        setUsers(result.data);
        setRowState(buildInitialRowState(result.data));
      })
      .catch((err: Error) => setLoadError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const toggleRole = (userId: string, role: RoleName) => {
    setRowState((prev) => {
      const current = prev[userId];
      const next = new Set(current.pending);
      if (next.has(role)) next.delete(role);
      else next.add(role);
      return { ...prev, [userId]: { ...current, pending: next, status: "idle" } };
    });
  };

  const handleSave = async (user: AdminUser) => {
    const row = rowState[user.id];
    const newRoles = Array.from(row.pending);
    setRowState((prev) => ({ ...prev, [user.id]: { ...prev[user.id], status: "saving", error: undefined } }));
    try {
      await setUserRoles(user.id, newRoles);
      setUsers((prev) => prev.map((u) => (u.id === user.id ? { ...u, roles: newRoles } : u)));
      setRowState((prev) => ({ ...prev, [user.id]: { ...prev[user.id], status: "saved" } }));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setRowState((prev) => ({ ...prev, [user.id]: { ...prev[user.id], status: "error", error: message } }));
    }
  };

  return html`
    <main class="admin-page page-content">
      <h1 class="admin-page__title">User roles</h1>
      ${loading ? html`<p class="admin-page__status">Loading…</p>` : null}
      ${loadError ? html`<p class="admin-page__status admin-page__error">Failed to load users: ${loadError}</p>` : null}
      ${!loading && !loadError && users.length === 0 ? html`<p class="admin-page__status">No users.</p>` : null}
      ${!loading && !loadError && users.length > 0 ? html`
        <table class="admin-users-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Display name</th>
              <th>Roles</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            ${users.map((user) => {
              const row = rowState[user.id];
              const dirty = isDirty(user, row);
              const saving = row.status === "saving";
              const isSelf = currentUserId !== null && user.id === currentUserId;
              return html`
                <tr>
                  <td>
                    ${user.email ?? "—"}
                    ${isSelf ? html`<span class="admin-users-table__self-tag">you</span>` : null}
                  </td>
                  <td>${user.display_name ?? "—"}</td>
                  <td>
                    ${ROLES.map(
                      (role) => html`
                        <label class="admin-users-table__role-cell">
                          <input
                            type="checkbox"
                            .checked=${row.pending.has(role)}
                            ?disabled=${saving || isSelf}
                            title=${isSelf ? SELF_LOCK_TOOLTIP : ""}
                            @change=${() => toggleRole(user.id, role)}
                          />
                          ${role}
                        </label>
                      `
                    )}
                  </td>
                  <td>
                    ${isSelf ? null : html`
                      <button
                        class="admin-users-table__save-btn"
                        ?disabled=${!dirty || saving}
                        @click=${() => handleSave(user)}
                      >
                        ${saving ? "Saving…" : "Save"}
                      </button>
                    `}
                    ${row.status === "saved"
                      ? html`<span class="admin-users-table__row-status admin-users-table__row-status--saved">Saved</span>`
                      : null}
                    ${row.status === "error"
                      ? html`<span class="admin-users-table__row-status admin-users-table__row-status--error">${row.error}</span>`
                      : null}
                  </td>
                </tr>
              `;
            })}
          </tbody>
        </table>
      ` : null}
    </main>
  `;
}

customElements.define("admin-page", component(AdminPage, { useShadowDOM: false }));
export default AdminPage;
