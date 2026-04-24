import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { fetchJurisdictionConfig, putJurisdictionConfig, fetchGlobalConfig, putGlobalConfig, fetchJurisdictionForState } from "../../api.js";
import { useAuth } from "../../hooks/useAuth.js";
import "../../components/basic/modal.js";
import "../../components/badge/badge.js";
import "../../components/inputs/auto-complete-select.js";

const SCOPE_GLOBAL = "global";
const SCOPE_STATE = "state";
const SCOPE_LOCALITY = "locality";

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

function useRoleEditor() {
  const [editingRole, setEditingRole] = useState(null);
  const [editName, setEditName] = useState("");
  const [editUnique, setEditUnique] = useState(false);
  const [editAliases, setEditAliases] = useState("");
  const [addingRole, setAddingRole] = useState(false);
  const [addName, setAddName] = useState("");
  const [addUnique, setAddUnique] = useState(false);
  const [addAliases, setAddAliases] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const openEdit = (role) => {
    setEditingRole(role.role);
    setEditName(role.role);
    setEditUnique(role.is_unique);
    setEditAliases((role.aliases || []).join("\n"));
    setAddingRole(false);
    setSaveError(null);
  };

  const openAdd = () => {
    setAddingRole(true);
    setEditingRole(null);
    setAddName("");
    setAddUnique(false);
    setAddAliases("");
    setSaveError(null);
  };

  const reset = () => { setEditingRole(null); setAddingRole(false); setSaveError(null); };

  return {
    editingRole, editName, setEditName, editUnique, setEditUnique, editAliases, setEditAliases,
    addingRole, addName, setAddName, addUnique, setAddUnique, addAliases, setAddAliases,
    saving, setSaving, saveError, setSaveError,
    openEdit, openAdd, reset,
  };
}

function RoleTable({ roles, scope, editable, editor, onSave }) {
  const [aliasModal, setAliasModal] = useState(null);
  const {
    editingRole, editName, setEditName, editUnique, setEditUnique, editAliases, setEditAliases,
    addingRole, addName, setAddName, addUnique, setAddUnique, addAliases, setAddAliases,
    saving, saveError, setSaveError,
    openEdit, openAdd, reset,
  } = editor;

  const handleSaveEdit = () => {
    const updated = roles.map((r) =>
      r.role === editingRole
        ? { role: editName.trim(), is_unique: editUnique, aliases: parseAliases(editAliases) }
        : { role: r.role, is_unique: r.is_unique, aliases: r.aliases }
    );
    onSave(updated, reset, setSaveError, saving);
  };

  const handleSaveAdd = () => {
    if (!addName.trim()) return;
    const updated = [
      ...roles.map((r) => ({ role: r.role, is_unique: r.is_unique, aliases: r.aliases })),
      { role: addName.trim(), is_unique: addUnique, aliases: parseAliases(addAliases) },
    ];
    onSave(updated, reset, setSaveError, saving);
  };

  const handleDelete = (roleName) => {
    if (!confirm(`Delete role "${roleName}" from ${scope}?`)) return;
    const updated = roles
      .filter((r) => r.role !== roleName)
      .map((r) => ({ role: r.role, is_unique: r.is_unique, aliases: r.aliases }));
    onSave(updated, reset, setSaveError, saving);
  };

  const formContent = editingRole !== null ? html`
    <div class="issues-page__config-edit-form">
      <label>Role name <input type="text" .value=${editName} @input=${(e) => setEditName(e.target.value)} /></label>
      <label class="issues-page__config-checkbox-label"><input type="checkbox" ?checked=${editUnique} @change=${(e) => setEditUnique(e.target.checked)} /> Unique</label>
      <label>Aliases (one per line)<br /><textarea rows="5" .value=${editAliases} @input=${(e) => setEditAliases(e.target.value)}></textarea></label>
      ${saveError ? html`<p class="issues-page__config-error">${saveError}</p>` : null}
    </div>
  ` : addingRole ? html`
    <div class="issues-page__config-edit-form">
      <label>Role name <input type="text" .value=${addName} @input=${(e) => setAddName(e.target.value)} /></label>
      <label class="issues-page__config-checkbox-label"><input type="checkbox" ?checked=${addUnique} @change=${(e) => setAddUnique(e.target.checked)} /> Unique</label>
      <label>Aliases (one per line)<br /><textarea rows="5" .value=${addAliases} @input=${(e) => setAddAliases(e.target.value)}></textarea></label>
      ${saveError ? html`<p class="issues-page__config-error">${saveError}</p>` : null}
    </div>
  ` : null;

  const formFooter = editingRole !== null ? html`
    <button class="btn btn-sm" @click=${handleSaveEdit} ?disabled=${saving}>Save</button>
    <button class="btn btn-sm secondary" @click=${reset}>Cancel</button>
  ` : addingRole ? html`
    <button class="btn btn-sm" @click=${handleSaveAdd} ?disabled=${saving || !addName.trim()}>Add</button>
    <button class="btn btn-sm secondary" @click=${reset}>Cancel</button>
  ` : null;

  const formTitle = editingRole !== null ? `Edit: ${editingRole}` : "Add role";

  return html`
    <table class="issues-page__config-table">
      <thead>
        <tr>
          <th>Role</th><th>Unique</th><th>Aliases</th>
          ${editable ? html`<th></th>` : null}
        </tr>
      </thead>
      <tbody>
        ${roles.map((r) => html`
          <tr>
            <td>${r.role}</td>
            <td>${r.is_unique ? "Yes" : "No"}</td>
            <td
              class=${r.aliases?.length > 1 ? "issues-page__alias-clickable" : ""}
              @click=${() => r.aliases?.length > 1 && setAliasModal(r)}
            >${aliasLabel(r.aliases)}</td>
            ${editable ? html`
              <td class="issues-page__config-actions">
                <button class="btn btn-sm secondary" @click=${() => openEdit(r)}>Edit</button>
                <button class="btn btn-sm destructive" @click=${() => handleDelete(r.role)}>Del</button>
              </td>
            ` : null}
          </tr>
        `)}
      </tbody>
    </table>
    ${editable ? html`<button class="btn btn-sm" @click=${openAdd}>+ Add role</button>` : null}
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
  `;
}

customElements.define("civ-role-table", component(RoleTable, { useShadowDOM: false }));

function ConfigSection({ title, badge, roles, loading, error, editable, onSave }) {
  return html`
    <div class="issues-page__config-section">
      <h4 class="issues-page__config-section-title">
        ${title}
        <civ-badge .label=${badge} .variant=${badge}></civ-badge>
        ${!editable ? html`<span class="issues-page__config-readonly">read-only</span>` : null}
      </h4>
      ${error ? html`<p class="issues-page__config-error">${error}</p>` : null}
      ${loading ? html`<div>Loading…</div>` : null}
      ${roles !== null && !loading
        ? html`<civ-role-table
            .roles=${roles}
            .scope=${badge}
            .editable=${editable}
            .editor=${onSave.__editor}
            .onSave=${onSave}
          ></civ-role-table>`
        : null}
    </div>
  `;
}

customElements.define("civ-config-section", component(ConfigSection, { useShadowDOM: false }));

function ConfigEditor(host) {
  const jurisdictions = host.jurisdictions || [];
  const firstOcdid = jurisdictions[0]?.jurisdiction_ocdid;
  const inline = Boolean(host.inline);
  const { permissions } = useAuth();

  const stateCode = inline ? (host.stateCode || "") : seedState(jurisdictions);

  // Global config
  const [globalRoles, setGlobalRoles] = useState(null);
  const [globalError, setGlobalError] = useState(null);
  const globalEditor = useRoleEditor();

  // State config
  const [stateOcdid, setStateOcdid] = useState(firstOcdid || null);
  const [stateRoles, setStateRoles] = useState(null);
  const [stateError, setStateError] = useState(null);
  const stateEditor = useRoleEditor();

  // Locality config
  const [localityOcdid, setLocalityOcdid] = useState(firstOcdid || null);
  const [localityRoles, setLocalityRoles] = useState(null);
  const [localityError, setLocalityError] = useState(null);
  const [localityOptions, setLocalityOptions] = useState([]);
  const [localityOptionsMetadata, setLocalityOptionsMetadata] = useState({});
  const [localityInputValue, setLocalityInputValue] = useState("");
  const localityEditor = useRoleEditor();

  const dispatch = (name, detail) =>
    host.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));

  const loadGlobal = () => {
    setGlobalRoles(null);
    setGlobalError(null);
    fetchGlobalConfig()
      .then((r) => setGlobalRoles(r.data?.roles || []))
      .catch((e) => setGlobalError(e.message));
  };

  const loadStateConfig = (ocdid) => {
    if (!ocdid) return;
    setStateRoles(null);
    setStateError(null);
    fetchJurisdictionConfig(ocdid)
      .then((r) => {
        const roles = r.data?.roles || [];
        setStateRoles(roles.filter((r) => r.source === SCOPE_STATE));
      })
      .catch((e) => setStateError(e.message));
  };

  const loadLocalityConfig = (ocdid) => {
    if (!ocdid) return;
    setLocalityRoles(null);
    setLocalityError(null);
    fetchJurisdictionConfig(ocdid)
      .then((r) => {
        const roles = r.data?.roles || [];
        setLocalityRoles(roles.filter((r) => r.source === SCOPE_LOCALITY));
      })
      .catch((e) => setLocalityError(e.message));
  };

  useEffect(() => {
    if (firstOcdid) { loadStateConfig(firstOcdid); loadLocalityConfig(firstOcdid); }
  }, []);

  useEffect(() => {
    if (permissions.CONFIG_WRITE && globalRoles === null && !globalError) loadGlobal();
  }, [permissions.CONFIG_WRITE]);

  useEffect(() => {
    if (!stateCode) { setStateRoles(null); setStateOcdid(null); return; }
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
    if (!stateCode) { setLocalityOptions([]); setLocalityRoles(null); setLocalityInputValue(""); return; }
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
    if (localityOcdid) loadLocalityConfig(localityOcdid);
  }, [localityOcdid]);

  const makeSave = (scope, ocdid, reload, editor) => {
    const fn = async (updatedRoles, reset, setSaveError) => {
      editor.setSaving(true);
      setSaveError(null);
      try {
        if (scope === SCOPE_GLOBAL) {
          await putGlobalConfig(updatedRoles);
          loadGlobal();
        } else {
          await putJurisdictionConfig({ ocdid, scope, roles: updatedRoles });
          reload(ocdid);
        }
        reset();
      } catch (e) {
        setSaveError(e.message);
      } finally {
        editor.setSaving(false);
      }
    };
    fn.__editor = editor;
    return fn;
  };

  const handleClose = () => dispatch("modal-close", {});

  const content = html`
    ${permissions.CONFIG_WRITE ? html`
      <div class="issues-page__config-section">
        <h4 class="issues-page__config-section-title">
          <civ-badge .label=${"global"} .variant=${"global"}></civ-badge>
        </h4>
        ${globalError ? html`<p class="issues-page__config-error">${globalError}</p>` : null}
        ${globalRoles === null && !globalError ? html`<div>Loading…</div>` : null}
        ${globalRoles !== null ? html`<civ-role-table
          .roles=${globalRoles}
          .scope=${SCOPE_GLOBAL}
          .editable=${permissions.CONFIG_GLOBAL_WRITE}
          .editor=${globalEditor}
          .onSave=${makeSave(SCOPE_GLOBAL, null, null, globalEditor)}
        ></civ-role-table>` : null}
      </div>
    ` : null}

    ${permissions.CONFIG_WRITE && stateCode ? html`
      <div class="issues-page__config-section">
        <h4 class="issues-page__config-section-title">
          <civ-badge .label=${"state"} .variant=${"state"}></civ-badge>
          ${stateCode ? html`<span class="issues-page__config-section-label">${stateCode.toUpperCase()}</span>` : null}
        </h4>
        ${stateError ? html`<p class="issues-page__config-error">${stateError}</p>` : null}
        ${stateRoles === null && !stateError && stateCode ? html`<div>Loading…</div>` : null}
        ${stateRoles !== null ? html`<civ-role-table
          .roles=${stateRoles}
          .scope=${SCOPE_STATE}
          .editable=${true}
          .editor=${stateEditor}
          .onSave=${makeSave(SCOPE_STATE, stateOcdid, loadStateConfig, stateEditor)}
        ></civ-role-table>` : null}
      </div>
    ` : null}

    ${permissions.CONFIG_WRITE && stateCode ? html`
      <div class="issues-page__config-section">
        <h4 class="issues-page__config-section-title">
          <civ-badge .label=${"locality"} .variant=${"locality"}></civ-badge>
          <div class="issues-page__config-locality-autocomplete">
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
        </h4>
        ${localityError ? html`<p class="issues-page__config-error">${localityError}</p>` : null}
        ${localityRoles === null && !localityError && localityOcdid ? html`<div>Loading…</div>` : null}
        ${localityRoles !== null ? html`<civ-role-table
          .roles=${localityRoles}
          .scope=${SCOPE_LOCALITY}
          .editable=${true}
          .editor=${localityEditor}
          .onSave=${makeSave(SCOPE_LOCALITY, localityOcdid, loadLocalityConfig, localityEditor)}
        ></civ-role-table>` : null}
      </div>
    ` : null}
  `;

  if (inline) return html`<div class="issues-page__config-inline">${content}</div>`;

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
