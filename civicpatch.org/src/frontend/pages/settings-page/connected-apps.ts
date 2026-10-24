import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { fetchConnectedApps, disconnectApp } from "../../api.js";
import { formatDate } from "./api-key-tables.js";

// Mirrors ConnectedApp in schemas/connected_apps.py.
type ConnectedApp = {
  client_id: string;
  name: string;
  granted_at: string;
};

function renderApps(
  apps: ConnectedApp[],
  disconnectingId: string | null,
  onDisconnect: (clientId: string) => void,
) {
  if (!apps.length) return html`<p class="api-keys__hint">No apps connected.</p>`;
  return html`
    <div class="api-keys__scroll">
      <table class="api-keys__table">
        <thead>
          <tr>
            <th>App</th>
            <th>Connected</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${apps.map(
            (app) => html`
              <tr>
                <td>${app.name}</td>
                <td>${formatDate(app.granted_at)}</td>
                <td class="api-key__actions">
                  <button
                    type="button"
                    class="civ-action-btn"
                    ?disabled=${disconnectingId === app.client_id}
                    @click=${() => onDisconnect(app.client_id)}
                  >
                    Disconnect
                  </button>
                </td>
              </tr>
            `,
          )}
        </tbody>
      </table>
    </div>
    <p class="api-keys__hint">Disconnecting stops the app within the hour.</p>
  `;
}

function ConnectedApps() {
  const [apps, setApps] = useState<ConnectedApp[]>([]);
  const [disconnectingId, setDisconnectingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const { data } = await fetchConnectedApps();
      setApps(data);
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleDisconnect = async (clientId: string) => {
    setDisconnectingId(clientId);
    try {
      await disconnectApp(clientId);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setDisconnectingId(null);
    }
  };

  return html`
    <section class="api-keys">
      <h2 class="api-keys__title">Connected apps</h2>
      ${error ? html`<p class="api-keys__error">${error}</p>` : null}
      ${renderApps(apps, disconnectingId, handleDisconnect)}
    </section>
  `;
}

customElements.define(
  "connected-apps",
  component(ConnectedApps as unknown as () => unknown, { useShadowDOM: false }),
);
