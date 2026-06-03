import "./role-reorder.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { reorderRoles } from "../../api.js";
import { moveUp, moveDown, moveToTop, applyDrop } from "./reorder-utils.js";

interface RoleTerm {
  role: string;
  is_unique?: boolean;
  aliases?: string[];
}

type RoleReorderHost = HTMLElement & {
  roles?: RoleTerm[];
  scope?: "global" | "state" | "locality";
  ocdid?: string | null;
};

export const REORDERED_EVENT = "reordered";
export const CANCEL_EVENT = "cancel";

function RoleReorder(host: RoleReorderHost) {
  const scope = host.scope ?? "global";
  const ocdid = host.ocdid ?? null;
  const [order, setOrder] = useState<RoleTerm[]>([...(host.roles ?? [])]);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [announce, setAnnounce] = useState("");
  // Roles the user has actively moved — tinted so the pending diff is visible.
  // Tracks moved roles, not shifted indexes (one move shifts everything below it).
  const [movedRoleValues, setMovedRoleValues] = useState<Set<string>>(new Set());

  const handleCancel = () =>
    host.dispatchEvent(new CustomEvent(CANCEL_EVENT, { bubbles: true, composed: true }));

  const reorderTo = (next: RoleTerm[], roleValue: string) => {
    setOrder(next);
    setMovedRoleValues(new Set(movedRoleValues).add(roleValue));
    const position = next.findIndex((r) => r.role === roleValue) + 1;
    setAnnounce(`${roleValue} moved to position ${position} of ${next.length}`);
  };

  const clearDrag = () => {
    setDragIndex(null);
    setDragOverIndex(null);
  };

  const handleDrop = (toIndex: number) => {
    if (dragIndex === null) return;
    const moved = order[dragIndex];
    reorderTo(applyDrop(order, dragIndex, toIndex), moved.role);
    clearDrag();
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await reorderRoles({ scope, ocdid, roleOrder: order.map((r) => r.role), movedRoles: [...movedRoleValues] });
      host.dispatchEvent(new CustomEvent(REORDERED_EVENT, { bubbles: true, composed: true }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const rows = order.map((term, i) => {
    const showDrop = dragIndex !== null && dragOverIndex === i && dragIndex !== i;
    const dropClass = showDrop ? (dragIndex < i ? " role-reorder__row--drop-after" : " role-reorder__row--drop-before") : "";
    const movedClass = movedRoleValues.has(term.role) ? " role-reorder__row--moved" : "";
    return html`
      <li
        class="role-reorder__row${dragIndex === i ? " role-reorder__row--dragging" : ""}${dropClass}${movedClass}"
        draggable="true"
        @dragstart=${() => setDragIndex(i)}
        @dragover=${(e: DragEvent) => { e.preventDefault(); if (dragOverIndex !== i) setDragOverIndex(i); }}
        @drop=${() => handleDrop(i)}
        @dragend=${clearDrag}
      >
        <span class="role-reorder__handle" aria-hidden="true"><i class="fa-solid fa-grip-vertical"></i></span>
        <span class="role-reorder__name">${term.role}</span>
        <span class="role-reorder__buttons">
          <button class="civ-action-btn" title="Move up" aria-label=${`Move ${term.role} up`}
            ?disabled=${i === 0} @click=${() => reorderTo(moveUp(order, i), term.role)}><i class="fa-solid fa-arrow-up" aria-hidden="true"></i></button>
          <button class="civ-action-btn" title="Move down" aria-label=${`Move ${term.role} down`}
            ?disabled=${i === order.length - 1} @click=${() => reorderTo(moveDown(order, i), term.role)}><i class="fa-solid fa-arrow-down" aria-hidden="true"></i></button>
          <button class="civ-action-btn" title="Move to top" aria-label=${`Move ${term.role} to top`}
            ?disabled=${i === 0} @click=${() => reorderTo(moveToTop(order, i), term.role)}><i class="fa-solid fa-angles-up" aria-hidden="true"></i></button>
        </span>
      </li>
    `;
  });

  return html`
    <div class="role-reorder">
      <div class="role-reorder__bar">
        <span class="role-reorder__hint">Drag, or use ↑ ↓, to reorder — top = highest priority.</span>
        <span class="role-reorder__actions">
          <button class="btn btn-sm" ?disabled=${saving} @click=${handleSave}>
            ${saving ? "Saving…" : "Save order"}
          </button>
          <button class="btn btn-sm secondary" ?disabled=${saving} @click=${handleCancel}>
            Cancel
          </button>
        </span>
      </div>
      ${error ? html`<p class="config-editor__error">${error}</p>` : null}
      <ol class="role-reorder__list">${rows}</ol>
      <div class="role-reorder__announce" aria-live="polite">${announce}</div>
    </div>
  `;
}

customElements.define(
  "civ-role-reorder",
  component(RoleReorder as unknown as () => unknown, { useShadowDOM: false }),
);
