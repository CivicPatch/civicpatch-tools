import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { fetchApiKeys, createApiKey, revokeApiKey } from "../../api.js";
import "../../components/action-btn/action-btn.css";
import "./connected-apps.js";
import { agentSetups, type AgentSetup, type SetupField } from "./api-key-commands.js";
import {
  AGENT_SCOPE,
  FULL_SCOPE,
  renderActiveKeys,
  renderRevokedKeys,
  type ApiKey,
  type ApiKeyScope,
} from "./api-key-tables.js";

const SCOPE_LABELS: Record<ApiKeyScope, string> = {
  [AGENT_SCOPE]: "Agent: MCP and roster comparisons only",
  [FULL_SCOPE]: "Full: everything you can do",
};

// Mirrors MAX_LABEL_LENGTH in schemas/api_keys.py.
const MAX_LABEL_LENGTH = 100;

type CreatedKey = {
  api_key: string;
  scope: ApiKeyScope;
};

const COPIED_FOR_MS = 1500;

function renderCreateForm(
  label: string,
  scope: ApiKeyScope,
  creating: boolean,
  onLabel: (e: Event) => void,
  onScope: (e: Event) => void,
  onSubmit: (e: Event) => void,
) {
  return html`
    <form class="api-keys__form" @submit=${onSubmit}>
      <label class="api-keys__form-field">
        What is it for?
        <input
          type="text"
          placeholder="Claude Code on laptop"
          maxlength=${MAX_LABEL_LENGTH}
          required
          .value=${label}
          @input=${onLabel}
        />
      </label>
      <label class="api-keys__form-field">
        Access
        <select @change=${onScope}>
          ${[AGENT_SCOPE, FULL_SCOPE].map(
            (option) =>
              html`<option value=${option} .selected=${option === scope}>
                ${SCOPE_LABELS[option]}
              </option>`,
          )}
        </select>
      </label>
      <button
        type="submit"
        class="api-keys__create"
        ?disabled=${creating || !label.trim()}
      >
        Create key
      </button>
    </form>
  `;
}

function renderField(
  field: SetupField,
  copied: string | null,
  onCopy: (field: SetupField) => void,
) {
  return html`
    <div class="api-keys__field">
      <div class="api-keys__field-head">
        <span class="api-keys__field-label">${field.label}</span>
        <button
          type="button"
          class="btn-ghost btn-sm"
          @click=${() => onCopy(field)}
        >
          ${copied === field.label ? "Copied" : "Copy"}
        </button>
      </div>
      <pre class="api-keys__command">${field.value}</pre>
    </div>
  `;
}

function renderConnectApp(
  setups: AgentSetup[],
  selected: number,
  onSelect: (index: number) => void,
  copied: string | null,
  onCopy: (field: SetupField) => void,
) {
  const setup = setups[selected];
  return html`
    <section class="api-keys">
      <h2 class="api-keys__title">Connect an app</h2>
      <label class="api-keys__agent-picker">
        App
        <select
          @change=${(e: Event) =>
            onSelect(Number((e.target as HTMLSelectElement).value))}
        >
          ${setups.map(
            (option, index) =>
              html`<option value=${index} .selected=${index === selected}>
                ${option.agent}
              </option>`,
          )}
        </select>
      </label>
      <p>${setup.where}:</p>
      ${setup.fields.map((field) => renderField(field, copied, onCopy))}
      ${setup.steps.length
        ? html`<ol>${setup.steps.map((step) => html`<li>${step}</li>`)}</ol>`
        : null}
    </section>
  `;
}

function ApiKeys() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [created, setCreated] = useState<CreatedKey | null>(null);
  const [label, setLabel] = useState("");
  const [scope, setScope] = useState<ApiKeyScope>(AGENT_SCOPE);
  const [creating, setCreating] = useState(false);
  const [revokingId, setRevokingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [agentIndex, setAgentIndex] = useState(0);
  const [copied, setCopied] = useState<string | null>(null);

  const handleCopy = (field: SetupField) => {
    navigator.clipboard.writeText(field.value);
    setCopied(field.label);
    setTimeout(() => setCopied(null), COPIED_FOR_MS);
  };

  const handleSelectAgent = (index: number) => {
    setAgentIndex(index);
    setCopied(null);
  };

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

  const handleLabel = (e: Event) =>
    setLabel((e.target as HTMLInputElement).value);
  const handleScope = (e: Event) =>
    setScope((e.target as HTMLSelectElement).value as ApiKeyScope);

  const handleCreate = async (e: Event) => {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const body = await createApiKey({ label, scope });
      // Shown once and never again — it is stored hashed, so there is nothing to show later.
      setCreated({ api_key: body.api_key, scope });
      setLabel("");
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (id: number) => {
    setRevokingId(id);
    try {
      await revokeApiKey(id);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setRevokingId(null);
    }
  };

  // Only an agent key goes into an app; a full key is for scripts, not agents.
  const agentKey = created?.scope === AGENT_SCOPE ? created.api_key : null;
  const activeKeys = keys.filter((key) => !key.revoked_at);
  const revokedKeys = keys.filter((key) => key.revoked_at);

  return html`
    <section class="api-keys">
      <h2 class="api-keys__title">API keys</h2>
      <p class="api-keys__hint">
        Agent key: MCP and roster comparisons<br />
        Full key: Full permissions inherited from your account permissions
      </p>

      ${error ? html`<p class="api-keys__error">${error}</p>` : null}
      ${created
        ? html`
            <div class="api-keys__created">
              <p>
                Copy this now — it is stored hashed and cannot be shown again.
              </p>
              <code class="api-keys__secret">${created.api_key}</code>
              ${created.scope === AGENT_SCOPE
                ? html`<p>Connect an app with it below.</p>`
                : null}
            </div>
          `
        : null}
      ${renderActiveKeys(activeKeys, revokingId, handleRevoke)}
      ${renderCreateForm(
        label,
        scope,
        creating,
        handleLabel,
        handleScope,
        handleCreate,
      )}
    </section>

    ${renderConnectApp(
      agentSetups(window.location.origin, agentKey),
      agentIndex,
      handleSelectAgent,
      copied,
      handleCopy,
    )}
    <connected-apps></connected-apps>
    ${renderRevokedKeys(revokedKeys)}
  `;
}

customElements.define(
  "api-keys",
  component(ApiKeys as unknown as () => unknown, { useShadowDOM: false }),
);
