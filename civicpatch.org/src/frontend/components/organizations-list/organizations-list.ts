import "./organizations-list.css";
import "./organization-edit.js";
import "./organization-add.js";
import "../posts-list/post-form.js";
import "../action-btn/action-btn.css";
import "../badge/badge.js";
import { html, type TemplateResult } from "lit-html";
import { component, useState } from "haunted";
import {
  fetchOrganizations,
  deleteOrganization,
  setDefaultOrganization,
} from "../../api-organizations.js";
import { deletePost } from "../../api-posts.js";
import { useAsyncData } from "../../hooks/use-async-data.js";
import { useJurisdictionRoles } from "../../hooks/use-jurisdiction-roles.js";
import {
  defaultOrganizationId,
  mergeTargets,
  type Organization,
  type OrganizationPost,
} from "./organizations-model.js";
import type { Post } from "../posts-list/posts-model.js";

type OrganizationsListHost = HTMLElement & {
  jurisdictionOcdid?: string;
  canManage?: boolean;
};

// Named for the entity, not the action — see posts-list.ts's own Editing type.
type Editing =
  | { entity: "organization"; id: string | null }
  | { entity: "post"; organizationId: string }
  | null;

type RowActions = {
  onEdit: (id: string) => void;
  onRemove: (id: string) => void;
  onMakeDefault: (id: string) => void;
};

type Deleting = { postId: string; intoPostId: string } | null;

type PostActions = {
  onDelete: (postId: string) => void;
  onPickInto: (intoPostId: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
};

const organizationName = (organizations: Organization[], id: string) =>
  organizations.find((organization) => organization.id === id)?.name ?? "";

const renderMoveTo = (
  holders: string,
  targets: Post[],
  organizations: Organization[],
  intoPostId: string,
  actions: PostActions,
) => html`
  <label>
    Move ${holders} to:
    <select
      .value=${intoPostId}
      @change=${(e: Event) => actions.onPickInto((e.target as HTMLSelectElement).value)}
    >
      <option value="">Pick a post</option>
      ${targets.map(
        (target) => html`<option value=${target.id}>
          ${organizationName(organizations, target.organization_id)}, ${target.label}
        </option>`,
      )}
    </select>
  </label>
  <button class="civ-action-btn" ?disabled=${!intoPostId} @click=${actions.onConfirm}>Delete</button>
`;

const renderDeleteConfirm = (
  post: OrganizationPost,
  targets: Post[],
  organizations: Organization[],
  intoPostId: string,
  actions: PostActions,
) => {
  const holders = post.holder_names.join(", ");
  const body = !post.holder_names.length
    ? html`<span>Delete this post?</span>
        <button class="civ-action-btn" @click=${actions.onConfirm}>Delete</button>`
    : targets.length
      ? renderMoveTo(holders, targets, organizations, intoPostId, actions)
      : html`<span>
          Held by ${holders}. To delete it, first add a ${post.label} post for the same division
          to another organization, then move them there.
        </span>`;
  return html`
    <div class="organizations-list__delete-confirm">
      ${body}
      <button class="civ-action-btn" @click=${actions.onCancel}>Cancel</button>
    </div>
  `;
};

const renderPost = (
  post: OrganizationPost,
  organizations: Organization[],
  deleting: Deleting,
  actions: PostActions,
) => html`
  <li class="organizations-list__post">
    <div class="organizations-list__post-line">
      <span>${post.label}</span>
      ${deleting?.postId === post.id
        ? ""
        : html`<button
            class="civ-action-btn"
            aria-label=${`Delete ${post.label}`}
            @click=${() => actions.onDelete(post.id)}
          >
            Delete
          </button>`}
    </div>
    ${deleting?.postId === post.id
      ? renderDeleteConfirm(
          post,
          mergeTargets(organizations, post),
          organizations,
          deleting.intoPostId,
          actions,
        )
      : ""}
  </li>
`;

const renderPosts = (
  organization: Organization,
  organizations: Organization[],
  deleting: Deleting,
  actions: PostActions,
  addPost: TemplateResult,
) => html`
  <div class="organizations-list__posts">
    <ul class="organizations-list__post-rows">
      ${organization.posts.map((post) => renderPost(post, organizations, deleting, actions))}
    </ul>
    ${addPost}
  </div>
`;

// Edit and Remove are off while organizations come only from the config sync (the routes are too).
const renderActions = (organization: Organization, isDefault: boolean, actions: RowActions) => html`
  <span class="organizations-list__actions">
    ${isDefault
      ? ""
      : html`<button class="civ-action-btn" @click=${() => actions.onMakeDefault(organization.id)}>
          Make default
        </button>`}
  </span>
`;
// <button class="civ-action-btn" @click=${() => actions.onEdit(organization.id)}>Edit</button>
// ${!isDefault && organization.posts.length === 0
//   ? html`<button class="civ-action-btn" @click=${() => actions.onRemove(organization.id)}>
//       Remove
//     </button>`
//   : ""}

const renderOrganization = (
  organization: Organization,
  isDefault: boolean,
  canManage: boolean,
  actions: RowActions,
) => html`
  <div class="organizations-list__row">
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
  </div>
`;

function OrganizationsList(host: OrganizationsListHost) {
  const [editing, setEditing] = useState<Editing>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Deleting>(null);
  const ocdid = host.jurisdictionOcdid;
  const canManage = !!host.canManage;
  const roles = useJurisdictionRoles();

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

  // const handleAdd = () => setEditing({ entity: "organization", id: null });
  const runAndReload = async (request: () => Promise<unknown>) => {
    setError(null);
    try {
      await request();
      reload();
    } catch (cause) {
      setError(String(cause).replace(/^Error:\s*/, ""));
    }
  };
  const actions: RowActions = {
    onEdit: (id) => setEditing({ entity: "organization", id }),
    onRemove: (id) => runAndReload(() => deleteOrganization(id)),
    onMakeDefault: (id) => runAndReload(() => setDefaultOrganization(id)),
  };
  const postActions: PostActions = {
    onDelete: (postId) => setDeleting({ postId, intoPostId: "" }),
    onPickInto: (intoPostId) => deleting && setDeleting({ ...deleting, intoPostId }),
    onConfirm: () => {
      if (!deleting) return;
      setDeleting(null);
      runAndReload(() => deletePost(deleting.postId, deleting.intoPostId || null));
    },
    onCancel: () => setDeleting(null),
  };

  // civ-post-form's `added` and `cancel` bubble to the list's own handlers below.
  const addPost = (organization: Organization) =>
    editing?.entity === "post" && editing.organizationId === organization.id
      ? html`<civ-post-form
          .jurisdictionOcdid=${ocdid ?? ""}
          .organizationId=${organization.id}
          .roles=${roles}
        ></civ-post-form>`
      : html`<button
          class="civ-action-btn"
          @click=${() => setEditing({ entity: "post", organizationId: organization.id })}
        >
          Add post
        </button>`;

  // Add organization is off while organizations come only from the config sync.
  // const controls = canManage
  //   ? html`<div class="organizations-list__controls">
  //       <button class="civ-action-btn" @click=${handleAdd}>Add organization</button>
  //     </div>`
  //   : "";
  const controls = "";

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
      ${error ? html`<p class="posts-list__error">${error}</p>` : ""}
      <ul class="organizations-list__rows">
        ${data.map(
          (organization) => html`<li class="organizations-list__organization">
            ${editingOrganization?.id === organization.id
              ? html`<civ-organization-edit .organization=${organization}></civ-organization-edit>`
              : renderOrganization(organization, organization.id === defaultId, canManage, actions)}
            ${canManage
              ? renderPosts(organization, data, deleting, postActions, addPost(organization))
              : ""}
          </li>`,
        )}
      </ul>
      ${editing?.entity === "organization" && editing.id === null
        ? html`<civ-organization-add .jurisdictionOcdid=${ocdid ?? ""}></civ-organization-add>`
        : controls}
    </div>
  `;
}

customElements.define(
  "civ-organizations-list",
  component(OrganizationsList, { useShadowDOM: false }),
);
