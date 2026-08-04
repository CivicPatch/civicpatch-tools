import "./config-editor.css";
import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import {
  fetchJurisdictionConfig,
  putJurisdictionConfig,
  fetchGlobalConfig,
  putGlobalConfig,
  fetchJurisdictionForState,
  excludeRole,
  includeExclusion,
  deleteRole,
} from "../../api.js";
import { useAuth } from "../../hooks/useAuth.js";
import "../../components/basic/modal.js";
import "../../components/badge/badge.js";
import "../../components/inputs/auto-complete-select.js";
import "../../components/role-reorder/role-reorder.ts";
import { ALERT_MODE, DANGER_VARIANT } from "../../components/confirm-modal/confirm-modal.ts";

const SCOPE_GLOBAL = "global";
const SCOPE_STATE = "state";
const SCOPE_LOCALITY = "locality";

const KIND_CANONICAL = "canonical";
const KIND_EXCLUSION = "exclusion";

function parseAliases(text) {
  return text.split("\n").map((s) => s.trim()).filter(Boolean);
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

// One editor per scope; tracks which entry is being edited/added and of what kind.
function useTermEditor() {
  const [editingValue, setEditingValue] = useState(null);
  const [editingKind, setEditingKind] = useState(KIND_CANONICAL);
  const [editName, setEditName] = useState("");
  const [editUnique, setEditUnique] = useState(false);
  const [editAliases, setEditAliases] = useState("");
  const [addingKind, setAddingKind] = useState(null);  // null | "canonical" | "exclusion"
  const [addName, setAddName] = useState("");
  const [addUnique, setAddUnique] = useState(false);
  const [addAliases, setAddAliases] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const openEdit = (term) => {
    setEditingValue(term.role);
    setEditingKind(term.kind || KIND_CANONICAL);
    setEditName(term.role);
    setEditUnique(term.is_unique);
    setEditAliases((term.aliases || []).join("\n"));
    setAddingKind(null);
    setSaveError(null);
  };

  const openAdd = (kind) => {
    setAddingKind(kind);
    setEditingValue(null);
    setAddName("");
    setAddUnique(false);
    setAddAliases("");
    setSaveError(null);
  };

  const reset = () => { setEditingValue(null); setAddingKind(null); setSaveError(null); };

  return {
    editingValue, editingKind, editName, setEditName, editUnique, setEditUnique, editAliases, setEditAliases,
    addingKind, addName, setAddName, addUnique, setAddUnique, addAliases, setAddAliases,
    saving, setSaving, saveError, setSaveError,
    openEdit, openAdd, reset,
  };
}

// Renders one table — either the canonical roles or the exclusions for a scope.
function TermTable({ terms, kind, scope, editable, editor, onSave, onExclude, onInclude, onDelete }) {
  const [aliasModal, setAliasModal] = useState(null);
  const [confirmState, setConfirmState] = useState(null);
  const {
    editingValue, editingKind, editName, setEditName, editUnique, setEditUnique, editAliases, setEditAliases,
    addingKind, addName, setAddName, addUnique, setAddUnique, addAliases, setAddAliases,
    saving, saveError, setSaveError,
    openEdit, openAdd, reset,
  } = editor;

  // Edit / Add still flow through PUT (batched diff). Single-row actions use surgical endpoints.
  const handleSaveEdit = () => {
    onSave({ type: "edit", value: editingValue, kind: editingKind, name: editName.trim(), is_unique: editUnique, aliases: parseAliases(editAliases) }, reset, setSaveError);
  };

  const handleSaveAdd = () => {
    if (!addName.trim()) return;
    onSave({ type: "add", kind: addingKind, name: addName.trim(), is_unique: addUnique, aliases: parseAliases(addAliases) }, reset, setSaveError);
  };

  const handleExclude = (term) => setConfirmState({
    message: `Exclude "${term.role}" from ${scope}? It will move to the Exclusions list.`,
    confirmLabel: "Exclude",
    onConfirm: () => onExclude(term.role),
  });

  const handleInclude = (term) => setConfirmState({
    message: `Include "${term.role}" in ${scope}? It will move to the Roles list.`,
    confirmLabel: "Include",
    onConfirm: () => onInclude(term.role),
  });

  const handleDelete = (term) => {
    const label = kind === KIND_CANONICAL ? "role" : "exclusion";
    setConfirmState({
      message: `Remove ${label} "${term.role}" from ${scope}? This cannot be undone.`,
      confirmLabel: "Remove",
      variant: DANGER_VARIANT,
      onConfirm: () => onDelete(term.role),
    });
  };

  const isEditingThisKind = editingValue !== null && editingKind === kind;
  const isAddingThisKind = addingKind === kind;
  const showsUnique = kind === KIND_CANONICAL;

  const formContent = isEditingThisKind ? html`
    <div class="config-editor__edit-form">
      <label>${showsUnique ? "Role" : "Pattern"}
        <input type="text" readonly .value=${editName} title="Rename isn't supported yet — use Remove + Add to change the name." />
      </label>
      ${showsUnique ? html`<label class="config-editor__checkbox-label"><input type="checkbox" ?checked=${editUnique} @change=${(e) => setEditUnique(e.target.checked)} /> Unique</label>` : null}
      <label>Aliases (one per line)<br /><textarea rows="5" .value=${editAliases} @input=${(e) => setEditAliases(e.target.value)}></textarea></label>
      ${saveError ? html`<p class="config-editor__error">${saveError}</p>` : null}
    </div>
  ` : isAddingThisKind ? html`
    <div class="config-editor__edit-form">
      <label>${showsUnique ? "Role" : "Pattern"} <input type="text" .value=${addName} @input=${(e) => setAddName(e.target.value)} /></label>
      ${showsUnique ? html`<label class="config-editor__checkbox-label"><input type="checkbox" ?checked=${addUnique} @change=${(e) => setAddUnique(e.target.checked)} /> Unique</label>` : null}
      <label>Aliases (one per line)<br /><textarea rows="5" .value=${addAliases} @input=${(e) => setAddAliases(e.target.value)}></textarea></label>
      ${saveError ? html`<p class="config-editor__error">${saveError}</p>` : null}
    </div>
  ` : null;

  const formFooter = isEditingThisKind ? html`
    <button class="btn btn-sm" @click=${handleSaveEdit} ?disabled=${saving}>Save</button>
    <button class="btn btn-sm secondary" @click=${reset}>Cancel</button>
  ` : isAddingThisKind ? html`
    <button class="btn btn-sm" @click=${handleSaveAdd} ?disabled=${saving || !addName.trim()}>Add</button>
    <button class="btn btn-sm secondary" @click=${reset}>Cancel</button>
  ` : null;

  const formTitle = isEditingThisKind
    ? `Edit: ${editingValue}`
    : (kind === KIND_CANONICAL ? "Add role" : "Add exclusion");

  return html`
    <table class="config-editor__table">
      <thead>
        <tr>
          <th>${showsUnique ? "Role" : "Pattern"}</th>
          ${showsUnique ? html`<th>Unique</th>` : null}
          <th>Aliases</th>
          ${editable ? html`<th></th>` : null}
        </tr>
      </thead>
      <tbody>
        ${terms.length === 0
          ? html`<tr><td colspan=${showsUnique ? 4 : 3} class="config-editor__empty">No ${kind === KIND_CANONICAL ? "roles" : "exclusions"} yet.</td></tr>`
          : terms.map((t) => html`
              <tr>
                <td>${t.role}</td>
                ${showsUnique ? html`<td>${t.is_unique ? "Yes" : "No"}</td>` : null}
                <td
                  class=${t.aliases?.length > 1 ? "config-editor__alias-clickable" : ""}
                  @click=${() => t.aliases?.length > 1 && setAliasModal(t)}
                >${aliasLabel(t.aliases)}</td>
                ${editable ? html`
                  <td class="config-editor__actions">
                    <button class="civ-action-btn" @click=${() => openEdit(t)}>Edit</button>
                    ${kind === KIND_CANONICAL
                      ? html`<button class="civ-action-btn" @click=${() => handleExclude(t)}>Exclude</button>`
                      : html`<button class="civ-action-btn" @click=${() => handleInclude(t)}>Include</button>`}
                    <button class="civ-action-btn civ-action-btn--danger" @click=${() => handleDelete(t)}>Remove</button>
                  </td>
                ` : null}
              </tr>
            `)}
      </tbody>
    </table>
    ${editable ? html`<button class="config-editor__add-btn" @click=${() => openAdd(kind)}>+ Add ${kind === KIND_CANONICAL ? "role" : "exclusion"}</button>` : null}
    ${formContent ? html`
      <civ-modal
        .title=${formTitle}
        .content=${formContent}
        .footer=${formFooter}
        .modalProps=${{ open: true, onClose: reset }}
      ></civ-modal>
    ` : null}

    ${aliasModal ? html`
      <civ-modal
        .title=${"Aliases: " + aliasModal.role}
        .content=${html`<ul>${aliasModal.aliases.map((a) => html`<li>${a}</li>`)}</ul>`}
        .footer=${html`<button class="btn btn-sm secondary" @click=${() => setAliasModal(null)}>Close</button>`}
        .modalProps=${{ open: true, onClose: () => setAliasModal(null) }}
      ></civ-modal>
    ` : null}

    ${confirmState ? html`
      <civ-confirm-modal
        .message=${confirmState.message}
        .confirmLabel=${confirmState.confirmLabel}
        .variant=${confirmState.variant}
        @confirm=${() => { confirmState.onConfirm(); setConfirmState(null); }}
        @cancel=${() => setConfirmState(null)}
      ></civ-confirm-modal>
    ` : null}
  `;
}

customElements.define("civ-term-table", component(TermTable, { useShadowDOM: false }));

function ConfigEditor(host) {
  const jurisdictions = host.jurisdictions || [];
  const firstOcdid = jurisdictions[0]?.jurisdiction_ocdid;
  const inline = Boolean(host.inline);
  const { permissions } = useAuth();

  const stateCode = inline ? (host.stateCode || "") : seedState(jurisdictions);

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
  const [localityOptions, setLocalityOptions] = useState([]);
  const [localityOptionsMetadata, setLocalityOptionsMetadata] = useState({});
  const [localityInputValue, setLocalityInputValue] = useState("");
  const localityEditor = useTermEditor();

  const [localityFilter, setLocalityFilter] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [globalFilter, setGlobalFilter] = useState("");

  // Which scope (if any) is currently in drag-to-reorder mode. null = none.
  const [reorderingScope, setReorderingScope] = useState(null);
  const [reorderToast, setReorderToast] = useState(null);
  const [errorState, setErrorState] = useState(null);

  const showReorderToast = () => {
    setReorderToast("Roles reordered");
    setTimeout(() => setReorderToast(null), 4000);
  };

  const dispatch = (name, detail) =>
    host.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));

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
        setStateTerms(terms.filter((t) => t.source === SCOPE_STATE));
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
        setLocalityTerms(terms.filter((t) => t.source === SCOPE_LOCALITY));
      })
      .catch((e) => setLocalityError(e.message));
  };

  useEffect(() => {
    if (firstOcdid) { loadStateConfig(firstOcdid); loadLocalityConfig(firstOcdid); }
  }, []);

  useEffect(() => {
    if (permissions.can_write_config && globalTerms === null && !globalError) loadGlobal();
  }, [permissions.can_write_config]);

  useEffect(() => {
    if (!stateCode) { setStateTerms(null); setStateOcdid(null); return; }
    fetchJurisdictionForState(stateCode)
      .then((r) => {
        const ocdid = r?.data?.[0]?.jurisdiction_ocdid;
        setStateOcdid(ocdid || null);
        if (ocdid) loadStateConfig(ocdid);
        else setStateError(`No jurisdictions found for ${stateCode.toUpperCase()}`);
      })
      .catch((e) => setStateError(e.message));
  }, [stateCode]);

  useEffect(() => {
    if (!stateCode) { setLocalityOptions([]); setLocalityTerms(null); setLocalityInputValue(""); return; }
    fetchLocalitySuggestions("");
  }, [stateCode]);

  const fetchLocalitySuggestions = ({ query = "", page = 1, pageSize = 25 } = {}) => {
    if (!stateCode) return;
    const params = new URLSearchParams({ search_string: query, limit: pageSize, page });
    fetch(`/api/v1/jurisdictions/${stateCode}/search?${params}`, { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        setLocalityOptions((data.data || []).map((j) => ({ label: j.name, value: j.jurisdiction_ocdid || j.id })));
        setLocalityOptionsMetadata({ total_items: data.total_items, total_pages: data.total_pages, page: data.page, limit: data.limit, links: data.links });
      })
      .catch(() => {});
  };

  useEffect(() => {
    setReorderingScope(null);  // a scope switch invalidates an in-progress reorder
    if (localityOcdid) loadLocalityConfig(localityOcdid);
  }, [localityOcdid]);

  // PUT-based batch save (Edit / Add). Rebuilds the full term list and ships it.
  const makeBatchSave = (scope, ocdid, terms, reload, editor) => {
    return async (op, reset, setSaveError) => {
      editor.setSaving(true);
      setSaveError(null);
      try {
        let updated;
        if (op.type === "edit") {
          updated = terms.map((t) => t.role === op.value
            ? { role: op.name, is_unique: op.is_unique, aliases: op.aliases, kind: op.kind }
            : { role: t.role, is_unique: t.is_unique, aliases: t.aliases, kind: t.kind });
        } else {  // add
          updated = [
            ...terms.map((t) => ({ role: t.role, is_unique: t.is_unique, aliases: t.aliases, kind: t.kind })),
            { role: op.name, is_unique: op.is_unique, aliases: op.aliases, kind: op.kind },
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

  // Surgical single-row endpoints — atomic kind flips / hard deletes.
  const makeExclude = (scope, ocdid, reload) => async (role) => {
    try { await excludeRole(role, scope, ocdid || ""); reload(); }
    catch (e) { console.error("Exclude failed:", e); setErrorState(`Exclude failed: ${e.message}`); }
  };
  const makeInclude = (scope, ocdid, reload) => async (value) => {
    try { await includeExclusion(value, scope, ocdid || ""); reload(); }
    catch (e) { console.error("Include failed:", e); setErrorState(`Include failed: ${e.message}`); }
  };
  const makeDelete = (scope, ocdid, reload) => async (role) => {
    try { await deleteRole(role, scope, ocdid || ""); reload(); }
    catch (e) { console.error("Remove failed:", e); setErrorState(`Remove failed: ${e.message}`); }
  };

  const renderSection = (params) => {
    const {
      scope, badge, label, terms, error, loading, ocdid, reload, editor, filter, setFilter,
      editable, open,
    } = params;

    const filtered = (terms ?? []).filter(
      (t) => t.role.toLowerCase().includes(filter.toLowerCase())
    );
    const canonicals = filtered.filter((t) => (t.kind || KIND_CANONICAL) === KIND_CANONICAL);
    const exclusions = filtered.filter((t) => t.kind === KIND_EXCLUSION);

    const batchSave = makeBatchSave(scope, ocdid, terms || [], reload, editor);
    const exclude = makeExclude(scope, ocdid, reload);
    const include = makeInclude(scope, ocdid, reload);
    const remove = makeDelete(scope, ocdid, reload);

    return html`
      <details class="config-editor__section" ?open=${open}>
        <summary class="config-editor__section-title">
          <civ-badge .label=${badge} .variant=${badge}></civ-badge>
          ${label ? html`<span class="config-editor__section-label">${label}</span>` : null}
          ${terms !== null ? html`<span class="config-editor__role-count">${terms.length}</span>` : null}
          <i class="fa-solid fa-chevron-down config-editor__chevron"></i>
        </summary>
        <div class="config-editor__section-body">
          ${scope === SCOPE_LOCALITY ? html`
            ${jurisdictions.length > 0
              ? html`
                <!-- Modal mode (e.g. opened from an issue's Resolve button):
                     restrict the picker to the jurisdictions the issue is
                     tagged for. A single tagged jurisdiction gets auto-picked
                     and the dropdown is hidden entirely. -->
                ${jurisdictions.length === 1 ? null : html`
                  <label class="config-editor__locality-picker">
                    Jurisdiction
                    <select @change=${(e) => { localityEditor.reset(); setLocalityOcdid(e.target.value); }}>
                      ${jurisdictions.map((j) => html`
                        <option value=${j.jurisdiction_ocdid} ?selected=${j.jurisdiction_ocdid === localityOcdid}>
                          ${j.name || j.jurisdiction_ocdid}
                        </option>
                      `)}
                    </select>
                  </label>
                `}
              `
              : html`
                <!-- Inline mode (/roles page): full state-wide search. -->
                <div class="config-editor__locality-autocomplete">
                  <civ-autocomplete-select
                    .options=${localityOptions}
                    .optionsMetadata=${localityOptionsMetadata}
                    .inputValue=${localityInputValue}
                    .pageSize=${25}
                    @fetch-suggestions=${(e) => fetchLocalitySuggestions(e.detail)}
                    @input-change=${(e) => { setLocalityInputValue(e.detail.value); }}
                    @item-selected=${(e) => { localityEditor.reset(); setLocalityOcdid(e.detail.value); }}
                  ></civ-autocomplete-select>
                </div>
              `}
          ` : null}
          ${error ? html`<p class="config-editor__error">${error}</p>` : null}
          ${loading ? html`<div>Loading…</div>` : null}
          ${terms !== null ? html`
            ${reorderingScope === scope ? null : html`
              <div class="config-editor__filter">
                <i class="fa-solid fa-magnifying-glass config-editor__filter-icon"></i>
                <input
                  type="text"
                  class="config-editor__filter-input"
                  placeholder="Filter…"
                  .value=${filter}
                  @input=${(e) => setFilter(e.target.value)}
                >
              </div>
            `}

            ${reorderingScope === scope ? null : html`
              <div class="config-editor__subsection-header">
                <p class="config-editor__subsection-label">Roles</p>
                ${editable && canonicals.length > 1 ? html`
                  <button
                    class="btn btn-sm secondary"
                    ?disabled=${filter.length > 0}
                    title=${filter.length > 0 ? "Clear the filter to reorder" : "Reorder roles by priority"}
                    @click=${() => setReorderingScope(scope)}
                  >Reorder</button>
                ` : null}
              </div>
            `}
            ${reorderingScope === scope ? html`
              <civ-role-reorder
                .roles=${canonicals}
                .scope=${scope}
                .ocdid=${ocdid}
                @reordered=${() => { setReorderingScope(null); reload(); showReorderToast(); }}
                @cancel=${() => setReorderingScope(null)}
              ></civ-role-reorder>
            ` : html`
              <civ-term-table
                .terms=${canonicals}
                .kind=${KIND_CANONICAL}
                .scope=${scope}
                .editable=${editable}
                .editor=${editor}
                .onSave=${batchSave}
                .onExclude=${exclude}
                .onInclude=${include}
                .onDelete=${remove}
              ></civ-term-table>
            `}

            ${reorderingScope === scope ? null : html`
              <p class="config-editor__subsection-label">Exclusions</p>
              <civ-term-table
                .terms=${exclusions}
                .kind=${KIND_EXCLUSION}
                .scope=${scope}
                .editable=${editable}
                .editor=${editor}
                .onSave=${batchSave}
                .onExclude=${exclude}
                .onInclude=${include}
                .onDelete=${remove}
              ></civ-term-table>
            `}
          ` : null}
        </div>
      </details>
    `;
  };

  const localitySection = renderSection({
    scope: SCOPE_LOCALITY, badge: "locality", label: null,
    terms: localityTerms, error: localityError,
    loading: localityTerms === null && !localityError && localityOcdid,
    ocdid: localityOcdid,
    reload: () => loadLocalityConfig(localityOcdid),
    editor: localityEditor, filter: localityFilter, setFilter: setLocalityFilter,
    editable: true, open: true,
  });

  const stateSection = renderSection({
    scope: SCOPE_STATE, badge: "state", label: stateCode ? stateCode.toUpperCase() : null,
    terms: stateTerms, error: stateError,
    loading: stateTerms === null && !stateError && stateCode,
    ocdid: stateOcdid,
    reload: () => loadStateConfig(stateOcdid),
    editor: stateEditor, filter: stateFilter, setFilter: setStateFilter,
    editable: true, open: true,
  });

  const globalSection = renderSection({
    scope: SCOPE_GLOBAL, badge: "global", label: null,
    terms: globalTerms, error: globalError,
    loading: globalTerms === null && !globalError,
    ocdid: null,
    reload: loadGlobal,
    editor: globalEditor, filter: globalFilter, setFilter: setGlobalFilter,
    editable: permissions.can_write_global_config, open: true,
  });

  const content = html`
    ${permissions.can_write_config && stateCode ? localitySection : null}
    ${permissions.can_write_config && stateCode ? stateSection : null}
    ${permissions.can_write_config ? globalSection : null}
    ${reorderToast ? html`<div class="config-editor__toast" role="status" aria-live="polite">${reorderToast}</div>` : null}
    ${errorState ? html`
      <civ-confirm-modal
        .mode=${ALERT_MODE}
        .title=${"Action failed"}
        .message=${errorState}
        @confirm=${() => setErrorState(null)}
        @cancel=${() => setErrorState(null)}
      ></civ-confirm-modal>
    ` : null}
  `;

  const handleClose = () => dispatch("modal-close", {});

  if (inline) return html`<div class="config-editor__inline">${content}</div>`;

  const title = jurisdictions.length === 1
    ? "Config: " + (jurisdictions[0].name || jurisdictions[0].jurisdiction_ocdid)
    : "Config: " + (seedState(jurisdictions).toUpperCase() || "");

  return html`
    <civ-modal
      .title=${title}
      .content=${content}
      .footer=${html`<button class="btn btn-sm secondary" @click=${handleClose}>Close</button>`}
      .modalProps=${{ open: true, onClose: handleClose }}
    ></civ-modal>
  `;
}

customElements.define("issues-config-editor", component(ConfigEditor, { useShadowDOM: false }));
