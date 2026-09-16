// The office field's picker: role (required) + division (optional), scoped to whatever
// roles/divisions existing posts already use — not the full role taxonomy or every division
// kind `civ-post-add` can build. Picking a combo with no matching post offers "Add a new
// office" instead, which opens that same `civ-post-add` modal (pre-filled, still fully
// editable) rather than a second creation flow.
import "../posts-list/post-add.js";
import { html } from "lit-html";
import { component, useEffect, useState } from "haunted";
import { attachFocus, inputValue, type FocusRef } from "../fields/field-utils.js";
import { hostDispatch } from "../../utils/host-dispatch.js";
import {
  AT_LARGE_DIVISION,
  buildDivisionOcdid,
  divisionName,
  type Post,
  type ProposedPost,
  type RoleOption,
} from "../posts-list/posts-model.js";

export const PICKED_EVENT = "picked";
// A new post was minted — distinct from PICKED_EVENT, which fires for an existing one too.
// `justAdded` only ever patches this one picker's own options; whoever owns the org's real
// posts list needs this to refetch it, or every other card (and this one, once remounted)
// keeps not knowing the post exists.
export const POST_CREATED_EVENT = "post-created";

type OfficePickerHost = HTMLElement & {
  posts?: Post[];
  roles?: RoleOption[];
  jurisdictionOcdid?: string | null;
  organizationId?: string;
  canCreatePost?: boolean;
  postId?: string | null;
  // Fallback initial pick when `postId` doesn't resolve to a real post — a proposal naming a
  // role/division nobody holds yet, so there's no row to look up. Ignored once `postId` does
  // resolve, or once the reviewer picks something themselves.
  initialRoleId?: string;
  initialDivisionOcdid?: string;
  // This person's own proposed role(s)/division(s) — a scrape's claim, whether or not any
  // established post matches it yet. Folded into the role/division options below so a
  // proposal naming a role nobody holds (or a second role, alongside one already held) is
  // still something a reviewer can pick, not just a "Moved from X to Y" note beside a picker
  // that has no way to select what it's describing.
  proposedPosts?: ProposedPost[];
  focusRef?: FocusRef | null;
};

const NO_ROLE = "";
const NO_DIVISION = "";

const byLabel = (a: RoleOption, b: RoleOption) => a.label.localeCompare(b.label);

function OfficePicker(host: OfficePickerHost) {
  const roles = host.roles ?? [];
  const jurisdictionOcdid = host.jurisdictionOcdid ?? "";
  const atLarge = buildDivisionOcdid(jurisdictionOcdid, AT_LARGE_DIVISION, "");
  // The post `civ-post-add` just minted, until the parent's own `posts` prop catches up with a
  // refetch — without this, a role/division nobody had before `handleAdded`'s own pick doesn't
  // match anything in `posts` yet, so the select it just set shows nothing selected at all.
  const [justAdded, setJustAdded] = useState<Post | null>(null);
  const posts = justAdded ? [...(host.posts ?? []), justAdded] : (host.posts ?? []);
  const currentPost = posts.find((post) => post.id === host.postId) ?? null;

  const initialRoleId = currentPost?.role_id ?? host.initialRoleId ?? NO_ROLE;
  const initialDivisionOcdid = currentPost
    ? currentPost.division_ocdid !== atLarge
      ? currentPost.division_ocdid
      : NO_DIVISION
    : host.initialDivisionOcdid && host.initialDivisionOcdid !== atLarge
      ? host.initialDivisionOcdid
      : NO_DIVISION;
  const [roleId, setRoleId] = useState(initialRoleId);
  const [divisionOcdid, setDivisionOcdid] = useState(initialDivisionOcdid);
  // `useState`'s own initializer only ever runs once — if this element's identity doesn't
  // change when the reviewer moves to a different person (the inline editor slot getting
  // reused rather than a fresh mount, however exactly that happens), the seeded value above
  // can go stale. Resyncing here whenever the actual identity — which post, or which proposed
  // role/division — changes is what makes that not matter either way. Skips a same-person
  // re-render (these stay `===` across it), so a reviewer's own in-progress pick is never
  // clobbered.
  useEffect(() => {
    setRoleId(initialRoleId);
    setDivisionOcdid(initialDivisionOcdid);
  }, [host.postId, host.initialRoleId, host.initialDivisionOcdid]);
  const [addOpen, setAddOpen] = useState(false);

  const proposedPosts = host.proposedPosts ?? [];
  const roleOptions = [
    ...new Set([...posts.map((post) => post.role_id), ...proposedPosts.map((p) => p.role_id)]),
  ]
    .map((id) => ({
      id,
      label:
        roles.find((role) => role.id === id)?.label ??
        proposedPosts.find((p) => p.role_id === id)?.role_label ??
        id,
    }))
    .sort(byLabel);
  const divisionOptions = [
    ...new Set([
      ...posts.filter((post) => post.role_id === roleId).map((post) => post.division_ocdid),
      ...proposedPosts.filter((p) => p.role_id === roleId).map((p) => p.division_ocdid),
    ]),
  ]
    .filter((ocdid) => ocdid !== atLarge)
    .sort((a, b) => divisionName(a).localeCompare(divisionName(b)));

  const matchFor = (role: string, division: string) =>
    role ? posts.find((post) => post.role_id === role && post.division_ocdid === division) ?? null : null;

  const notifyPicked = (post_id: string, membership_label?: string) =>
    hostDispatch(
      host,
      PICKED_EVENT,
      membership_label === undefined ? { post_id } : { post_id, membership_label },
    );

  const handleRole = (e: Event) => {
    const id = inputValue(e);
    setRoleId(id);
    setDivisionOcdid(NO_DIVISION);
    const match = matchFor(id, atLarge);
    if (match) notifyPicked(match.id);
  };
  const handleDivision = (e: Event) => {
    const division = inputValue(e);
    setDivisionOcdid(division);
    const match = matchFor(roleId, division || atLarge);
    if (match) notifyPicked(match.id);
  };
  const handleAdded = (e: CustomEvent) => {
    const { post_id, role_id, division_ocdid, label } = e.detail;
    setAddOpen(false);
    setJustAdded({
      id: post_id,
      organization_id: host.organizationId ?? "",
      role_id,
      division_ocdid,
      label: label ?? roles.find((role) => role.id === role_id)?.label ?? role_id,
      meta_headcount: 1,
      meta_is_tracked: true,
      meta_is_verified: true,
    });
    setRoleId(role_id);
    setDivisionOcdid(division_ocdid === atLarge ? NO_DIVISION : division_ocdid);
    // Not `label` — that's the new post's own name (civ-post-add's own field, ignored by the
    // API since 148 anyway), never the occupant's membership label. Picking a post never sets
    // one (see office-changes.ts/field-controls.ts's own comments on this).
    notifyPicked(post_id);
    hostDispatch(host, POST_CREATED_EVENT);
  };

  return html`
    <span class="office-picker">
      <select
        ${attachFocus(host.focusRef ?? null)}
        class="field-control__office"
        aria-label="Role"
        @change=${handleRole}
      >
        <option value=${NO_ROLE} .selected=${roleId === NO_ROLE} disabled>Choose a role…</option>
        ${roleOptions.map(
          (role) => html`<option value=${role.id} .selected=${role.id === roleId}>
            ${role.label}
          </option>`,
        )}
      </select>
      ${roleId
        ? html`<select
            class="field-control__office"
            aria-label="Division"
            @change=${handleDivision}
          >
            <option value=${NO_DIVISION} .selected=${divisionOcdid === NO_DIVISION}>
              ${divisionName("")}
            </option>
            ${divisionOptions.map(
              (ocdid) => html`<option value=${ocdid} .selected=${ocdid === divisionOcdid}>
                ${divisionName(ocdid)}
              </option>`,
            )}
          </select>`
        : ""}
      ${host.canCreatePost
        ? html`<button type="button" class="btn btn-sm" @click=${() => setAddOpen(true)}>
            Add a new office
          </button>`
        : ""}
    </span>
    ${addOpen
      ? html`<civ-post-add
          .jurisdictionOcdid=${jurisdictionOcdid}
          .organizationId=${host.organizationId ?? ""}
          .roles=${roles}
          .initialRoleId=${roleId}
          .initialDivisionOcdid=${divisionOcdid || atLarge}
          @added=${handleAdded}
          @cancel=${() => setAddOpen(false)}
        ></civ-post-add>`
      : ""}
  `;
}

customElements.define("civ-office-picker", component(OfficePicker, { useShadowDOM: false }));
