import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { fetchJurisdictionConfig, putJurisdictionConfig } from "../../api.js";
import "../../components/basic/modal.js";

function parseAliases(text) {
  return text.split("\n").map((s) => s.trim()).filter(Boolean);
}

function aliasLabel(aliases) {
  if (!aliases?.length) return "—";
  if (aliases.length === 1) return aliases[0];
  return `${aliases.length} aliases`;
}

function ConfigEditor(host) {
  const ocdid = host.ocdid;
  const jurisdictionName = host.jurisdictionName;

  // "merged" | "state" | "locality"
  const [view, setView] = useState("merged");
  // per-level role lists fetched from server
  const [rolesPerLevel, setRolesPerLevel] = useState(null);
  const [loadError, setLoadError] = useState(null);

  // which row is open for editing (role name string), or null
  const [editingRole, setEditingRole] = useState(null);
  const [editName, setEditName] = useState("");
  const [editUnique, setEditUnique] = useState(false);
  const [editAliases, setEditAliases] = useState("");

  // add-role form
  const [addingRole, setAddingRole] = useState(false);
  const [addName, setAddName] = useState("");
  const [addUnique, setAddUnique] = useState(false);
  const [addAliases, setAddAliases] = useState("");

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const dispatch = (name, detail) =>
    host.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));

  const loadConfig = () => {
    setRolesPerLevel(null);
    setLoadError(null);
    fetchJurisdictionConfig(ocdid)
      .then((r) => {
        const roles = r.data?.roles || [];
        setRolesPerLevel({
          global: roles.filter((r) => r.source === "global"),
          state: roles.filter((r) => r.source === "state"),
          locality: roles.filter((r) => r.source === "locality"),
        });
      })
      .catch((e) => setLoadError(e.message));
  };

  useEffect(() => { if (ocdid) loadConfig(); }, []);

  const handleClose = () => dispatch("modal-close", {});

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

  const saveRoles = async (scope, updatedRoles) => {
    setSaving(true);
    setSaveError(null);
    try {
      await putJurisdictionConfig({ ocdid, scope, roles: updatedRoles });
      setEditingRole(null);
      setAddingRole(false);
      loadConfig();
    } catch (e) {
      setSaveError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveEdit = (scope, currentRoles) => {
    const updated = currentRoles.map((r) =>
      r.role === editingRole
        ? { role: editName.trim(), is_unique: editUnique, aliases: parseAliases(editAliases) }
        : { role: r.role, is_unique: r.is_unique, aliases: r.aliases }
    );
    saveRoles(scope, updated);
  };

  const handleSaveAdd = (scope, currentRoles) => {
    if (!addName.trim()) return;
    const updated = [
      ...currentRoles.map((r) => ({ role: r.role, is_unique: r.is_unique, aliases: r.aliases })),
      { role: addName.trim(), is_unique: addUnique, aliases: parseAliases(addAliases) },
    ];
    saveRoles(scope, updated);
  };

  const handleDelete = (scope, currentRoles, roleName) => {
    if (!confirm(`Delete role "${roleName}" from ${scope}?`)) return;
    const updated = currentRoles
      .filter((r) => r.role !== roleName)
      .map((r) => ({ role: r.role, is_unique: r.is_unique, aliases: r.aliases }));
    saveRoles(scope, updated);
  };

  const editForm = (scope, currentRoles) => html`
    <tr>
      <td colspan="99">
        <div class="issues-page__config-edit-form">
          <label>Role name <input type="text" .value=${editName} @input=${(e) => setEditName(e.target.value)} /></label>
          <label><input type="checkbox" ?checked=${editUnique} @change=${(e) => setEditUnique(e.target.checked)} /> Unique</label>
          <label>Aliases (one per line)<br /><textarea rows="4" .value=${editAliases} @input=${(e) => setEditAliases(e.target.value)}></textarea></label>
          ${saveError ? html`<p class="issues-page__config-error">${saveError}</p>` : null}
          <div class="issues-page__config-edit-actions">
            <button class="btn btn-sm" @click=${() => handleSaveEdit(scope, currentRoles)} ?disabled=${saving}>Save</button>
            <button class="btn btn-sm secondary" @click=${() => setEditingRole(null)}>Cancel</button>
          </div>
        </div>
      </td>
    </tr>
  `;

  const addForm = (scope, currentRoles) => html`
    <tr>
      <td colspan="99">
        <div class="issues-page__config-edit-form">
          <label>Role name <input type="text" .value=${addName} @input=${(e) => setAddName(e.target.value)} /></label>
          <label><input type="checkbox" ?checked=${addUnique} @change=${(e) => setAddUnique(e.target.checked)} /> Unique</label>
          <label>Aliases (one per line)<br /><textarea rows="4" .value=${addAliases} @input=${(e) => setAddAliases(e.target.value)}></textarea></label>
          ${saveError ? html`<p class="issues-page__config-error">${saveError}</p>` : null}
          <div class="issues-page__config-edit-actions">
            <button class="btn btn-sm" @click=${() => handleSaveAdd(scope, currentRoles)} ?disabled=${saving || !addName.trim()}>Add</button>
            <button class="btn btn-sm secondary" @click=${() => setAddingRole(false)}>Cancel</button>
          </div>
        </div>
      </td>
    </tr>
  `;

  const mergedTable = (allRoles) => html`
    <table class="issues-page__config-table">
      <thead>
        <tr><th>Role</th><th>Source</th><th>Unique</th><th>Aliases</th><th></th></tr>
      </thead>
      <tbody>
        ${allRoles.map((r) => html`
          <tr>
            <td>${r.role}</td>
            <td><span class="issues-page__config-source issues-page__config-source--${r.source}">${r.source}</span></td>
            <td>${r.is_unique ? "Yes" : "No"}</td>
            <td>${aliasLabel(r.aliases)}</td>
            <td></td>
          </tr>
        `)}
      </tbody>
    </table>
  `;

  const scopeTable = (scope, roles) => html`
    <table class="issues-page__config-table">
      <thead>
        <tr><th>Role</th><th>Unique</th><th>Aliases</th><th></th></tr>
      </thead>
      <tbody>
        ${roles.map((r) => html`
          <tr>
            <td>${r.role}</td>
            <td>${r.is_unique ? "Yes" : "No"}</td>
            <td>${aliasLabel(r.aliases)}</td>
            <td class="issues-page__config-actions">
              <button class="btn btn-sm secondary" @click=${() => openEdit(r)}>Edit</button>
              <button class="btn btn-sm destructive" @click=${() => handleDelete(scope, roles, r.role)}>Del</button>
            </td>
          </tr>
          ${editingRole === r.role ? editForm(scope, roles) : null}
        `)}
        ${addingRole ? addForm(scope, roles) : null}
      </tbody>
    </table>
    <button class="btn btn-sm" @click=${openAdd}>+ Add role</button>
  `;

  const content = html`
    <div class="issues-page__config-view-toggle">
      ${["merged", "state", "locality"].map((v) => html`
        <button
          class="issues-page__config-toggle-btn${view === v ? " issues-page__config-toggle-btn--active" : ""}"
          @click=${() => { setView(v); setEditingRole(null); setAddingRole(false); setSaveError(null); }}
        >${v === "merged" ? "Merged" : v.charAt(0).toUpperCase() + v.slice(1)}</button>
      `)}
    </div>
    ${loadError ? html`<p class="issues-page__config-error">${loadError}</p>` : null}
    ${rolesPerLevel === null && !loadError ? html`<div>Loading…</div>` : null}
    ${rolesPerLevel ? html`
      ${view === "merged"
        ? mergedTable([...rolesPerLevel.global, ...rolesPerLevel.state, ...rolesPerLevel.locality])
        : scopeTable(view, rolesPerLevel[view] || [])}
    ` : null}
  `;

  return html`
    <civ-modal
      .title=${"Config: " + (jurisdictionName || ocdid)}
      .content=${content}
      .footer=${html`<button class="btn btn-sm secondary" @click=${handleClose}>Close</button>`}
      .modalProps=${{ open: true, onClose: handleClose }}
    ></civ-modal>
  `;
}

customElements.define("issues-config-editor", component(ConfigEditor, { useShadowDOM: false }));
