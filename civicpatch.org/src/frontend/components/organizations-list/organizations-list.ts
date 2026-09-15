import "./organizations-list.css";
import "./organization-edit.js";
import "./organization-add.js";
import "../action-btn/action-btn.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { fetchOrganizations, deleteOrganization } from "../../api-organizations.js";
import { useAsyncData } from "../../hooks/use-async-data.js";
import type { Organization } from "./organizations-model.js";

type OrganizationsListHost = HTMLElement & {
  jurisdictionOcdid?: string;
  canManage?: boolean;
};

// Named for the entity, not the action — see posts-list.ts's own Editing type.
type Editing = { entity: "organization"; id: string | null } | null;

const renderOrganization = (
  organization: Organization,
  canManage: boolean,
  onEdit: (id: string) => void,
  onRemove: (id: string) => void,
) => html`
  <li class="organizations-list__row">
    <span class="organizations-list__name">${organization.name}</span>
    ${organization.url
      ? html`<a class="organizations-list__url" href=${organization.url} target="_blank" rel="noopener">
          ${organization.url}
        </a>`
      : ""}
    <span class="organizations-list__capacity">
      ${organization.posts.length} post${organization.posts.length === 1 ? "" : "s"}
    </span>
    ${canManage
      ? html`
          <button class="civ-action-btn" @click=${() => onEdit(organization.id)}>Edit</button>
          ${organization.posts.length === 0
            ? html`<button class="civ-action-btn" @click=${() => onRemove(organization.id)}>
                Remove
              </button>`
            : ""}
        `
      : ""}
  </li>
`;

function OrganizationsList(host: OrganizationsListHost) {
  const [editing, setEditing] = useState<Editing>(null);
  const [error, setError] = useState<string | null>(null);
  const ocdid = host.jurisdictionOcdid;
  const canManage = !!host.canManage;

  const { data, error: loadError, reload } = useAsyncData<Organization[]>(async () => {
    if (!ocdid) return [];
    const body = await fetchOrganizations(ocdid);
    return body.data.organizations;
  }, [ocdid]);

  const closeAndReload = () => {
    setEditing(null);
    reload();
  };
  const close = () => setEditing(null);

  const handleAdd = () => setEditing({ entity: "organization", id: null });
  const handleRemove = async (id: string) => {
    setError(null);
    try {
      await deleteOrganization(id);
      reload();
    } catch (cause) {
      setError(String(cause).replace(/^Error:\s*/, ""));
    }
  };

  const controls = html`
    <div class="posts-list__controls">
      ${canManage
        ? html`<button class="civ-action-btn" @click=${handleAdd}>Add organization</button>`
        : ""}
    </div>
  `;

  if (loadError) {
    return html`<p class="posts-list__error">Could not load organizations: ${loadError}</p>`;
  }
  if (data === null) {
    return html`<p class="posts-list__empty">Loading…</p>`;
  }

  const editingOrganization =
    editing?.entity === "organization" && editing.id
      ? data.find((organization) => organization.id === editing.id)
      : undefined;

  return html`
    <div class="organizations-list" @saved=${closeAndReload} @added=${closeAndReload} @cancel=${close}>
      ${controls}
      ${error ? html`<p class="posts-list__error">${error}</p>` : ""}
      ${editingOrganization
        ? html`<civ-organization-edit .organization=${editingOrganization}></civ-organization-edit>`
        : ""}
      ${editing?.entity === "organization" && editing.id === null
        ? html`<civ-organization-add .jurisdictionOcdid=${ocdid ?? ""}></civ-organization-add>`
        : ""}
      <ul class="organizations-list__rows">
        ${data.map((organization) =>
          renderOrganization(organization, canManage, (id) =>
            setEditing({ entity: "organization", id }), handleRemove),
        )}
      </ul>
    </div>
  `;
}

customElements.define(
  "civ-organizations-list",
  component(OrganizationsList, { useShadowDOM: false }),
);
