import "./config-editor.css";
import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { fetchRoles } from "../../api.js";
import { useAuth } from "../../hooks/useAuth.js";
import "../../components/basic/modal.js";

const STATUS_ACTIVE = "active";
const ALL_LEVELS = "";
const LEVEL_OPTIONS = [
  { value: ALL_LEVELS, label: "All levels" },
  { value: "local", label: "Local" },
  { value: "counties", label: "Counties" },
];

function aliasLabel(aliases) {
  if (!aliases?.length) return "—";
  if (aliases.length === 1) return aliases[0];
  return `${aliases.length} aliases`;
}

function seedState(jurisdictions) {
  const j = jurisdictions[0];
  return j?.state || j?.jurisdiction_path?.split("/")[0] || "";
}

function TermTable({ terms }) {
  const [aliasModal, setAliasModal] = useState(null);

  return html`
    <div class="config-editor__table-wrapper">
    <table class="config-editor__table">
      <thead>
        <tr>
          <th>Role</th>
          <th>Unique</th>
          <th>Aliases</th>
        </tr>
      </thead>
      <tbody>
        ${terms.length === 0
          ? html`<tr>
              <td colspan="3" class="config-editor__empty">No roles yet.</td>
            </tr>`
          : terms.map(
              (t) => html`
                <tr>
                  <td>${t.label}</td>
                  <td>${t.is_unique ? "Yes" : "No"}</td>
                  <td
                    class=${t.aliases?.length > 1
                      ? "config-editor__alias-clickable"
                      : ""}
                    @click=${() => t.aliases?.length > 1 && setAliasModal(t)}
                  >
                    ${aliasLabel(t.aliases)}
                  </td>
                </tr>
              `,
            )}
      </tbody>
    </table>
    </div>
    ${aliasModal
      ? html`
          <civ-modal
            .title=${"Aliases: " + aliasModal.label}
            .content=${html`<ul>
              ${aliasModal.aliases.map((a) => html`<li>${a}</li>`)}
            </ul>`}
            .footer=${html`<button
              class="btn btn-sm secondary"
              @click=${() => setAliasModal(null)}
            >
              Close
            </button>`}
            .modalProps=${{ open: true, onClose: () => setAliasModal(null) }}
          ></civ-modal>
        `
      : null}
  `;
}

customElements.define(
  "civ-term-table",
  component(TermTable, { useShadowDOM: false }),
);

function ConfigEditor(host) {
  const jurisdictions = host.jurisdictions || [];
  const inline = Boolean(host.inline);
  const { permissions } = useAuth();

  const [terms, setTerms] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [filter, setFilter] = useState("");
  const [level, setLevel] = useState(ALL_LEVELS);
  const [stateCode, setStateCode] = useState(seedState(jurisdictions));

  const dispatch = (name, detail) =>
    host.dispatchEvent(
      new CustomEvent(name, { detail, bubbles: true, composed: true }),
    );

  const load = () => {
    setTerms(null);
    setLoadError(null);
    fetchRoles({ level, state: stateCode })
      .then((r) => setTerms((r.data?.roles || []).filter((t) => t.status === STATUS_ACTIVE)))
      .catch((e) => setLoadError(e.message));
  };

  useEffect(() => {
    if (permissions.can_write_config) load();
  }, [permissions.can_write_config, level, stateCode]);

  const filtered = (terms ?? []).filter((t) =>
    t.label.toLowerCase().includes(filter.toLowerCase()),
  );

  const loading = terms === null && !loadError;

  const rolesSection = html`
    <div class="config-editor__section-body">
      ${loadError
        ? html`<p class="config-editor__error">${loadError}</p>`
        : null}
      ${loading ? html`<div>Loading…</div>` : null}
      ${terms !== null
        ? html`
            <div class="config-editor__layer">
              <label>
                Level
                <select
                  .value=${level}
                  @change=${(e) => setLevel(e.target.value)}
                >
                  ${LEVEL_OPTIONS.map(
                    (option) =>
                      html`<option value=${option.value}>${option.label}</option>`,
                  )}
                </select>
              </label>
              <label>
                State
                <input
                  type="text"
                  maxlength="2"
                  ?disabled=${level === ALL_LEVELS}
                  .value=${stateCode}
                  @change=${(e) => setStateCode(e.target.value.trim().toLowerCase())}
                />
              </label>
            </div>
            <div class="config-editor__filter">
              <i
                class="fa-solid fa-magnifying-glass config-editor__filter-icon"
              ></i>
              <input
                type="text"
                class="config-editor__filter-input"
                placeholder="Filter…"
                .value=${filter}
                @input=${(e) => setFilter(e.target.value)}
              />
            </div>
            <div class="config-editor__subsection-header">
              <p class="config-editor__subsection-label">
                Roles
                <span class="config-editor__role-count">${terms.length}</span>
              </p>
            </div>
            <civ-term-table .terms=${filtered}></civ-term-table>
          `
        : null}
    </div>
  `;

  const content = html`${permissions.can_write_config ? rolesSection : null}`;

  const handleClose = () => dispatch("modal-close", {});

  if (inline) return html`<div class="config-editor__inline">${content}</div>`;

  const title =
    jurisdictions.length === 1
      ? "Config: " +
        (jurisdictions[0].name || jurisdictions[0].jurisdiction_ocdid)
      : "Config: " + (seedState(jurisdictions).toUpperCase() || "");

  return html`
    <civ-modal
      .title=${title}
      .content=${content}
      .footer=${html`<button class="btn btn-sm secondary" @click=${handleClose}>
        Close
      </button>`}
      .modalProps=${{ open: true, onClose: handleClose }}
    ></civ-modal>
  `;
}

customElements.define(
  "issues-config-editor",
  component(ConfigEditor, { useShadowDOM: false }),
);
