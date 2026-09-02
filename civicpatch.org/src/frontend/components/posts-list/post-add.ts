import "./posts-list.css";
import "../basic/modal.js";
import { html } from "lit-html";
import { inputValue } from "../fields/field-controls.js";
import { component, useState } from "haunted";
import { createPost } from "../../api.js";
import {
  ADDABLE_DIVISIONS,
  AT_LARGE_DIVISION,
  buildDivisionOcdid,
  derivedPostLabel,
  divisionName,
  isDivisionValue,
} from "./posts-model.js";
import type { AddableDivision, RoleOption } from "./posts-model.js";
import { hostDispatch } from "../../utils/host-dispatch.js";

type PostAddHost = HTMLElement & {
  jurisdictionOcdid?: string;
  roles?: RoleOption[];
};

export const ADDED_EVENT = "added";
export const CANCEL_EVENT = "cancel";

// Unpicked. A role has to be chosen rather than defaulted, because every default is a real
// role and filing a post under the wrong one is invisible once saved.
const NO_ROLE = "";

const byLabel = (a: RoleOption, b: RoleOption) => a.label.localeCompare(b.label);

function PostAdd(host: PostAddHost) {
  const [roleId, setRoleId] = useState(NO_ROLE);
  const [designation, setDesignation] = useState<AddableDivision>(AT_LARGE_DIVISION);
  const [value, setValue] = useState("");
  const [label, setLabel] = useState("");
  // Until someone types, the field tracks role and division rather than sitting empty —
  // so the name the post will get is visible before saving, not after.
  const [labelTouched, setLabelTouched] = useState(false);
  const [headcount, setHeadcount] = useState("1");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCancel = () => hostDispatch(host, CANCEL_EVENT);
  const handleRole = (e: Event) => setRoleId(inputValue(e));
  const handleDesignation = (e: Event) =>
    setDesignation(inputValue(e) as AddableDivision);
  // Whitespace stripped as typed: a division value is a single token, and pasting
  // "Ward 3" should land as "3" rather than failing validation for a reason the field
  // never showed.
  const handleValue = (e: Event) =>
    setValue(inputValue(e).replace(/\s+/g, ""));
  const handleLabel = (e: Event) => {
    setLabelTouched(true);
    setLabel(inputValue(e));
  };
  const handleHeadcount = (e: Event) => setHeadcount(inputValue(e));

  const needsValue = designation !== AT_LARGE_DIVISION;
  const jurisdiction = host.jurisdictionOcdid ?? "";
  const divisionOcdid = jurisdiction
    ? buildDivisionOcdid(jurisdiction, designation, value)
    : "";
  const roleLabel = [...(host.roles ?? [])].find((role) => role.id === roleId)?.label ?? "";
  // Shown, not stored: the field tracks the pickers until someone overrides it, and an
  // untouched field saves exactly what the server would have derived anyway.
  const labelValue = labelTouched ? label : derivedPostLabel(roleLabel, divisionOcdid);
  // The same closed set the parser accepts. A value outside it builds an ocdid no scrape
  // can ever produce, so the post would sit unmatched forever beside the real one.
  const validValue = !needsValue || isDivisionValue(value);
  const roles = [...(host.roles ?? [])].sort(byLabel);

  const handleSave = async () => {
    if (!host.jurisdictionOcdid || roleId === NO_ROLE || !validValue) return;
    setSaving(true);
    setError(null);
    try {
      const division_ocdid = buildDivisionOcdid(host.jurisdictionOcdid, designation, value);
      const created = await createPost(host.jurisdictionOcdid, {
        role_id: roleId,
        division_ocdid,
        label: labelValue.trim() || null,
        _headcount: Number(headcount),
      });
      hostDispatch(host, ADDED_EVENT, {
        post_id: created?.data?.id,
        role_id: roleId,
        division_ocdid,
        label: labelValue.trim() || null,
      });
    } catch (cause) {
      // 409 included: the triple is already taken, and the answer is to raise that post's
      // headcount rather than make a second one.
      setError(String(cause).replace(/^Error:\s*/, ""));
      setSaving(false);
    }
  };

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
        <span class="post-edit__label">Label (optional)</span>
        <input
          type="text"
          .value=${labelValue}
          placeholder="Position 8"
          @input=${handleLabel}
        />
      </label>
      <label class="post-edit__field">
        <span class="post-edit__label">Headcount</span>
        <input type="number" min="1" .value=${headcount} @input=${handleHeadcount} />
      </label>
      ${error ? html`<p class="posts-list__error">${error}</p>` : ""}
    </div>
  `;

  const footer = html`
    <button class="btn btn-sm secondary" @click=${handleCancel}>Cancel</button>
    <button
      class="btn btn-sm"
      ?disabled=${saving || roleId === NO_ROLE || (needsValue && !validValue)}
      @click=${handleSave}
    >
      ${saving ? "Adding…" : "Add"}
    </button>
  `;

  return html`
    <civ-modal
      .title=${"Add a post"}
      .content=${fields}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleCancel }}
    ></civ-modal>
  `;
}

customElements.define("civ-post-add", component(PostAdd, { useShadowDOM: false }));
