import { html } from "lit-html";

// Mirrors ApiKeyScope in schemas/common.py.
export const AGENT_SCOPE = "agent";
export const FULL_SCOPE = "full";
export type ApiKeyScope = typeof AGENT_SCOPE | typeof FULL_SCOPE;

const SCOPE_NAMES: Record<ApiKeyScope, string> = {
  [AGENT_SCOPE]: "Agent",
  [FULL_SCOPE]: "Full",
};

export type ApiKey = {
  id: number;
  suffix: string;
  created_at: string | null;
  revoked_at: string | null;
  scope: ApiKeyScope;
  label: string | null;
  last_used_at: string | null;
};

function formatDate(value: string | null): string {
  if (!value) return "never";
  return new Date(value).toLocaleDateString();
}

export function renderActiveKeys(
  keys: ApiKey[],
  revokingId: number | null,
  onRevoke: (id: number) => void,
) {
  if (!keys.length) return html`<p class="api-keys__hint">No keys yet.</p>`;
  return html`
    <table class="api-keys__table">
      <thead>
        <tr>
          <th>For</th>
          <th>Key</th>
          <th>Access</th>
          <th>Created</th>
          <th>Last used</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${keys.map(
          (key) => html`
            <tr>
              <td>${key.label ?? ""}</td>
              <td class="api-key__suffix">…${key.suffix}</td>
              <td>${SCOPE_NAMES[key.scope]}</td>
              <td>${formatDate(key.created_at)}</td>
              <td>${formatDate(key.last_used_at)}</td>
              <td class="api-key__actions">
                <button
                  type="button"
                  class="civ-action-btn"
                  ?disabled=${revokingId === key.id}
                  @click=${() => onRevoke(key.id)}
                >
                  Revoke
                </button>
              </td>
            </tr>
          `,
        )}
      </tbody>
    </table>
  `;
}

export function renderRevokedKeys(keys: ApiKey[]) {
  if (!keys.length) return null;
  return html`
    <section class="api-keys">
      <h2 class="api-keys__title">Revoked keys</h2>
      <table class="api-keys__table">
        <thead>
          <tr>
            <th>For</th>
            <th>Key</th>
            <th>Access</th>
            <th>Created</th>
            <th>Last used</th>
            <th>Revoked</th>
          </tr>
        </thead>
        <tbody>
          ${keys.map(
            (key) => html`
              <tr>
                <td>${key.label ?? ""}</td>
                <td class="api-key__suffix">…${key.suffix}</td>
                <td>${SCOPE_NAMES[key.scope]}</td>
                <td>${formatDate(key.created_at)}</td>
                <td>${formatDate(key.last_used_at)}</td>
                <td>${formatDate(key.revoked_at)}</td>
              </tr>
            `,
          )}
        </tbody>
      </table>
    </section>
  `;
}
