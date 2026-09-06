export type SettingsUser = {
  authenticated?: boolean;
  display_name?: string | null;
  permissions?: { can_write_config?: boolean };
};

/**
 * Whether to show the API-key section.
 *
 * Cosmetic only — every `/api/v1/api_keys` route enforces the same level server-side, so
 * this hides a control rather than protecting anything. It fails closed: an unparseable or
 * absent user is not a maintainer.
 *
 * Also hidden until a display name is set, because that page blocks behind its own banner and
 * offering a secret-minting button under a "you cannot continue yet" alert is a bad thing to
 * click.
 */
export function canManageApiKeys(user: SettingsUser | null): boolean {
  if (!user || !user.authenticated) return false;
  if (!user.display_name) return false;
  return user.permissions?.can_write_config === true;
}
