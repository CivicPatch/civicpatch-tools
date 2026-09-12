import "./posts-list.css";
import "./post-edit.js";
import "./post-add.js";
import "../action-btn/action-btn.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { fetchPosts, fetchMemberships, fetchRoles } from "../../api.js";
import { useAsyncData } from "../../hooks/use-async-data.js";
import { groupPostsByRole, divisionName } from "./posts-model.js";
import type { RoleGroup, PostRow, RoleOption } from "./posts-model.js";

type PostsListHost = HTMLElement & {
  jurisdictionOcdid?: string;
  // Same gate as people editing on this page: a scrape still awaiting review blocks both, so
  // the roster and the posts describing it cannot drift while a change is in flight.
  canEdit?: boolean;
};

// Named for the entity, not the action: adding and editing a post are the same entity with and
// without an id, so `id: null` is "this post does not exist yet" rather than a third case.
type Editing = { entity: "post"; id: string | null } | null;

// Who holds it is the Officials panel's job — this row says only how many hold the seat,
// not by whom, so it stays a count rather than a name.
const renderPost = (post: PostRow, canEdit: boolean, onEdit: (id: string) => void) => html`
  <li class="posts-list__post">
    <span class="posts-list__division">${divisionName(post.division_ocdid)}</span>
    <span class="posts-list__status">
      ${post.holder_names.length
        ? html`<span class="posts-list__held"
            >${post.holder_names.length} held</span
          >`
        : html`<span class="posts-list__vacant">vacant</span>`}
      ${post.over_headcount ? html`<span class="posts-list__over">over headcount</span>` : ""}
      ${post._is_verified ? "" : html`<span class="posts-list__unverified">unverified</span>`}
      ${post._is_tracked
        ? ""
        : html`<span class="posts-list__untracked" title="Recorded, but a roster that stops naming its holder will not ask for review">untracked</span>`}
    </span>
    ${canEdit
      ? html`<button class="civ-action-btn" @click=${() => onEdit(post.id)}>Edit</button>`
      : ""}
  </li>
`;

// "7 posts, headcount 11, 3 free" — capacity is only worth saying when a role has more room
// than posts, which is what an at-large body looks like.
const renderCapacity = (group: RoleGroup) => {
  const posts = `${group.posts.length} post${group.posts.length === 1 ? "" : "s"}`;
  if (group.headcount === group.posts.length && group.free === 0) return posts;
  return `${posts}, headcount ${group.headcount}, ${group.free} free`;
};

interface RoleContext {
  canEdit: boolean;
  editing: Editing;
  jurisdictionOcdid: string;
  onEditPost: (id: string) => void;
}

const renderRole = (group: RoleGroup, context: RoleContext) => html`
  <section class="posts-list__role">
    <div class="posts-list__role-head">
      <h3 class="posts-list__role-name">${group.role_label}</h3>
      <span class="posts-list__capacity">${renderCapacity(group)}</span>
    </div>
    <ul class="posts-list__posts">
      ${group.posts.map((post) => renderPost(post, context.canEdit, context.onEditPost))}
    </ul>
  </section>
`;

function PostsList(host: PostsListHost) {
  const [editing, setEditing] = useState<Editing>(null);
  const ocdid = host.jurisdictionOcdid;
  const canEdit = !!host.canEdit;

  const { data, error, reload } = useAsyncData<{
    byRole: RoleGroup[];
    roles: RoleOption[];
  }>(async () => {
    if (!ocdid) return { byRole: [], roles: [] };
    const [postsBody, membershipsBody, rolesBody] = await Promise.all([
      fetchPosts(ocdid),
      fetchMemberships(ocdid),
      fetchRoles(),
    ]);
    // Kept whole as well as reduced: the groups need a label lookup, the add form needs every
    // role as an option — including the ones this jurisdiction has no post for yet.
    const roles: RoleOption[] = rolesBody.data.roles;
    const roleLabels = new Map<string, string>(
      roles.map((role) => [role.id, role.label]),
    );
    const posts = postsBody.data.organizations.flatMap(
      (organization: { posts: unknown[] }) => organization.posts,
    );
    const memberships = membershipsBody.data.memberships;
    return {
      byRole: groupPostsByRole(posts, memberships, roleLabels),
      roles,
    };
  }, [ocdid]);

  const closeAndReload = () => {
    setEditing(null);
    reload();
  };
  const close = () => setEditing(null);

  const handleAddPost = () => setEditing({ entity: "post", id: null });

  const controls = html`
    <div class="posts-list__controls">
      ${canEdit
        ? html`<button class="civ-action-btn" @click=${handleAddPost}>Add post</button>`
        : ""}
    </div>
  `;

  if (error) {
    return html`<p class="posts-list__error">Could not load posts: ${error}</p>`;
  }
  if (data === null) {
    return html`<p class="posts-list__empty">Loading…</p>`;
  }

  const groups = data.byRole;

  const context: RoleContext = {
    canEdit,
    editing,
    jurisdictionOcdid: ocdid ?? "",
    onEditPost: (id) => setEditing({ entity: "post", id }),
  };

  // Found across groups rather than rendered inside one, because a modal floats above the
  // list — slotting it into the row would replace the row it is describing.
  const editingPost =
    editing?.entity === "post" && editing.id
      ? groups.flatMap((group) => group.posts).find((post) => post.id === editing.id)
      : undefined;

  // An empty list is a state the add form has to reach, not an early return: a jurisdiction
  // with no posts yet is exactly when someone needs to make the first one.
  const renderRows = () => {
    if (groups.length === 0) {
      return html`<p class="posts-list__empty">
        No posts yet — they are derived when a scrape is published.
      </p>`;
    }
    return groups.map((group) => renderRole(group, context));
  };

  return html`
    <div class="posts-list" @saved=${closeAndReload} @added=${closeAndReload} @cancel=${close}>
      ${controls}
      ${editingPost ? html`<civ-post-edit .post=${editingPost}></civ-post-edit>` : ""}
      ${editing?.entity === "post" && editing.id === null
        ? html`<civ-post-add
            .jurisdictionOcdid=${ocdid ?? ""}
            .roles=${data.roles}
          ></civ-post-add>`
        : ""}
      ${renderRows()}
    </div>
  `;
}

customElements.define("civ-posts-list", component(PostsList, { useShadowDOM: false }));
