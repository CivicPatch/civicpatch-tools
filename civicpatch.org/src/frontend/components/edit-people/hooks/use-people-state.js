import { useState, useMemo } from 'haunted';
import { changedFieldKeys, listChanged, mergeFields, collapseInto, buildPeoplePatch } from './people-state-utils.js';

export function usePeopleState({ people }) {
  const [currentPeople, setCurrentPeople] = useState(people || []);
  const [originalPeople, setOriginalPeople] = useState([]);
  // "Drop this person on publish" is a reviewer decision about a record, not a
  // field of it, so it lives beside the list rather than on the row.
  const [deletedIds, setDeletedIds] = useState(new Set());

  const selectedPeople = currentPeople.filter(p => p._selected).map(p => p.id);

  // Edits are derived from the baseline, not tracked on the records themselves.
  // Memoized because this compares every tracked field on every person against
  // the baseline — it should run per edit, not per render.
  const { changesById, dirtyIds, dirty, peoplePatch } = useMemo(() => {
    const originalById = new Map(originalPeople.map(p => [p.id, p]));
    const changesById = new Map(currentPeople.map(p => [p.id, changedFieldKeys(p, originalById.get(p.id))]));
    const dirtyIds = new Set(
      currentPeople.filter(p => deletedIds.has(p.id) || changesById.get(p.id).length > 0).map(p => p.id)
    );
    return {
      changesById,
      dirtyIds,
      // Field edits and deletions surface in dirtyIds. A reorder changes no field
      // on anyone — it used to stamp _dirty directly — and a merge drops a row
      // from the list, so the id sequence is checked separately.
      dirty: dirtyIds.size > 0 || listChanged(currentPeople, originalPeople),
      peoplePatch: buildPeoplePatch(currentPeople, changesById, deletedIds),
    };
  }, [currentPeople, originalPeople, deletedIds]);

  function assignPeople(peopleToAssign) {
    setCurrentPeople(peopleToAssign);
    setOriginalPeople(peopleToAssign); // For tracking changes
    setDeletedIds(new Set()); // a new baseline carries no decisions
  }

  function updatePerson(key, updates) {
    setCurrentPeople(current => {
      const mapped = current.map(p => p.id === key ? { ...p, ...updates } : p);

      // When re-iding collapses two existing rows, merge them into the survivor.
      if (updates.id && updates.id !== key) {
        const survivor = current.find(p => p.id === updates.id);
        const absorbed = current.find(p => p.id === key);
        if (survivor && absorbed) return collapseInto(survivor, absorbed, mapped);
      }

      return mapped;
    });
  }

  function addPerson(newPerson) {
    setCurrentPeople(current => [newPerson, ...current]);
  }

  function toggleSelect(key) {
    setCurrentPeople(current =>
      current.map(p => p.id === key ? { ...p, _selected: !p._selected } : p)
    );
  }

  function handleDelete(keys) {
    setDeletedIds(current => new Set([...current, ...keys]));
    setCurrentPeople(current => current.map(p => ({ ...p, _selected: false })));
  }

  function handleRestore(key) {
    setDeletedIds(current => {
      const next = new Set(current);
      next.delete(key);
      return next;
    });
  }

  function handleBulkDelete() {
    handleDelete(selectedPeople);
  }

  function handleMerge() {
    setCurrentPeople(current => {
      const selected = current.filter(p => p._selected);
      // Prefer a non-new person as survivor; fall back to the last selected
      const survivor = selected.find(p => !p._isNew) ?? selected[selected.length - 1];
      if (!survivor) return current;
      const absorbed = selected.filter(p => p.id !== survivor.id);
      const merged = mergeFields(survivor, absorbed);
      const absorbedIds = new Set(absorbed.map(p => p.id));
      return current
        .filter(p => !absorbedIds.has(p.id))
        .map(p => p.id === survivor.id ? merged : { ...p, _selected: false });
    });
  }

  // Reset restores the baseline record, which never carried a deletion — so it
  // un-deletes too. That was implicit when _deleted lived on the row (the
  // baseline copy simply had no flag); with a Set it has to be said.
  function handleReset(key) {
    const original = originalPeople.find(p => p.id === key);
    if (original) {
      setCurrentPeople(current => current.map(p => p.id === key ? { ...original } : p));
      handleRestore(key);
    }
  }

  function handleResetAll() {
    setCurrentPeople([...originalPeople]);
    setDeletedIds(new Set());
  }

  function handleTableDataChange(e) {
    const { identifier, field, value } = e.detail;
    if (field === "_selected") {
      toggleSelect(identifier);
    } else {
      updatePerson(identifier, { [field]: value });
    }
  }

  function handleTableDataReorder(e) {
    const { newOrder } = e.detail;
    setCurrentPeople(current => {
      // newOrder is the person ids (uuids) in their new position. Rebuild the
      // array in that order; filter(Boolean) drops any id with no current row
      // (defensive — every id comes from `current`, so nothing is dropped).
      const byId = current.reduce((acc, p) => ({ ...acc, [p.id]: p }), {});
      return newOrder.map(id => byId[id]).filter(Boolean);
    });
  }

  return {
    currentPeople,
    originalPeople,
    selectedPeople,
    changesById,
    dirtyIds,
    deletedIds,
    dirty,
    peoplePatch,
    assignPeople,
    addPerson,
    updatePerson,
    toggleSelect,
    handleDelete,
    handleRestore,
    handleBulkDelete,
    handleMerge,
    handleReset,
    handleResetAll,
    handleTableDataChange,
    handleTableDataReorder,
  };
}
