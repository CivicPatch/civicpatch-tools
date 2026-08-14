import "./config-editor.css";
import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { fetchRoles, putRoles, deleteRole } from "../../api.js";
import { useAuth } from "../../hooks/useAuth.js";
import "../../components/basic/modal.js";
import "../../components/badge/badge.js";
import "../../components/role-reorder/role-reorder.ts";
import {
  ALERT_MODE,
  DANGER_VARIANT,
} from "../../components/confirm-modal/confirm-modal.ts";

const STATUS_ACTIVE = "active";
const STATUS_CANDIDATE = "candidate";
const STATUS_EXCLUDED = "excluded";
const STATUS_INACTIVE = "inactive";

const STATUS_OPTIONS = [
  STATUS_ACTIVE,
  STATUS_CANDIDATE,
  STATUS_EXCLUDED,
  STATUS_INACTIVE,
];

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
    setEditingValue(term.label);
    setEditName(term.label);
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

function TermTable({ terms, editable, editor, onSave, onDelete }) {
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
    setConfirmState({
      message: `Remove role "${term.label}"? It stops matching, but is kept so any seat history survives.`,
      confirmLabel: "Remove",
      variant: DANGER_VARIANT,
      onConfirm: () => onDelete(term.id),
    });
  };

  const statusBadge = (status) => {
    if (!status || status === STATUS_ACTIVE) return "";
    return ` (${status})`;
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
                  <td>${t.label}</td>
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
  const inline = Boolean(host.inline);
  const { permissions } = useAuth();

  const [terms, setTerms] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const editor = useTermEditor();

  const [filter, setFilter] = useState("");
  const [reordering, setReordering] = useState(false);
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

  const load = () => {
    setTerms(null);
    setLoadError(null);
    fetchRoles()
      .then((r) => setTerms(r.data?.roles || []))
      .catch((e) => setLoadError(e.message));
  };

  useEffect(() => {
    if (permissions.can_write_config && terms === null && !loadError) load();
  }, [permissions.can_write_config]);

  // The taxonomy is one flat global list, so a save sends every role back —
  // absence is not removal, but an edit still has to carry the others through.
  const handleSave = async (op, reset, setSaveError) => {
    editor.setSaving(true);
    setSaveError(null);
    try {
      const asPayload = (t) => ({
        label: t.label,
        status: t.status || STATUS_ACTIVE,
        is_unique: t.is_unique,
        aliases: t.aliases,
      });
      const edited = {
        label: op.label,
        status: op.status,
        is_unique: op.is_unique,
        aliases: op.aliases,
      };
      const updated =
        op.type === "edit"
          ? (terms || []).map((t) => (t.label === op.value ? edited : asPayload(t)))
          : [...(terms || []).map(asPayload), edited];

      await putRoles({ roles: updated });
      load();
      reset();
    } catch (e) {
      setSaveError(e.message);
    } finally {
      editor.setSaving(false);
    }
  };

  const handleDelete = async (roleId) => {
    try {
      await deleteRole(roleId);
      load();
    } catch (e) {
      console.error("Remove failed:", e);
      setErrorState(`Remove failed: ${e.message}`);
    }
  };

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
            ${reordering
              ? html`
                  <civ-role-reorder
                    .roles=${filtered}
                    @reordered=${() => {
                      setReordering(false);
                      load();
                      showReorderToast();
                    }}
                    @cancel=${() => setReordering(false)}
                  ></civ-role-reorder>
                `
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
                  <div class="config-editor__subsection-header">
                    <p class="config-editor__subsection-label">
                      Roles
                      <span class="config-editor__role-count"
                        >${terms.length}</span
                      >
                    </p>
                    ${permissions.can_write_global_config && filtered.length > 1
                      ? html`
                          <button
                            class="btn btn-sm secondary"
                            ?disabled=${filter.length > 0}
                            title=${filter.length > 0
                              ? "Clear the filter to reorder"
                              : "Reorder roles by priority"}
                            @click=${() => setReordering(true)}
                          >
                            Reorder
                          </button>
                        `
                      : null}
                  </div>
                  <civ-term-table
                    .terms=${filtered}
                    .editable=${permissions.can_write_config}
                    .editor=${editor}
                    .onSave=${handleSave}
                    .onDelete=${handleDelete}
                  ></civ-term-table>
                `}
          `
        : null}
    </div>
  `;

  const content = html`
    ${permissions.can_write_config ? rolesSection : null}
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
