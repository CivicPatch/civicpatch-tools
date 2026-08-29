import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import {
  fetchApiKeys,
  createApiKey,
  revokeApiKey,
  deleteApiKey,
} from "../../api.js";

type ApiKey = {
  id: number;
  suffix: string;
  created_at: string | null;
  revoked_at: string | null;
};

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString();
}

function ApiKeys() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [created, setCreated] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const { data } = await fetchApiKeys();
      setKeys(data);
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async () => {
    setBusy(true);
    setError(null);
    try {
      const body = await createApiKey();
      // Shown once and never again — it is stored hashed, so there is nothing to show later.
      setCreated(body.api_key);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleRevoke = async (id: number) => {
    setBusy(true);
    try {
      await revokeApiKey(id);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (id: number) => {
    setBusy(true);
    try {
      await deleteApiKey(id);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const keyRow = (key: ApiKey) => html`
    <tr class=${key.revoked_at ? "api-key--revoked" : ""}>
      <td class="api-key__suffix">…${key.suffix}</td>
      <td>${formatDate(key.created_at)}</td>
      <td>${key.revoked_at ? `revoked ${formatDate(key.revoked_at)}` : "active"}</td>
      <td class="api-key__actions">
        ${key.revoked_at
          ? null
          : html`<button
              type="button"
              class="api-key__link"
              ?disabled=${busy}
              @click=${() => handleRevoke(key.id)}
            >
              Revoke
            </button>`}
        <button
          type="button"
          class="api-key__link api-key__link--danger"
          ?disabled=${busy}
          @click=${() => handleDelete(key.id)}
        >
          Delete
        </button>
      </td>
    </tr>
  `;

  return html`
    <section class="api-keys">
      <h2 class="api-keys__title">API keys</h2>
      <p class="api-keys__hint">
        A key carries your own access. Use one for a script or scheduled job —
        anything that needs to reach civicpatch without a browser session.
      </p>

      ${error ? html`<p class="api-keys__error">${error}</p>` : null}

      ${created
        ? html`
            <div class="api-keys__created">
              <p>Copy this now — it is stored hashed and cannot be shown again.</p>
              <code class="api-keys__secret">${created}</code>
            </div>
          `
        : null}

      ${keys.length
        ? html`
            <table class="api-keys__table">
              <thead>
                <tr>
                  <th>Key</th>
                  <th>Created</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                ${keys.map(keyRow)}
              </tbody>
            </table>
          `
        : html`<p class="api-keys__hint">No keys yet.</p>`}

      <button
        type="button"
        class="api-keys__create"
        ?disabled=${busy}
        @click=${handleCreate}
      >
        Create key
      </button>
    </section>
  `;
}

customElements.define(
  "api-keys",
  component(ApiKeys as unknown as () => unknown, { useShadowDOM: false }),
);
