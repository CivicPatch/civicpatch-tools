import { html } from "lit-html";
import { component, useState, useEffect, useRef } from "haunted";
import { fetchAdminUsers, setUserRole } from "../../api.js";
import { useAuth } from "../../hooks/useAuth.js";
import { ROLES_META, getRoleMeta, type RoleKey, type RoleMeta } from "./roles-meta.js";
import type { ConfirmRoleContext } from "./confirm-role-modal.js";
import "./role-chip.js";
import "./status-toast.js";
import "./confirm-role-modal.js";
import "./admin-page.css";

const SELF_LOCK_TOOLTIP = "To change your own role, use `mise run grant_role`.";
const TOAST_TIMEOUT_MS = 10_000;

const DEFAULT_ROLE = "default";
// Ladder order for "what's filled" + "what's the level just below" logic.
// Mirrors schemas/common.py:_ROLE_RANK.
const LADDER: readonly RoleKey[] = ROLES_META.map((m) => m.key);

type AdminUser = {
  id: string;
  email: string | null;
  display_name: string | null;
  provider: string;
  provider_user_id: string;
  role: string;
};

// Rank of a role on the ladder. default=0, contributors=1, ..., admins=3.
function rolePos(role: string): number {
  if (role === DEFAULT_ROLE) return 0;
  const idx = LADDER.indexOf(role as RoleKey);
  return idx === -1 ? 0 : idx + 1;
}

// Only the chip matching the user's exact current role is filled.
// Users at `default` have no chips filled.
function isChipFilled(userRole: string, chipKey: RoleKey): boolean {
  return userRole === chipKey;
}

// Click a chip → compute the user's new role.
//   - Click outlined → set role to that chip's level (promote or demote)
//   - Click filled (i.e. the user's current level) → revoke fully back to default
function computeTargetRole(chipKey: RoleKey, wasAssigned: boolean): string {
  return wasAssigned ? DEFAULT_ROLE : chipKey;
}

function isHighPower(role: string): boolean {
  const meta = getRoleMeta(role);
  return meta?.power === "high";
}

function changedMessage(user: AdminUser, fromRole: string, toRole: string): string {
  const who = user.email ?? user.display_name ?? "user";
  const fromLabel = getRoleMeta(fromRole)?.label ?? "default";
  const toLabel = getRoleMeta(toRole)?.label ?? "default";
  if (rolePos(toRole) > rolePos(fromRole)) {
    return `Promoted ${who} to ${toLabel}`;
  }
  return `Demoted ${who} from ${fromLabel} to ${toLabel}`;
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

  // Persist the new role and update the local row on success.
  const commitRole = async (user: AdminUser, fromRole: string, toRole: string): Promise<boolean> => {
    try {
      await setUserRole(user.id, toRole);
      setUsers((prev) => prev.map((u) => (u.id === user.id ? { ...u, role: toRole } : u)));
      showToast(changedMessage(user, fromRole, toRole));
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setLoadError(message);
      return false;
    }
  };

  const handleChipClick = (user: AdminUser, ev: CustomEvent) => {
    const { role: chipKey, assigned } = ev.detail as { role: RoleKey; assigned: boolean };
    const fromRole = user.role;
    const toRole = computeTargetRole(chipKey, assigned);
    if (fromRole === toRole) return;

    const isHigh = isHighPower(fromRole) || isHighPower(toRole);
    if (isHigh) {
      setPendingConfirm({
        userId: user.id,
        userLabel: user.email ?? user.display_name ?? "user",
        fromRole,
        toRole,
      });
    } else {
      void commitRole(user, fromRole, toRole);
    }
  };

  const handleConfirmCancel = () => setPendingConfirm(null);

  const handleConfirmRoleConfirmed = async (ev: CustomEvent) => {
    const ctx = ev.detail as ConfirmRoleContext;
    setPendingConfirm(null);
    const user = users.find((u) => u.id === ctx.userId);
    if (!user) return;
    await commitRole(user, ctx.fromRole, ctx.toRole);
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
                  <th>Role</th>
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
                          ${ROLES_META.map((meta: RoleMeta) => {
                            const assigned = isChipFilled(user.role, meta.key);
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
