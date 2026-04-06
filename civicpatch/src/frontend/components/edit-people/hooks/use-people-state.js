// hooks/use-people-state.js
import { useState } from 'haunted';

const PERSON_FIELDS = {
  single: ["name", "image", "cdn_image", "start_date", "end_date", "updated_at"],
  array:  ["other_names", "phones", "emails", "urls", "source_urls"],
  object: ["office"],
};

const TRACKED_FIELDS = [...PERSON_FIELDS.single, ...PERSON_FIELDS.array, ...PERSON_FIELDS.object];

function applyUpdate(person, updates, original) {
  const next = { ...person, ...updates };
  const changedFields = TRACKED_FIELDS.filter(
    field => JSON.stringify(next[field]) !== JSON.stringify(original?.[field])
  );
  return { ...next, _dirty: changedFields.length > 0 || updates._deleted === true, _changes: changedFields };
}

function mergeFields(survivor, absorbed) {
  const merged = { ...survivor };

  for (const field of PERSON_FIELDS.single) {
    merged[field] = [survivor, ...absorbed].map(p => p[field]).find(v => v != null && v !== "") ?? null;
  }
  for (const field of PERSON_FIELDS.array) {
    merged[field] = Array.from(new Set(
      [survivor, ...absorbed].flatMap(p => (p[field] || []).filter(Boolean))
    ));
  }

  const absorbedNames = absorbed.map(p => p.name).filter(Boolean);
  merged.other_names = Array.from(new Set([...merged.other_names, ...absorbedNames]))
    .filter(n => n !== merged.name);

  const officeNames = Array.from(new Set(
    [survivor, ...absorbed].flatMap(p => (p.office?.name || "").split(" - ").map(s => s.trim())).filter(Boolean)
  ));
  if (officeNames.length > 0) {
    merged.office = { ...(merged.office || {}), name: officeNames.join(" - ") };
  }

  return { ...merged, _dirty: true, _changes: TRACKED_FIELDS, _selected: false };
}

function collapseInto(survivor, absorbed, list) {
  const merged = mergeFields(survivor, [absorbed]);
  return list.filter(p => p.id !== survivor.id && p.id !== absorbed.id).concat(merged);
}

export function usePeopleState({ people }) {
  const [currentPeople, setCurrentPeople] = useState(people || []);
  const [originalPeople, setOriginalPeople] = useState([]);

  const selectedPeople = currentPeople.filter(p => p._selected).map(p => p.id);
  const dirty = currentPeople.some(p => p._dirty);
  const peopleToSubmit = currentPeople
    .filter(p => !p._deleted)
    .map(({ _dirty, _changes, _selected, _deleted, _isNew, ...person }) => person);

  function assignPeople(peopleToAssign) {
    setCurrentPeople(peopleToAssign);
    setOriginalPeople(peopleToAssign); // For tracking changes
  }

  function updatePerson(key, updates) {
    setCurrentPeople(current => {
      const original = originalPeople.find(p => p.id === key);
      const mapped = current.map(p => p.id === key ? applyUpdate(p, updates, original) : p);

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
    const keySet = new Set(keys);
    setCurrentPeople(current =>
      current.map(p => keySet.has(p.id)
        ? { ...p, _deleted: true, _dirty: true, _changes: TRACKED_FIELDS, _selected: false }
        : { ...p, _selected: false }
      )
    );
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

  function handleReset(key) {
    const original = originalPeople.find(p => p.id === key);
    if (original) {
      setCurrentPeople(current => current.map(p => p.id === key ? { ...original } : p));
    }
  }

  function handleResetAll() {
    setCurrentPeople([...originalPeople]);
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
      const byId = current.reduce((acc, p) => ({ ...acc, [p.id]: { ...p, _dirty: true } }), {});
      return newOrder.map(id => byId[id] || byId[parseInt(id)]);
    });
  }

  return {
    currentPeople,
    originalPeople,
    selectedPeople,
    dirty,
    peopleToSubmit,
    assignPeople,
    addPerson,
    updatePerson,
    toggleSelect,
    handleDelete,
    handleBulkDelete,
    handleMerge,
    handleReset,
    handleResetAll,
    handleTableDataChange,
    handleTableDataReorder,
  };
}