import { useState, useMemo } from 'haunted';
import { changedFieldKeys, listChanged, buildPeoplePatch, pruneIds } from './people-state-utils.js';
import { personIdIn } from '../../people/person-cards.ts';

export function usePeopleState({ people }) {
  const [currentPeople, setCurrentPeople] = useState(people || []);
  const [originalPeople, setOriginalPeople] = useState([]);
  // "Drop this on publish" is a reviewer decision about a record, not a field of
  // it, so it lives beside the list rather than on the row. Keyed the way the page
  // keys its cards: a person id in a review, a person-in-a-body on a roster.
  const [removedIds, setRemovedIds] = useState(new Set());
  // Someone the scrape didn't find, whom the reviewer restored. It has to be
  // remembered rather than derived: restoring copies their old record into the
  // list, which makes them identical on both sides — indistinguishable from a
  // person nothing happened to. removedIds can't express it either, since a
  // person the scrape didn't find was never removed by the reviewer.
  const [restoredIds, setRestoredIds] = useState(new Set());
  // Absorbed id → survivor id. Kept apart from the list because the absorbed row is gone
  // from it, and the server has to be told who they were merged into.
  const [mergedInto, setMergedInto] = useState(new Map());

  const selectedPeople = currentPeople.filter(p => p._selected).map(p => p.id);

  // Edits are derived from the baseline, not tracked on the records themselves.
  // Memoized because this compares every tracked field on every person against
  // the baseline — it should run per edit, not per render.
  const { changesById, dirtyIds, dirty, peoplePatch } = useMemo(() => {
    const originalById = new Map(originalPeople.map(p => [p.id, p]));
    const changesById = new Map(currentPeople.map(p => [p.id, changedFieldKeys(p, originalById.get(p.id))]));
    const removedPeople = new Set([...removedIds].map(personIdIn));
    const dirtyIds = new Set(
      currentPeople.filter(p => removedPeople.has(p.id) || changesById.get(p.id).length > 0).map(p => p.id)
    );
    return {
      changesById,
      dirtyIds,
      // Field edits and removals surface in dirtyIds. A reorder changes no field
      // on anyone — it used to stamp _dirty directly — and a merge drops a row
      // from the list, so the id sequence is checked separately.
      dirty: dirtyIds.size > 0 || listChanged(currentPeople, originalPeople),
      peoplePatch: buildPeoplePatch(currentPeople, changesById, removedIds, new Set(mergedInto.values())),
    };
  }, [currentPeople, originalPeople, removedIds, mergedInto]);

  function assignPeople(peopleToAssign) {
    setCurrentPeople(peopleToAssign);
    setOriginalPeople(peopleToAssign); // For tracking changes
    // A new baseline carries none of the previous card's decisions.
    setRemovedIds(new Set());
    setRestoredIds(new Set());
    setMergedInto(new Map());
  }

  function updatePerson(key, updates) {
    // Text fields save on every keystroke, so this must stay a functional
    // update: reading the list from the closure drops a character whenever two
    // edits land in the same frame.
    setCurrentPeople(current => current.map(p => p.id === key ? { ...p, ...updates } : p));
  }

  // The one way two rows become one. What the merged record *contains* is the
  // caller's policy; this owns only the consequences — the absorbed row leaves
  // the list, and every id-keyed set drops its id.
  function mergePeople(survivorId, absorbedId, mergedRecord) {
    // The survivor may not be in the working list at all: someone the scrape
    // didn't find has an old side only. When that happens the merged record
    // takes the absorbed row's slot, rather than being dropped on the floor.
    const survivorIsListed = currentPeople.some(p => p.id === survivorId);
    setPeopleAndPruneIds(
      currentPeople.flatMap(p => {
        if (p.id === survivorId) return [mergedRecord];
        if (p.id === absorbedId) return survivorIsListed ? [] : [mergedRecord];
        return [p];
      })
    );
    setMergedInto(current => new Map([...current, [absorbedId, survivorId]]));
  }

  // An id that no longer names anyone must leave every id-keyed set, or it
  // silently drops whoever inherits it. Every merge path goes through here, and
  // the pruning is paired with the assignment because that is the only moment
  // the two can disagree.
  function setPeopleAndPruneIds(remaining) {
    const living = new Set(remaining.map(p => p.id));
    setCurrentPeople(remaining);
    setRemovedIds(current => pruneIds(current, living));
    setRestoredIds(current => pruneIds(current, living));
  }

  // Appended, not prepended: the review card orders by slot, so a new person
  // belongs after the roster — right where the add affordance stood.
  function addPerson(newPerson) {
    setCurrentPeople(current => [...current, newPerson]);
  }

  function toggleSelect(key) {
    setCurrentPeople(current =>
      current.map(p => p.id === key ? { ...p, _selected: !p._selected } : p)
    );
  }

  function handleRemove(keys) {
    setRemovedIds(current => new Set([...current, ...keys]));
    setCurrentPeople(current => current.map(p => ({ ...p, _selected: false })));
  }

  // Takes whichever rows the key names: one row on a roster, or — given a bare person id, which
  // is what Reset has — every row of theirs.
  function handleUnremove(key) {
    setRemovedIds(current => {
      const next = new Set(current);
      for (const removed of current) {
        if (removed === key || personIdIn(removed) === key) next.delete(removed);
      }
      return next;
    });
  }

  // Put back someone the scrape didn't find. Their old record joins the list, so
  // the publish patch carries them and the backend stops reading their absence
  // as a removal. Appended rather than slotted: a person the scrape missed has no
  // position in the proposed list to return to.
  function handleRestore(person) {
    setCurrentPeople(current =>
      current.some(p => p.id === person.id) ? current : [...current, { ...person }]
    );
    setRestoredIds(current => new Set([...current, person.id]));
  }

  function handleUndoRestore(key) {
    setCurrentPeople(current => current.filter(p => p.id !== key));
    setRestoredIds(current => {
      const next = new Set(current);
      next.delete(key);
      return next;
    });
  }

  function handleBulkRemove() {
    handleRemove(selectedPeople);
  }

  // Reset returns one person to how the card loaded. For someone restored that
  // means leaving the list again — they had no place in it at load, so
  // there is no baseline record to return them to.
  //
  // Otherwise it restores the baseline record, which never carried a removal,
  // so it un-removes too. That was implicit when the flag lived on the row (the
  // baseline copy simply had no flag); with a Set it has to be said.
  //
  // A survivor's reset also undoes the merges into them, bringing the absorbed rows back.
  //
  // A person with no baseline record at all was added this session, not loaded
  // from the server — resetting them means undoing the add.
  function handleReset(key) {
    if (restoredIds.has(key)) {
      handleUndoRestore(key);
      return;
    }
    const original = originalPeople.find(p => p.id === key);
    if (original) {
      const unmerged = originalPeople.filter(p => mergedInto.get(p.id) === key);
      setCurrentPeople(current => [
        ...current.map(p => p.id === key ? { ...original } : p),
        ...unmerged.map(p => ({ ...p })),
      ]);
      setMergedInto(current => new Map([...current].filter(([, survivorId]) => survivorId !== key)));
      handleUnremove(key);
      return;
    }
    setCurrentPeople(current => current.filter(p => p.id !== key));
  }

  function handleResetAll() {
    setCurrentPeople([...originalPeople]);
    setRemovedIds(new Set());
    setRestoredIds(new Set());
    setMergedInto(new Map());
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
    removedIds,
    restoredIds,
    mergedInto,
    dirty,
    peoplePatch,
    assignPeople,
    addPerson,
    updatePerson,
    mergePeople,
    toggleSelect,
    handleRemove,
    handleUnremove,
    handleRestore,
    handleUndoRestore,
    handleBulkRemove,
    handleReset,
    handleResetAll,
    handleTableDataChange,
    handleTableDataReorder,
  };
}
