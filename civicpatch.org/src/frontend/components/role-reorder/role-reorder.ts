import "../action-btn/action-btn.css";
import "./role-reorder.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { reorderRoles } from "../../api.js";
import { moveUp, moveDown, moveToTop, applyDrop } from "./reorder-utils.js";

// What this component needs from each role, not the whole API shape: `id` is
// what the reorder call sends and what tracks a moved row, `label` is what the
// row renders. Callers pass richer objects; the extra fields are ignored.
interface ReorderableRole {
  id: string;
  label: string;
}

type RoleReorderHost = HTMLElement & {
  roles?: ReorderableRole[];
};

export const REORDERED_EVENT = "reordered";
export const CANCEL_EVENT = "cancel";

function RoleReorder(host: RoleReorderHost) {
  const [order, setOrder] = useState<ReorderableRole[]>([...(host.roles ?? [])]);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [announce, setAnnounce] = useState("");
  // Ids of roles the user has actively moved — tinted so the pending diff is
  // visible. Tracks moved roles, not shifted indexes (one move shifts
  // everything below it). Ids, not labels: the reorder API keys on id.
  const [movedRoleIds, setMovedRoleIds] = useState<Set<string>>(new Set());

  const handleCancel = () =>
    host.dispatchEvent(new CustomEvent(CANCEL_EVENT, { bubbles: true, composed: true }));

  // Takes the role, not one field of it: tracking keys on id, the announcement
  // reads out the label.
  const reorderTo = (next: ReorderableRole[], moved: ReorderableRole) => {
    setOrder(next);
    setMovedRoleIds(new Set(movedRoleIds).add(moved.id));
    const position = next.findIndex((r) => r.id === moved.id) + 1;
    setAnnounce(`${moved.label} moved to position ${position} of ${next.length}`);
  };

  const clearDrag = () => {
    setDragIndex(null);
    setDragOverIndex(null);
  };

  const handleDrop = (toIndex: number) => {
    if (dragIndex === null) return;
    reorderTo(applyDrop(order, dragIndex, toIndex), order[dragIndex]);
    clearDrag();
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await reorderRoles({ roleOrder: order.map((r) => r.id), movedRoles: [...movedRoleIds] });
      host.dispatchEvent(new CustomEvent(REORDERED_EVENT, { bubbles: true, composed: true }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const rows = order.map((role, i) => {
    const showDrop = dragIndex !== null && dragOverIndex === i && dragIndex !== i;
    const dropClass = showDrop ? (dragIndex < i ? " role-reorder__row--drop-after" : " role-reorder__row--drop-before") : "";
    const movedClass = movedRoleIds.has(role.id) ? " role-reorder__row--moved" : "";
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
        <span class="role-reorder__name">${role.label}</span>
        <span class="role-reorder__buttons">
          <button class="civ-action-btn" title="Move up" aria-label=${`Move ${role.label} up`}
            ?disabled=${i === 0} @click=${() => reorderTo(moveUp(order, i), role)}><i class="fa-solid fa-arrow-up" aria-hidden="true"></i></button>
          <button class="civ-action-btn" title="Move down" aria-label=${`Move ${role.label} down`}
            ?disabled=${i === order.length - 1} @click=${() => reorderTo(moveDown(order, i), role)}><i class="fa-solid fa-arrow-down" aria-hidden="true"></i></button>
          <button class="civ-action-btn" title="Move to top" aria-label=${`Move ${role.label} to top`}
            ?disabled=${i === 0} @click=${() => reorderTo(moveToTop(order, i), role)}><i class="fa-solid fa-angles-up" aria-hidden="true"></i></button>
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
