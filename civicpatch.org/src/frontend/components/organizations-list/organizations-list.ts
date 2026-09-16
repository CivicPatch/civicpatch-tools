import "./organizations-list.css";
import "./organization-edit.js";
import "./organization-add.js";
import "../action-btn/action-btn.css";
import "../badge/badge.js";
import { html } from "lit-html";
import { component, useState } from "haunted";
import {
  fetchOrganizations,
  deleteOrganization,
  setDefaultOrganization,
} from "../../api-organizations.js";
import { movePost } from "../../api.js";
import { inputValue } from "../fields/field-controls.js";
import { useAsyncData } from "../../hooks/use-async-data.js";
import { defaultOrganizationId, type Organization } from "./organizations-model.js";

type OrganizationsListHost = HTMLElement & {
  jurisdictionOcdid?: string;
  canManage?: boolean;
};

// Named for the entity, not the action — see posts-list.ts's own Editing type.
type Editing = { entity: "organization"; id: string | null } | null;

type RowActions = {
  onEdit: (id: string) => void;
  onRemove: (id: string) => void;
  onMakeDefault: (id: string) => void;
  onMovePost: (postId: string, e: Event) => void;
};

const NOT_MOVING = "";

const renderPosts = (organization: Organization, others: Organization[], actions: RowActions) => html`
  <li class="organizations-list__posts">
    <ul class="organizations-list__post-rows">
      ${organization.posts.map(
        (post) => html`
          <li class="organizations-list__post">
            <span>${post.label}</span>
            ${others.length
              ? html`<select
                  aria-label="Move ${post.label} to another organization"
                  @change=${(e: Event) => actions.onMovePost(post.id, e)}
                >
                  <option value=${NOT_MOVING} selected>Move to…</option>
                  ${others.map((other) => html`<option value=${other.id}>${other.name}</option>`)}
                </select>`
              : ""}
          </li>
        `,
      )}
    </ul>
  </li>
`;

const renderActions = (organization: Organization, isDefault: boolean, actions: RowActions) => html`
  <span class="organizations-list__actions">
    <button class="civ-action-btn" @click=${() => actions.onEdit(organization.id)}>Edit</button>
    ${isDefault
      ? ""
      : html`<button class="civ-action-btn" @click=${() => actions.onMakeDefault(organization.id)}>
          Make default
        </button>`}
    ${!isDefault && organization.posts.length === 0
      ? html`<button class="civ-action-btn" @click=${() => actions.onRemove(organization.id)}>
          Remove
        </button>`
      : ""}
  </span>
`;

const renderOrganization = (
  organization: Organization,
  isDefault: boolean,
  canManage: boolean,
  actions: RowActions,
) => html`
  <li class="organizations-list__row">
    <span class="organizations-list__name">
      ${organization.name}
      ${isDefault ? html`<civ-badge .label=${"default"} .variant=${"secondary"}></civ-badge>` : ""}
    </span>
    <span class="organizations-list__url">
      ${organization.url
        ? html`<a href=${organization.url} target="_blank" rel="noopener">${organization.url}</a>`
        : ""}
    </span>
    <span class="organizations-list__capacity">
      ${organization.posts.length} post${organization.posts.length === 1 ? "" : "s"}
    </span>
    ${canManage ? renderActions(organization, isDefault, actions) : ""}
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
  const runAndReload = async (request: () => Promise<unknown>) => {
    setError(null);
    try {
      await request();
      reload();
    } catch (cause) {
      setError(String(cause).replace(/^Error:\s*/, ""));
    }
  };
  const handleMovePost = (postId: string, e: Event) => {
    const organizationId = inputValue(e);
    // A refused move leaves the list unchanged, so the select would keep showing the choice.
    (e.target as HTMLSelectElement).value = NOT_MOVING;
    if (organizationId !== NOT_MOVING) runAndReload(() => movePost(postId, organizationId));
  };
  const actions: RowActions = {
    onEdit: (id) => setEditing({ entity: "organization", id }),
    onRemove: (id) => runAndReload(() => deleteOrganization(id)),
    onMakeDefault: (id) => runAndReload(() => setDefaultOrganization(id)),
    onMovePost: handleMovePost,
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
  const defaultId = defaultOrganizationId(data);

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
        ${data.map(
          (organization) => html`
            ${renderOrganization(organization, organization.id === defaultId, canManage, actions)}
            ${canManage && organization.posts.length
              ? renderPosts(
                  organization,
                  data.filter((other) => other.id !== organization.id),
                  actions,
                )
              : ""}
          `,
        )}
      </ul>
    </div>
  `;
}

customElements.define(
  "civ-organizations-list",
  component(OrganizationsList, { useShadowDOM: false }),
);
