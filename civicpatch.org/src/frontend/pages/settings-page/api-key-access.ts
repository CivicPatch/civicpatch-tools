export type SettingsUser = {
  authenticated?: boolean;
  username?: string | null;
  permissions?: { can_write_config?: boolean };
};

/**
 * Whether to show the API-key section.
 *
 * Cosmetic only — every `/api/v1/api_keys` route enforces the same level server-side, so
 * this hides a control rather than protecting anything. It fails closed: an unparseable or
 * absent user is not a maintainer.
 */
export function canManageApiKeys(user: SettingsUser | null): boolean {
  if (!user || !user.authenticated) return false;
  return user.permissions?.can_write_config === true;
}
