import "./config-editor.css";
import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import {
  fetchJurisdictionConfig,
  putJurisdictionConfig,
  fetchGlobalConfig,
  putGlobalConfig,
  fetchJurisdictionForState,
  deleteRole,
} from "../../api.js";
import { useAuth } from "../../hooks/useAuth.js";
import "../../components/basic/modal.js";
import "../../components/badge/badge.js";
import "../../components/inputs/auto-complete-select.js";
import "../../components/role-reorder/role-reorder.ts";
import "../../components/jurisdiction-search/jurisdiction-search.ts";
import {
  ALERT_MODE,
  DANGER_VARIANT,
} from "../../components/confirm-modal/confirm-modal.ts";

const SCOPE_GLOBAL = "global";
const SCOPE_STATE = "state";
const SCOPE_LOCALITY = "locality";

const STATUS_ACTIVE = "active";
const STATUS_CANDIDATE = "candidate";
const STATUS_REJECTED = "rejected";

const STATUS_OPTIONS = [STATUS_ACTIVE, STATUS_CANDIDATE, STATUS_REJECTED];

function parseAliases(text) {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

function aliasLabel(aliases) {
  if (!aliases?.length) return "—";
  if (aliases.length === 1) return aliases[0];
  return `${aliases.length} aliases`;
}

function seedState(jurisdictions) {
  const j = jurisdictions[0];
  return j?.state || j?.jurisdiction_path?.split("/")[0] || "";
}

function useTermEditor() {
  const [isAdding, setIsAdding] = useState(false);
  const [editingValue, setEditingValue] = useState(null);
  const [editName, setEditName] = useState("");
  const [editStatus, setEditStatus] = useState(STATUS_ACTIVE);
  const [editUnique, setEditUnique] = useState(false);
  const [editAliases, setEditAliases] = useState("");
  const [addName, setAddName] = useState("");
  const [addStatus, setAddStatus] = useState(STATUS_ACTIVE);
  const [addUnique, setAddUnique] = useState(false);
  const [addAliases, setAddAliases] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const openEdit = (term) => {
    setIsAdding(false);
    setEditingValue(term.label || term.role);
    setEditName(term.label || term.role);
    setEditStatus(term.status || STATUS_ACTIVE);
    setEditUnique(term.is_unique);
    setEditAliases((term.aliases || []).join("\n"));
    setSaveError(null);
  };

  const openAdd = () => {
    setIsAdding(true);
    setEditingValue(null);
    setAddName("");
    setAddStatus(STATUS_ACTIVE);
    setAddUnique(false);
    setAddAliases("");
    setSaveError(null);
  };

  const reset = () => {
    setIsAdding(false);
    setEditingValue(null);
    setSaveError(null);
  };

  return {
    isAdding,
    editingValue,
    editName,
    setEditName,
    editStatus,
    setEditStatus,
    editUnique,
    setEditUnique,
    editAliases,
    setEditAliases,
    addName,
    setAddName,
    addStatus,
    setAddStatus,
    addUnique,
    setAddUnique,
    addAliases,
    setAddAliases,
    saving,
    setSaving,
    saveError,
    setSaveError,
    openEdit,
    openAdd,
    reset,
  };
}

function TermTable({ terms, scope, editable, editor, onSave, onDelete }) {
  const [aliasModal, setAliasModal] = useState(null);
  const [confirmState, setConfirmState] = useState(null);
  const {
    isAdding,
    editingValue,
    editName,
    setEditName,
    editStatus,
    setEditStatus,
    editUnique,
    setEditUnique,
    editAliases,
    setEditAliases,
    addName,
    setAddName,
    addStatus,
    setAddStatus,
    addUnique,
    setAddUnique,
    addAliases,
    setAddAliases,
    saving,
    saveError,
    setSaveError,
    openEdit,
    openAdd,
    reset,
  } = editor;

  const handleSaveEdit = () => {
    onSave(
      {
        type: "edit",
        value: editingValue,
        label: editName.trim(),
        status: editStatus,
        is_unique: editUnique,
        aliases: parseAliases(editAliases),
      },
      reset,
      setSaveError,
    );
  };

  const handleSaveAdd = () => {
    if (!addName.trim()) return;
    onSave(
      {
        type: "add",
        label: addName.trim(),
        status: addStatus,
        is_unique: addUnique,
        aliases: parseAliases(addAliases),
      },
      reset,
      setSaveError,
    );
  };

  const handleDelete = (term) => {
    const name = term.label || term.role;
    setConfirmState({
      message: `Remove role "${name}" from ${scope}? This cannot be undone.`,
      confirmLabel: "Remove",
      variant: DANGER_VARIANT,
      onConfirm: () => onDelete(name),
    });
  };

  const statusBadge = (status) => {
    if (!status || status === STATUS_ACTIVE) return "";
    if (status === STATUS_CANDIDATE) return " (candidate)";
    if (status === STATUS_REJECTED) return " (rejected)";
    return "";
  };

  const editing = editingValue !== null;
  const adding = isAdding;

  const formContent = editing
    ? html`
        <div class="config-editor__edit-form">
          <label>Label <input type="text" readonly .value=${editName} /></label>
          <label
            >Status
            <select
              .value=${editStatus}
              @change=${(e) => setEditStatus(e.target.value)}
            >
              ${STATUS_OPTIONS.map(
                (s) => html`<option value=${s}>${s}</option>`,
              )}
            </select>
          </label>
          <label class="config-editor__checkbox-label"
            ><input
              type="checkbox"
              ?checked=${editUnique}
              @change=${(e) => setEditUnique(e.target.checked)}
            />
            Unique</label
          >
          <label
            >Aliases (one per line)<br /><textarea
              rows="5"
              .value=${editAliases}
              @input=${(e) => setEditAliases(e.target.value)}
            ></textarea>
          </label>
          ${saveError
            ? html`<p class="config-editor__error">${saveError}</p>`
            : null}
        </div>
      `
    : html``;

  const addFormContent = adding
    ? html`
        <div class="config-editor__edit-form">
          <label
            >Label
            <input
              type="text"
              .value=${addName}
              @input=${(e) => setAddName(e.target.value)}
          /></label>
          <label
            >Status
            <select
              .value=${addStatus}
              @change=${(e) => setAddStatus(e.target.value)}
            >
              ${STATUS_OPTIONS.map(
                (s) => html`<option value=${s}>${s}</option>`,
              )}
            </select>
          </label>
          <label class="config-editor__checkbox-label"
            ><input
              type="checkbox"
              ?checked=${addUnique}
              @change=${(e) => setAddUnique(e.target.checked)}
            />
            Unique</label
          >
          <label
            >Aliases (one per line)<br /><textarea
              rows="5"
              .value=${addAliases}
              @input=${(e) => setAddAliases(e.target.value)}
            ></textarea>
          </label>
          ${saveError
            ? html`<p class="config-editor__error">${saveError}</p>`
            : null}
        </div>
      `
    : html``;

  const formFooter = editing
    ? html`
        <button class="btn btn-sm" @click=${handleSaveEdit} ?disabled=${saving}>
          Save
        </button>
        <button class="btn btn-sm secondary" @click=${reset}>Cancel</button>
      `
    : adding
      ? html`
          <button
            class="btn btn-sm"
            @click=${handleSaveAdd}
            ?disabled=${saving || !addName.trim()}
          >
            Add
          </button>
          <button class="btn btn-sm secondary" @click=${reset}>Cancel</button>
        `
      : null;

  const formTitle = editing ? `Edit: ${editingValue}` : "Add role";

  return html`
    <table class="config-editor__table">
      <thead>
        <tr>
          <th>Role</th>
          <th>Status</th>
          <th>Unique</th>
          <th>Aliases</th>
          ${editable ? html`<th></th>` : null}
        </tr>
      </thead>
      <tbody>
        ${terms.length === 0
          ? html`<tr>
              <td colspan=${editable ? 5 : 4} class="config-editor__empty">
                No roles yet.
              </td>
            </tr>`
          : terms.map(
              (t) => html`
                <tr>
                  <td>${t.label || t.role}</td>
                  <td>${t.status || STATUS_ACTIVE}${statusBadge(t.status)}</td>
                  <td>${t.is_unique ? "Yes" : "No"}</td>
                  <td
                    class=${t.aliases?.length > 1
                      ? "config-editor__alias-clickable"
                      : ""}
                    @click=${() => t.aliases?.length > 1 && setAliasModal(t)}
                  >
                    ${aliasLabel(t.aliases)}
                  </td>
                  ${editable
                    ? html`
                        <td class="config-editor__actions">
                          <button
                            class="civ-action-btn"
                            @click=${() => openEdit(t)}
                          >
                            Edit
                          </button>
                          <button
                            class="civ-action-btn civ-action-btn--danger"
                            @click=${() => handleDelete(t)}
                          >
                            Remove
                          </button>
                        </td>
                      `
                    : null}
                </tr>
              `,
            )}
      </tbody>
    </table>
    ${editable
      ? html`<button class="config-editor__add-btn" @click=${() => openAdd()}>
          + Add role
        </button>`
      : null}
    ${editing || adding
      ? html`
          <civ-modal
            .title=${formTitle}
            .content=${editing ? formContent : addFormContent}
            .footer=${formFooter}
            .modalProps=${{ open: true, onClose: reset }}
          ></civ-modal>
        `
      : null}
    ${aliasModal
      ? html`
          <civ-modal
            .title=${"Aliases: " + (aliasModal.label || aliasModal.role)}
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
    ${confirmState
      ? html`
          <civ-confirm-modal
            .message=${confirmState.message}
            .confirmLabel=${confirmState.confirmLabel}
            .variant=${confirmState.variant}
            @confirm=${() => {
              confirmState.onConfirm();
              setConfirmState(null);
            }}
            @cancel=${() => setConfirmState(null)}
          ></civ-confirm-modal>
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
  const firstOcdid = jurisdictions[0]?.jurisdiction_ocdid;
  const inline = Boolean(host.inline);
  const { permissions } = useAuth();

  const stateCode = inline ? host.stateCode || "" : seedState(jurisdictions);

  const [globalTerms, setGlobalTerms] = useState(null);
  const [globalError, setGlobalError] = useState(null);
  const globalEditor = useTermEditor();

  const [stateOcdid, setStateOcdid] = useState(firstOcdid || null);
  const [stateTerms, setStateTerms] = useState(null);
  const [stateError, setStateError] = useState(null);
  const stateEditor = useTermEditor();

  const [localityOcdid, setLocalityOcdid] = useState(firstOcdid || null);
  const [localityTerms, setLocalityTerms] = useState(null);
  const [localityError, setLocalityError] = useState(null);
  const localityEditor = useTermEditor();

  const [localityFilter, setLocalityFilter] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [globalFilter, setGlobalFilter] = useState("");

  const [reorderingScope, setReorderingScope] = useState(null);
  const [reorderToast, setReorderToast] = useState(null);
  const [errorState, setErrorState] = useState(null);

  const showReorderToast = () => {
    setReorderToast("Roles reordered");
    setTimeout(() => setReorderToast(null), 4000);
  };

  const dispatch = (name, detail) =>
    host.dispatchEvent(
      new CustomEvent(name, { detail, bubbles: true, composed: true }),
    );

  const loadGlobal = () => {
    setGlobalTerms(null);
    setGlobalError(null);
    fetchGlobalConfig()
      .then((r) => setGlobalTerms(r.data?.roles || []))
      .catch((e) => setGlobalError(e.message));
  };

  const loadStateConfig = (ocdid) => {
    if (!ocdid) return;
    setStateTerms(null);
    setStateError(null);
    fetchJurisdictionConfig(ocdid)
      .then((r) => {
        const terms = r.data?.roles || [];
        setStateTerms(terms.filter((t) => t.scope === SCOPE_STATE));
      })
      .catch((e) => setStateError(e.message));
  };

  const loadLocalityConfig = (ocdid) => {
    if (!ocdid) return;
    setLocalityTerms(null);
    setLocalityError(null);
    fetchJurisdictionConfig(ocdid)
      .then((r) => {
        const terms = r.data?.roles || [];
        setLocalityTerms(terms.filter((t) => t.scope === SCOPE_LOCALITY));
      })
      .catch((e) => setLocalityError(e.message));
  };

  useEffect(() => {
    if (firstOcdid) {
      loadStateConfig(firstOcdid);
      loadLocalityConfig(firstOcdid);
    }
  }, []);

  useEffect(() => {
    if (permissions.can_write_config && globalTerms === null && !globalError)
      loadGlobal();
  }, [permissions.can_write_config]);

  useEffect(() => {
    if (!stateCode) {
      setStateTerms(null);
      setStateOcdid(null);
      return;
    }
    fetchJurisdictionForState(stateCode)
      .then((r) => {
        const ocdid = r?.data?.[0]?.jurisdiction_ocdid;
        setStateOcdid(ocdid || null);
        if (ocdid) loadStateConfig(ocdid);
        else
          setStateError(
            `No jurisdictions found for ${stateCode.toUpperCase()}`,
          );
      })
      .catch((e) => setStateError(e.message));
  }, [stateCode]);

  useEffect(() => {
    setReorderingScope(null);
    if (localityOcdid) loadLocalityConfig(localityOcdid);
  }, [localityOcdid]);

  const makeBatchSave = (scope, ocdid, terms, reload, editor) => {
    return async (op, reset, setSaveError) => {
      editor.setSaving(true);
      setSaveError(null);
      try {
        let updated;
        if (op.type === "edit") {
          updated = terms.map((t) => {
            const name = t.label || t.role;
            if (name === op.value) {
              return {
                label: op.label,
                status: op.status,
                is_unique: op.is_unique,
                aliases: op.aliases,
              };
            }
            return {
              label: name,
              status: t.status || STATUS_ACTIVE,
              is_unique: t.is_unique,
              aliases: t.aliases,
            };
          });
        } else {
          // add
          updated = [
            ...terms.map((t) => ({
              label: t.label || t.role,
              status: t.status || STATUS_ACTIVE,
              is_unique: t.is_unique,
              aliases: t.aliases,
            })),
            {
              label: op.label,
              status: op.status,
              is_unique: op.is_unique,
              aliases: op.aliases,
            },
          ];
        }
        if (scope === SCOPE_GLOBAL) {
          await putGlobalConfig(updated);
        } else {
          await putJurisdictionConfig({ ocdid, scope, roles: updated });
        }
        reload();
        reset();
      } catch (e) {
        setSaveError(e.message);
      } finally {
        editor.setSaving(false);
      }
    };
  };

  const makeDelete = (scope, ocdid, reload) => async (role) => {
    try {
      await deleteRole(role, scope, ocdid || "");
      reload();
    } catch (e) {
      console.error("Remove failed:", e);
      setErrorState(`Remove failed: ${e.message}`);
    }
  };

  const renderSection = (params) => {
    const {
      scope,
      badge,
      label,
      terms,
      error,
      loading,
      ocdid,
      reload,
      editor,
      filter,
      setFilter,
      editable,
      open,
    } = params;

    const filtered = (terms ?? []).filter((t) =>
      (t.label || t.role).toLowerCase().includes(filter.toLowerCase()),
    );

    const batchSave = makeBatchSave(scope, ocdid, terms || [], reload, editor);
    const remove = makeDelete(scope, ocdid, reload);

    return html`
      <details class="config-editor__section" ?open=${open}>
        <summary class="config-editor__section-title">
          <civ-badge .label=${badge} .variant=${badge}></civ-badge>
          ${label
            ? html`<span class="config-editor__section-label">${label}</span>`
            : null}
          ${terms !== null
            ? html`<span class="config-editor__role-count"
                >${terms.length}</span
              >`
            : null}
          <i class="fa-solid fa-chevron-down config-editor__chevron"></i>
        </summary>
        <div class="config-editor__section-body">
          ${scope === SCOPE_LOCALITY
            ? html`
                ${jurisdictions.length > 0
                  ? html`
                      ${jurisdictions.length === 1
                        ? null
                        : html`
                            <label class="config-editor__locality-picker">
                              Jurisdiction
                              <select
                                @change=${(e) => {
                                  localityEditor.reset();
                                  setLocalityOcdid(e.target.value);
                                }}
                              >
                                ${jurisdictions.map(
                                  (j) => html`
                                    <option
                                      value=${j.jurisdiction_ocdid}
                                      ?selected=${j.jurisdiction_ocdid ===
                                      localityOcdid}
                                    >
                                      ${j.name || j.jurisdiction_ocdid}
                                    </option>
                                  `,
                                )}
                              </select>
                            </label>
                          `}
                    `
                  : html`
                      <div class="config-editor__locality-search">
                        <civ-jurisdiction-search
                          .state=${stateCode}
                          .level=${`local`}
                          .placeholder=${`Search for a city in ${stateCode.toUpperCase()}`}
                          @jurisdiction-select=${(e) => {
                            localityEditor.reset();
                            setLocalityOcdid(e.detail.jurisdiction_ocdid);
                          }}
                        ></civ-jurisdiction-search>
                      </div>
                    `}
              `
            : null}
          ${error ? html`<p class="config-editor__error">${error}</p>` : null}
          ${loading ? html`<div>Loading…</div>` : null}
          ${terms !== null
            ? html`
                ${reorderingScope === scope
                  ? null
                  : html`
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
                    `}
                ${reorderingScope === scope
                  ? null
                  : html`
                      <div class="config-editor__subsection-header">
                        <p class="config-editor__subsection-label">Roles</p>
                        ${editable && filtered.length > 1
                          ? html`
                              <button
                                class="btn btn-sm secondary"
                                ?disabled=${filter.length > 0}
                                title=${filter.length > 0
                                  ? "Clear the filter to reorder"
                                  : "Reorder roles by priority"}
                                @click=${() => setReorderingScope(scope)}
                              >
                                Reorder
                              </button>
                            `
                          : null}
                      </div>
                    `}
                ${reorderingScope === scope
                  ? html`
                      <civ-role-reorder
                        .roles=${filtered}
                        .scope=${scope}
                        .ocdid=${ocdid}
                        @reordered=${() => {
                          setReorderingScope(null);
                          reload();
                          showReorderToast();
                        }}
                        @cancel=${() => setReorderingScope(null)}
                      ></civ-role-reorder>
                    `
                  : html`
                      <civ-term-table
                        .terms=${filtered}
                        .scope=${scope}
                        .editable=${editable}
                        .editor=${editor}
                        .onSave=${batchSave}
                        .onDelete=${remove}
                      ></civ-term-table>
                    `}
              `
            : null}
        </div>
      </details>
    `;
  };

  const localitySection = renderSection({
    scope: SCOPE_LOCALITY,
    badge: "locality",
    label: null,
    terms: localityTerms,
    error: localityError,
    loading: localityTerms === null && !localityError && localityOcdid,
    ocdid: localityOcdid,
    reload: () => loadLocalityConfig(localityOcdid),
    editor: localityEditor,
    filter: localityFilter,
    setFilter: setLocalityFilter,
    editable: true,
    open: true,
  });

  const stateSection = renderSection({
    scope: SCOPE_STATE,
    badge: "state",
    label: stateCode ? stateCode.toUpperCase() : null,
    terms: stateTerms,
    error: stateError,
    loading: stateTerms === null && !stateError && stateCode,
    ocdid: stateOcdid,
    reload: () => loadStateConfig(stateOcdid),
    editor: stateEditor,
    filter: stateFilter,
    setFilter: setStateFilter,
    editable: true,
    open: true,
  });

  const globalSection = renderSection({
    scope: SCOPE_GLOBAL,
    badge: "global",
    label: null,
    terms: globalTerms,
    error: globalError,
    loading: globalTerms === null && !globalError,
    ocdid: null,
    reload: loadGlobal,
    editor: globalEditor,
    filter: globalFilter,
    setFilter: setGlobalFilter,
    editable: permissions.can_write_global_config,
    open: true,
  });

  const content = html`
    ${permissions.can_write_config && stateCode ? localitySection : null}
    ${permissions.can_write_config && stateCode ? stateSection : null}
    ${permissions.can_write_config ? globalSection : null}
    ${reorderToast
      ? html`<div class="config-editor__toast" role="status" aria-live="polite">
          ${reorderToast}
        </div>`
      : null}
    ${errorState
      ? html`
          <civ-confirm-modal
            .mode=${ALERT_MODE}
            .title=${"Action failed"}
            .message=${errorState}
            @confirm=${() => setErrorState(null)}
            @cancel=${() => setErrorState(null)}
          ></civ-confirm-modal>
        `
      : null}
  `;

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
