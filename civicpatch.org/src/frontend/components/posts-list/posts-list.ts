import "./posts-list.css";
import "./post-edit.js";
import "./post-add.js";
import "./membership-assign.js";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { fetchPosts, fetchMemberships, fetchRoles } from "../../api.js";
import { useAsyncData } from "../../hooks/use-async-data.js";
import {
  groupPostsByRole,
  groupMembershipsByPerson,
  divisionName,
  divisionKey,
  postTitle,
  decompose,
  postOptions,
} from "./posts-model.js";
import type {
  RoleGroup,
  PostRow,
  PersonRow,
  Membership,
  RoleOption,
  PostOption,
} from "./posts-model.js";

type PostsListHost = HTMLElement & {
  jurisdictionOcdid?: string;
  // Same gate as people editing on this page: a scrape still awaiting review blocks both, so
  // the roster and the posts describing it cannot drift while a change is in flight.
  canEdit?: boolean;
};

const HOLDER_SEPARATOR = ", ";

// "The same rows" — one dataset, two axes. A toggle rather than separate screens, because the
// question ("who holds what") is identical and only the grouping differs.
const BY_POST = "post";
const BY_PERSON = "person";
type Axis = typeof BY_POST | typeof BY_PERSON;

// Which entity the screen has open, and only ever one — two booleans would allow editing and
// adding at once, which the layout has no room for and the user never means.
//
// Named for the entity, not the action: adding and editing a post are the same entity with and
// without an id, so `id: null` is "this post does not exist yet" rather than a third case.
//
// There is deliberately no equivalent for membership. Posts are CRUD — POST mints an identity
// (organization, role, division) that did not exist. A membership is asserted, not created:
// the route is a single idempotent PUT that says where a person is, and opens or closes rows
// to make that true. So "a new membership" is not a thing a caller can ask for.
type Editing =
  | { entity: "post"; id: string | null }
  | { entity: "membership"; membership: Membership }
  | null;

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
    ${post._is_verified ? "" : html`<span class="posts-list__unverified">unverified</span>`}
    ${post._is_tracked
      ? ""
      : html`<span class="posts-list__untracked" title="Recorded, but a roster that stops naming its holder will not ask for review">untracked</span>`}
    ${canEdit
      ? html`<button class="posts-list__edit" @click=${() => onEdit(post.id)}>Edit</button>`
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

// What the source said, and what the parser made of every piece of it. Shown together
// because the derived name alone cannot be judged — it says where the person landed, not why.
const renderMembership = (
  membership: Membership,
  canEdit: boolean,
  onAssign: (membership: Membership) => void,
) => html`
  <li class="posts-list__post posts-list__post--stacked">
    <span class="posts-list__holders">${postTitle(membership)}</span>
    ${canEdit
      ? html`<button class="posts-list__edit" @click=${() => onAssign(membership)}>
          Change post
        </button>`
      : ""}
    ${membership.source_labels.map(
      (label) => html`<p class="posts-list__source">“${label}”</p>`,
    )}
    <p class="posts-list__parts">
      ${decompose(membership).map(
        (part) => html`<span class="posts-list__part posts-list__part--${part.kind}">
          <span class="posts-list__part-kind">${part.kind}</span>${part.value}
        </span>`,
      )}
    </p>
  </li>
`;

const renderPerson = (
  row: PersonRow,
  canEdit: boolean,
  onAssign: (membership: Membership) => void,
) => html`
  <section class="posts-list__role">
    <h3 class="posts-list__role-name">${row.person_name}</h3>
    <ul class="posts-list__posts">
      ${row.posts.map((membership) => renderMembership(membership, canEdit, onAssign))}
    </ul>
  </section>
`;

function PostsList(host: PostsListHost) {
  const [editing, setEditing] = useState<Editing>(null);
  const [axis, setAxis] = useState<Axis>(BY_POST);
  // Empty means now. Held as the raw input value so the field and the query cannot disagree.
  const [asOf, setAsOf] = useState("");
  const ocdid = host.jurisdictionOcdid;
  const canEdit = !!host.canEdit;

  // Two reads because the screen is post-shaped but lists people: posts carry capacity,
  // memberships carry who is in them.
  const { data, error, reload } = useAsyncData<{
    byRole: RoleGroup[];
    byPerson: PersonRow[];
    roles: RoleOption[];
    postOptions: PostOption[];
  }>(async () => {
    if (!ocdid) return { byRole: [], byPerson: [], roles: [], postOptions: [] };
    const on = asOf || null;
    const [postsBody, membershipsBody, rolesBody] = await Promise.all([
      fetchPosts(ocdid),
      fetchMemberships(ocdid, on),
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
      byPerson: groupMembershipsByPerson(memberships),
      roles,
      postOptions: postOptions(posts, memberships, roleLabels),
    };
  }, [ocdid, asOf]);

  const closeAndReload = () => {
    setEditing(null);
    reload();
  };
  const close = () => setEditing(null);

  const handleAxis = (next: Axis) => () => {
    setEditing(null);
    setAxis(next);
  };
  const handleAsOf = (e: Event) => setAsOf((e.target as HTMLInputElement).value);
  const handleNow = () => setAsOf("");
  const handleAddPost = () => setEditing({ entity: "post", id: null });

  // Editing is off while looking at the past: the forms write to the present, so a Save from
  // a dated view would silently apply to now.
  const dated = asOf !== "";
  const tab = (which: Axis) =>
    axis === which ? "posts-list__tab posts-list__tab--on" : "posts-list__tab";

  const controls = html`
    <div class="posts-list__controls">
      <div class="posts-list__axis">
        <button class=${tab(BY_POST)} @click=${handleAxis(BY_POST)}>By post</button>
        <button class=${tab(BY_PERSON)} @click=${handleAxis(BY_PERSON)}>By person</button>
      </div>
      <label class="posts-list__as-of">
        <span>Showing</span>
        <input type="date" .value=${asOf} @input=${handleAsOf} />
        ${dated
          ? html`<button class="posts-list__edit" @click=${handleNow}>back to today</button>`
          : html`<span class="posts-list__today">today</span>`}
      </label>
      ${canEdit && !dated
        ? html`<button class="posts-list__add" @click=${handleAddPost}>Add post</button>`
        : ""}
    </div>
    ${dated
      ? html`<p class="posts-list__dated-note">
          Editing is off while viewing a past date — the forms write to today.
        </p>`
      : ""}
  `;

  if (error) {
    return html`<p class="posts-list__error">Could not load posts: ${error}</p>`;
  }
  if (data === null) {
    return html`<p class="posts-list__empty">Loading…</p>`;
  }

  const groups = data.byRole;

  const context: RoleContext = {
    canEdit: canEdit && !dated,
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
        ${dated
          ? "No posts on that date."
          : "No posts yet — they are derived when a scrape is published."}
      </p>`;
    }
    if (axis === BY_POST) return groups.map((group) => renderRole(group, context));
    return data.byPerson.map((row) =>
      renderPerson(row, context.canEdit, (membership) =>
        setEditing({ entity: "membership", membership }),
      ),
    );
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
      ${editing?.entity === "membership"
        ? html`<civ-membership-assign
            .personId=${editing.membership.person_id}
            .personName=${editing.membership.person_name}
            .jurisdictionOcdid=${ocdid ?? ""}
            .roles=${data.roles}
            .options=${data.postOptions}
            .currentRoleId=${editing.membership.role_id}
            .currentDivisionOcdid=${editing.membership.division_ocdid}
            .currentLabel=${editing.membership.label}
          ></civ-membership-assign>`
        : ""}
      ${renderRows()}
    </div>
  `;
}

customElements.define("civ-posts-list", component(PostsList, { useShadowDOM: false }));
