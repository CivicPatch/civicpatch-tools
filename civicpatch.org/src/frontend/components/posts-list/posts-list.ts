import "./posts-list.css";
import "./post-edit.js";
import "./post-add.js";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { fetchPosts, fetchMemberships } from "../../api.js";
import { useAsyncData } from "../../hooks/use-async-data.js";
import { groupPostsByRole, divisionName, divisionKey } from "./posts-model.js";
import type { RoleGroup, PostRow } from "./posts-model.js";

type PostsListHost = HTMLElement & {
  jurisdictionOcdid?: string;
  // Same gate as people editing on this page: a scrape still awaiting review blocks both, so
  // the roster and the posts describing it cannot drift while a change is in flight.
  canEdit?: boolean;
};

const HOLDER_SEPARATOR = " · ";

// What the screen is doing to one post. Two booleans would allow editing and adding at once,
// which the layout has no room for and the user never means.
type Editing = { kind: "post"; id: string } | { kind: "role"; id: string } | null;

const renderPost = (post: PostRow, canEdit: boolean, onEdit: (id: string) => void) => html`
  <li class="posts-list__post">
    <span class="posts-list__division">${divisionName(post.division_ocdid)}</span>
    <span class="posts-list__key">${divisionKey(post.division_ocdid)}</span>
    ${post.holder_names.length
      ? html`<span class="posts-list__holders">
          ${post.holder_names.join(HOLDER_SEPARATOR)}
        </span>`
      : html`<span class="posts-list__vacant">nobody</span>`}
    ${post.over_headcount ? html`<span class="posts-list__over">over headcount</span>` : ""}
    ${post._verified ? "" : html`<span class="posts-list__unverified">unverified</span>`}
    ${canEdit
      ? html`<button class="posts-list__edit" @click=${() => onEdit(post.id)}>Edit</button>`
      : ""}
  </li>
`;

// "7 posts · headcount 11 · 3 free" — capacity is only worth saying when a role has more room
// than posts, which is what an at-large body looks like.
const renderCapacity = (group: RoleGroup) => {
  const posts = `${group.posts.length} post${group.posts.length === 1 ? "" : "s"}`;
  if (group.headcount === group.posts.length && group.free === 0) return posts;
  return `${posts} · headcount ${group.headcount} · ${group.free} free`;
};

interface RoleContext {
  canEdit: boolean;
  editing: Editing;
  jurisdictionOcdid: string;
  onEditPost: (id: string) => void;
  onAddToRole: (roleId: string) => void;
}

const renderRole = (group: RoleGroup, context: RoleContext) => html`
  <section class="posts-list__role">
    <div class="posts-list__role-head">
      <h3 class="posts-list__role-name">${group.role_label}</h3>
      <span class="posts-list__capacity">
        ${renderCapacity(group)}
        ${context.canEdit
          ? html`<button
              class="posts-list__edit"
              @click=${() => context.onAddToRole(group.role_id)}
            >
              Add
            </button>`
          : ""}
      </span>
    </div>
    ${context.editing?.kind === "role" && context.editing.id === group.role_id
      ? html`<civ-post-add
          .jurisdictionOcdid=${context.jurisdictionOcdid}
          .roleId=${group.role_id}
          .roleLabel=${group.role_label}
        ></civ-post-add>`
      : ""}
    <ul class="posts-list__posts">
      ${group.posts.map((post) =>
        context.editing?.kind === "post" && context.editing.id === post.id
          ? html`<li class="posts-list__post posts-list__post--editing">
              <civ-post-edit .post=${post}></civ-post-edit>
            </li>`
          : renderPost(post, context.canEdit, context.onEditPost),
      )}
    </ul>
  </section>
`;

function PostsList(host: PostsListHost) {
  const [editing, setEditing] = useState<Editing>(null);
  const ocdid = host.jurisdictionOcdid;
  const canEdit = !!host.canEdit;

  // Two reads because the screen is post-shaped but lists people: posts carry capacity,
  // memberships carry who is in them.
  const {
    data: groups,
    error,
    reload,
  } = useAsyncData<RoleGroup[]>(async () => {
    if (!ocdid) return [];
    const [postsBody, membershipsBody] = await Promise.all([
      fetchPosts(ocdid),
      fetchMemberships(ocdid),
    ]);
    const posts = postsBody.data.organizations.flatMap(
      (organization: { posts: unknown[] }) => organization.posts,
    );
    return groupPostsByRole(posts, membershipsBody.data.memberships);
  }, [ocdid]);

  const closeAndReload = () => {
    setEditing(null);
    reload();
  };
  const close = () => setEditing(null);

  if (error) {
    return html`<p class="posts-list__error">Could not load posts: ${error}</p>`;
  }
  if (groups === null) {
    return html`<p class="posts-list__empty">Loading…</p>`;
  }
  if (groups.length === 0) {
    return html`<p class="posts-list__empty">
      No posts yet — they are derived when a scrape is published.
    </p>`;
  }

  const context: RoleContext = {
    canEdit,
    editing,
    jurisdictionOcdid: ocdid ?? "",
    onEditPost: (id) => setEditing({ kind: "post", id }),
    onAddToRole: (id) => setEditing({ kind: "role", id }),
  };

  return html`
    <div class="posts-list" @saved=${closeAndReload} @added=${closeAndReload} @cancel=${close}>
      ${groups.map((group) => renderRole(group, context))}
    </div>
  `;
}

customElements.define("civ-posts-list", component(PostsList, { useShadowDOM: false }));
