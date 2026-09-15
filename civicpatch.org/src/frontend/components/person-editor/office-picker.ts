// The office field's picker: role (required) + division (optional), scoped to whatever
// roles/divisions existing posts already use — not the full role taxonomy or every division
// kind `civ-post-add` can build. Picking a combo with no matching post offers "Add a new
// office" instead, which opens that same `civ-post-add` modal (pre-filled, still fully
// editable) rather than a second creation flow.
import "../posts-list/post-add.js";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { attachFocus, inputValue, type FocusRef } from "../fields/field-utils.js";
import { hostDispatch } from "../../utils/host-dispatch.js";
import {
  AT_LARGE_DIVISION,
  buildDivisionOcdid,
  divisionName,
  type Post,
  type RoleOption,
} from "../posts-list/posts-model.js";

export const PICKED_EVENT = "picked";

type OfficePickerHost = HTMLElement & {
  posts?: Post[];
  roles?: RoleOption[];
  jurisdictionOcdid?: string | null;
  canCreatePost?: boolean;
  postId?: string | null;
  focusRef?: FocusRef | null;
};

const NO_ROLE = "";
const NO_DIVISION = "";

const byLabel = (a: RoleOption, b: RoleOption) => a.label.localeCompare(b.label);

function OfficePicker(host: OfficePickerHost) {
  const posts = host.posts ?? [];
  const roles = host.roles ?? [];
  const jurisdictionOcdid = host.jurisdictionOcdid ?? "";
  const atLarge = buildDivisionOcdid(jurisdictionOcdid, AT_LARGE_DIVISION, "");
  const currentPost = posts.find((post) => post.id === host.postId) ?? null;

  const [roleId, setRoleId] = useState(currentPost?.role_id ?? NO_ROLE);
  const [divisionOcdid, setDivisionOcdid] = useState(
    currentPost && currentPost.division_ocdid !== atLarge
      ? currentPost.division_ocdid
      : NO_DIVISION,
  );
  const [addOpen, setAddOpen] = useState(false);

  const roleOptions = [...new Set(posts.map((post) => post.role_id))]
    .map((id) => ({ id, label: roles.find((role) => role.id === id)?.label ?? id }))
    .sort(byLabel);
  const divisionOptions = [
    ...new Set(posts.filter((post) => post.role_id === roleId).map((post) => post.division_ocdid)),
  ]
    .filter((ocdid) => ocdid !== atLarge)
    .sort((a, b) => divisionName(a).localeCompare(divisionName(b)));

  const matchFor = (role: string, division: string) =>
    role ? posts.find((post) => post.role_id === role && post.division_ocdid === division) ?? null : null;
  const matchedPost = matchFor(roleId, divisionOcdid || atLarge);

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
    setRoleId(role_id);
    setDivisionOcdid(division_ocdid === atLarge ? NO_DIVISION : division_ocdid);
    notifyPicked(post_id, label ?? undefined);
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
      ${roleId && !matchedPost && host.canCreatePost
        ? html`<button type="button" class="btn-quiet" @click=${() => setAddOpen(true)}>
            Add a new office
          </button>`
        : ""}
    </span>
    ${addOpen
      ? html`<civ-post-add
          .jurisdictionOcdid=${jurisdictionOcdid}
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
