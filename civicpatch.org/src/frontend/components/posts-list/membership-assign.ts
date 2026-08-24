import "./posts-list.css";
import "../basic/modal.js";
import { html } from "lit-html";
import { inputValue } from "../fields/field-controls.js";
import { component, useState } from "haunted";
import { assignMembership, createPost } from "../../api.js";
import {
  ADDABLE_DIVISIONS,
  AT_LARGE_DIVISION,
  buildDivisionOcdid,
  divisionName,
  isDivisionValue,
  divisionSelection,
  UNNAMED_HOLDER,
} from "./posts-model.js";
import type { AddableDivision, PostOption, RoleOption } from "./posts-model.js";

type MembershipAssignHost = HTMLElement & {
  personId?: string;
  personName?: string | null;
  jurisdictionOcdid?: string;
  roles?: RoleOption[];
  // Every post the jurisdiction already has, so the form can tell "put them in the existing
  // one" from "mint one" without asking the server first.
  options?: PostOption[];
  currentRoleId?: string | null;
  currentDivisionOcdid?: string | null;
  currentLabel?: string | null;
};

export const SAVED_EVENT = "saved";
export const CANCEL_EVENT = "cancel";

// Unpicked. A role has to be chosen rather than defaulted — every default is a real role, and
// filing someone under the wrong one is invisible once saved.
const NO_ROLE = "";

const byLabel = (a: RoleOption, b: RoleOption) => a.label.localeCompare(b.label);

function MembershipAssign(host: MembershipAssignHost) {
  const seeded = divisionSelection(host.currentDivisionOcdid);
  const [roleId, setRoleId] = useState(host.currentRoleId ?? NO_ROLE);
  const [designation, setDesignation] = useState<AddableDivision>(seeded.designation);
  const [value, setValue] = useState(seeded.value);
  const [office, setOffice] = useState(host.currentLabel ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const roles = [...(host.roles ?? [])].sort(byLabel);
  const emit = (name: string) =>
    host.dispatchEvent(new CustomEvent(name, { bubbles: true, composed: true }));

  const handleCancel = () => emit(CANCEL_EVENT);
  const handleRole = (e: Event) => setRoleId(inputValue(e));
  const handleDesignation = (e: Event) =>
    setDesignation(inputValue(e) as AddableDivision);
  // Whitespace stripped as typed: a division value is a single token, and pasting
  // "Ward 3" should land as "3" rather than failing validation for a reason the field
  // never showed.
  const handleValue = (e: Event) =>
    setValue(inputValue(e).replace(/\s+/g, ""));
  const handleOffice = (e: Event) => setOffice(inputValue(e));

  const needsValue = designation !== AT_LARGE_DIVISION;
  // The same closed set the parser accepts. A value outside it builds an ocdid no scrape
  // can ever produce, so the post would sit unmatched forever beside the real one.
  const validValue = !needsValue || isDivisionValue(value);
  const jurisdiction = host.jurisdictionOcdid ?? "";
  const divisionOcdid = jurisdiction
    ? buildDivisionOcdid(jurisdiction, designation, value)
    : "";
  // Role and division *are* the post's identity, so this is a lookup rather than a search.
  const existing = (host.options ?? []).find(
    (option) => option.role_id === roleId && option.division_ocdid === divisionOcdid,
  );

  const handleSave = async () => {
    if (!host.personId || roleId === NO_ROLE || (needsValue && !validValue)) return;
    setSaving(true);
    setError(null);
    try {
      // Mint the post only when the pair names one that does not exist. `POST /posts` 409s on
      // a taken triple rather than returning the existing id, which is why this asks `options`
      // first instead of catching the conflict.
      const postId =
        existing?.post_id ??
        (await createPost(jurisdiction, {
          role_id: roleId,
          division_ocdid: divisionOcdid,
          label: null,
          _headcount: 1,
        })).data.id;
      await assignMembership(host.personId, postId, office.trim() || null);
      emit(SAVED_EVENT);
    } catch (cause) {
      setError(String(cause).replace(/^Error:\s*/, ""));
      setSaving(false);
    }
  };

  const unchanged =
    roleId === host.currentRoleId &&
    divisionOcdid === host.currentDivisionOcdid &&
    office.trim() === (host.currentLabel ?? "");
  // Said before saving, because a move closes the old membership and mints nothing visible.
  const consequence =
    roleId === NO_ROLE
      ? null
      : unchanged
        ? html`<p class="post-edit__hint">Nothing has changed yet.</p>`
        : existing
          ? html`<p class="post-edit__hint">
              Seats them in ${existing.label}${existing.full
                ? ` — already at headcount (${existing.held}/${existing.headcount})`
                : ""}.
            </p>`
          : html`<p class="post-edit__hint">
              No such post yet — saving creates ${roles.find((role) => role.id === roleId)
                ?.label ?? roleId}, ${divisionName(divisionOcdid)} and seats them in it.
            </p>`;

  const fields = html`
    <div class="post-edit">
      <label class="post-edit__field">
        <span class="post-edit__label">Role</span>
        <select @change=${handleRole}>
          <option value=${NO_ROLE} .selected=${roleId === NO_ROLE}>Choose a role…</option>
          ${roles.map(
            (role) => html`<option value=${role.id} .selected=${role.id === roleId}>
              ${role.label}
            </option>`,
          )}
        </select>
      </label>
      <label class="post-edit__field">
        <span class="post-edit__label">Division</span>
        <span class="post-edit__division">
          <select @change=${handleDesignation}>
          ${ADDABLE_DIVISIONS.map(
            (option) => html`<option value=${option} .selected=${option === designation}>
              ${option === AT_LARGE_DIVISION ? divisionName("") : option.replace(/_/g, " ")}
            </option>`,
          )}
          </select>
          ${needsValue
            ? html`<input
                type="text"
                class="post-edit__division-value"
                placeholder="3, North, A"
                aria-label="Division number or name"
                .value=${value}
                @input=${handleValue}
              />`
            : ""}
        </span>
      </label>
      ${needsValue && value && !validValue
        ? html`<p class="post-edit__hint post-edit__hint--error">
            A ward or district is numbered, named for a direction (North, Southeast), or a
            single letter — anything else builds an id no scrape will match.
          </p>`
        : ""}
      <label class="post-edit__field">
        <span class="post-edit__label">Office (optional)</span>
        <input
          type="text"
          .value=${office}
          placeholder="Deputy Mayor Pro Tempore"
          @input=${handleOffice}
        />
      </label>
      ${consequence}
      ${error ? html`<p class="posts-list__error">${error}</p>` : ""}
    </div>
  `;

  const footer = html`
    <button class="btn btn-sm secondary" @click=${handleCancel}>Cancel</button>
    <button
      class="btn btn-sm"
      ?disabled=${saving || roleId === NO_ROLE || (needsValue && !validValue) || unchanged}
      @click=${handleSave}
    >
      ${saving ? "Saving…" : "Save"}
    </button>
  `;

  return html`
    <civ-modal
      .title=${`Post for ${host.personName || UNNAMED_HOLDER}`}
      .content=${fields}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleCancel }}
    ></civ-modal>
  `;
}

customElements.define(
  "civ-membership-assign",
  component(MembershipAssign, { useShadowDOM: false }),
);
