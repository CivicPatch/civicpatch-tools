import "./posts-list.css";
import "../basic/modal.js";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { createPost } from "../../api.js";
import {
  ADDABLE_DIVISIONS,
  AT_LARGE_DIVISION,
  buildDivisionOcdid,
  divisionName,
} from "./posts-model.js";
import type { AddableDivision } from "./posts-model.js";

type PostAddHost = HTMLElement & {
  jurisdictionOcdid?: string;
  // Pre-filled from the role group the Add sits under, so the one field a person cannot
  // change after saving is the one they never have to pick.
  roleId?: string;
  roleLabel?: string;
};

export const ADDED_EVENT = "added";
export const CANCEL_EVENT = "cancel";

function PostAdd(host: PostAddHost) {
  const [designation, setDesignation] = useState<AddableDivision>(AT_LARGE_DIVISION);
  const [value, setValue] = useState("");
  const [label, setLabel] = useState("");
  const [headcount, setHeadcount] = useState("1");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emit = (name: string) =>
    host.dispatchEvent(new CustomEvent(name, { bubbles: true, composed: true }));

  const handleCancel = () => emit(CANCEL_EVENT);
  const handleDesignation = (e: Event) =>
    setDesignation((e.target as HTMLSelectElement).value as AddableDivision);
  const handleValue = (e: Event) => setValue((e.target as HTMLInputElement).value);
  const handleLabel = (e: Event) => setLabel((e.target as HTMLInputElement).value);
  const handleHeadcount = (e: Event) => setHeadcount((e.target as HTMLInputElement).value);

  const needsValue = designation !== AT_LARGE_DIVISION;

  const handleSave = async () => {
    if (!host.jurisdictionOcdid || !host.roleId) return;
    setSaving(true);
    setError(null);
    try {
      await createPost(host.jurisdictionOcdid, {
        role_id: host.roleId,
        division_ocdid: buildDivisionOcdid(host.jurisdictionOcdid, designation, value),
        label: label.trim() || null,
        headcount: Number(headcount),
      });
      emit(ADDED_EVENT);
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
        <span class="post-edit__label">Division</span>
        <select .value=${designation} @change=${handleDesignation}>
          ${ADDABLE_DIVISIONS.map(
            (option) => html`<option value=${option}>
              ${option === AT_LARGE_DIVISION ? divisionName("") : option.replace(/_/g, " ")}
            </option>`,
          )}
        </select>
      </label>
      ${needsValue
        ? html`<label class="post-edit__field">
            <span class="post-edit__label">Number</span>
            <input type="text" .value=${value} @input=${handleValue} />
          </label>`
        : ""}
      <label class="post-edit__field">
        <span class="post-edit__label">Label</span>
        <input
          type="text"
          .value=${label}
          placeholder="derived from role and division"
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
      ?disabled=${saving || (needsValue && !value.trim())}
      @click=${handleSave}
    >
      ${saving ? "Adding…" : "Add"}
    </button>
  `;

  return html`
    <civ-modal
      .title=${`Add a ${host.roleLabel ?? "post"}`}
      .content=${fields}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleCancel }}
    ></civ-modal>
  `;
}

customElements.define("civ-post-add", component(PostAdd, { useShadowDOM: false }));
