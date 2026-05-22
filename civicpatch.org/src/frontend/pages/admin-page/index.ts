import { html } from "lit-html";
import { component, useState, useEffect, useRef } from "haunted";
import { fetchAdminUsers, setUserRoles } from "../../api.js";
import { useAuth } from "../../hooks/useAuth.js";
import { ROLES_META, getRoleMeta, type RoleKey, type RoleMeta } from "./roles-meta.js";
import type { ConfirmRoleContext } from "./confirm-role-modal.js";
import "./role-chip.js";
import "./status-toast.js";
import "./confirm-role-modal.js";
import "./admin-page.css";

const SELF_LOCK_TOOLTIP = "To change your own roles, use `mise run grant_role`.";
const TOAST_TIMEOUT_MS = 10_000;

type AdminUser = {
  id: string;
  email: string | null;
  display_name: string | null;
  provider: string;
  provider_user_id: string;
  roles: string[];
};

function isManagedRole(role: string): role is RoleKey {
  return ROLES_META.some((m) => m.key === role);
}

// Non-managed roles (e.g. legacy "default") are preserved verbatim on every
// PUT so chip toggles don't accidentally strip them from user_roles.
function preservedRolesOf(user: AdminUser): string[] {
  return user.roles.filter((r) => !isManagedRole(r));
}

function composeNewRoles(user: AdminUser, role: RoleKey, action: "add" | "remove"): string[] {
  const preserved = preservedRolesOf(user);
  const managed = new Set(user.roles.filter(isManagedRole) as RoleKey[]);
  if (action === "add") managed.add(role);
  else managed.delete(role);
  return [...preserved, ...managed];
}

function changedMessage(user: AdminUser, meta: RoleMeta, action: "add" | "remove"): string {
  const who = user.email ?? user.display_name ?? "user";
  const verb = action === "add" ? "Granted" : "Removed";
  const prep = action === "add" ? "to" : "from";
  return `${verb} ${meta.label} ${prep} ${who}`;
}

function AdminPage() {
  const { user: currentUser } = useAuth();
  const currentUserId: string | null = currentUser?.user_id ?? null;

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<number | null>(null);

  const [pendingConfirm, setPendingConfirm] = useState<ConfirmRoleContext | null>(null);

  useEffect(() => {
    setLoading(true);
    setLoadError(null);
    fetchAdminUsers()
      .then((result: { data: AdminUser[] }) => setUsers(result.data))
      .catch((err: Error) => setLoadError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    return () => {
      if (toastTimer.current !== null) window.clearTimeout(toastTimer.current);
    };
  }, []);

  const dismissToast = () => {
    if (toastTimer.current !== null) {
      window.clearTimeout(toastTimer.current);
      toastTimer.current = null;
    }
    setToast(null);
  };

  const showToast = (message: string) => {
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current);
    setToast(message);
    toastTimer.current = window.setTimeout(() => {
      setToast(null);
      toastTimer.current = null;
    }, TOAST_TIMEOUT_MS);
  };

  // Persist the new role set and update the local row on success.
  const commitRoles = async (userId: string, newRoles: string[]): Promise<boolean> => {
    try {
      await setUserRoles(userId, newRoles);
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, roles: newRoles } : u)));
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setLoadError(message);
      return false;
    }
  };

  const toggleLowFriction = async (user: AdminUser, meta: RoleMeta, assigned: boolean) => {
    const action = assigned ? "remove" : "add";
    const newRoles = composeNewRoles(user, meta.key, action);
    const ok = await commitRoles(user.id, newRoles);
    if (!ok) return;
    showToast(changedMessage(user, meta, action));
  };

  const openHighFrictionModal = (user: AdminUser, meta: RoleMeta, assigned: boolean) => {
    setPendingConfirm({
      userId: user.id,
      userLabel: user.email ?? user.display_name ?? "user",
      role: meta.key,
      action: assigned ? "remove" : "add",
    });
  };

  const handleChipClick = (user: AdminUser, ev: CustomEvent) => {
    const { role, assigned } = ev.detail as { role: RoleKey; assigned: boolean };
    const meta = getRoleMeta(role);
    if (!meta) return;
    if (meta.power === "low") {
      void toggleLowFriction(user, meta, assigned);
    } else {
      openHighFrictionModal(user, meta, assigned);
    }
  };

  const handleConfirmCancel = () => setPendingConfirm(null);

  const handleConfirmRoleConfirmed = async (ev: CustomEvent) => {
    const ctx = ev.detail as ConfirmRoleContext;
    setPendingConfirm(null);
    const user = users.find((u) => u.id === ctx.userId);
    if (!user) return;
    const newRoles = composeNewRoles(user, ctx.role as RoleKey, ctx.action);
    await commitRoles(user.id, newRoles);
    // No toast for high-friction — the modal was the confirmation.
  };

  return html`
    <main class="admin-page page-content">
      <h1 class="admin-page__title">User roles</h1>
      ${loading ? html`<p class="admin-page__status">Loading…</p>` : null}
      ${loadError ? html`<p class="admin-page__status admin-page__error">${loadError}</p>` : null}
      ${!loading && !loadError && users.length === 0
        ? html`<p class="admin-page__status">No users.</p>`
        : null}
      ${!loading && !loadError && users.length > 0
        ? html`
            <table class="admin-users-table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Display name</th>
                  <th>Roles</th>
                </tr>
              </thead>
              <tbody>
                ${users.map((user) => {
                  const isSelf = currentUserId !== null && user.id === currentUserId;
                  return html`
                    <tr>
                      <td>
                        ${user.email ?? "—"}
                        ${isSelf
                          ? html`<span class="admin-users-table__self-tag">you</span>`
                          : null}
                      </td>
                      <td>${user.display_name ?? "—"}</td>
                      <td>
                        <div class="admin-users-table__roles">
                          ${ROLES_META.map((meta) => {
                            const assigned = user.roles.includes(meta.key);
                            return html`
                              <role-chip
                                .role=${meta.key}
                                .assigned=${assigned}
                                .disabled=${isSelf}
                                .disabledTooltip=${SELF_LOCK_TOOLTIP}
                                @role-chip-click=${(e: CustomEvent) => handleChipClick(user, e)}
                              ></role-chip>
                            `;
                          })}
                        </div>
                      </td>
                    </tr>
                  `;
                })}
              </tbody>
            </table>
          `
        : null}
      ${toast
        ? html`
            <status-toast
              .message=${toast}
              .onDismiss=${dismissToast}
            ></status-toast>
          `
        : null}
      ${pendingConfirm
        ? html`
            <confirm-role-modal
              .context=${pendingConfirm}
              @modal-close=${handleConfirmCancel}
              @role-confirmed=${handleConfirmRoleConfirmed}
            ></confirm-role-modal>
          `
        : null}
    </main>
  `;
}

customElements.define("admin-page", component(AdminPage, { useShadowDOM: false }));
export default AdminPage;
