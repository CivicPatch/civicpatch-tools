// hooks/use-people-state.js
import { useState } from 'haunted';

const PERSON_FIELDS = {
  single: ["name", "image", "cdn_image", "start_date", "end_date", "updated_at"],
  array:  ["other_names", "phones", "emails", "urls", "source_urls"],
  object: ["office"],
};

const TRACKED_FIELDS = [...PERSON_FIELDS.single, ...PERSON_FIELDS.array, ...PERSON_FIELDS.object];

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
    setCurrentPeople(current =>
      current.map(person => {
        if (person.id !== key) return person;
        const original = originalPeople.find(p => p.id === key);
        const next = { ...person, ...updates };
        const changedFields = TRACKED_FIELDS.filter(
          field => JSON.stringify(next[field]) !== JSON.stringify(original?.[field])
        );
        return {
          ...next,
          _dirty: changedFields.length > 0 || updates._deleted === true,
          _changes: changedFields,
        };
      })
    );
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
    const next = keys.reduce((acc, key) => {
      const person = acc.find(p => p.id === key);
      if (!person) return acc;
      if (person._isNew) return acc.filter(p => p.id !== key);
      const without = acc.filter(p => p.id !== key);
      const deleted = { ...person, _deleted: true, _dirty: true, _changes: TRACKED_FIELDS };
      return [...without, deleted];
    }, currentPeople);
    setCurrentPeople(next);
  }

  function handleBulkDelete() {
    handleDelete(selectedPeople);
  }

  function handleMerge() {
    // When merging a set of people, always keep the person who is not new as the base
    const peopleToMerge = currentPeople.filter(p => selectedPeople.includes(p.id));
    const baseIndex = currentPeople.findIndex(p => selectedPeople.includes(p.id) && !p._isNew) ?? currentPeople.findIndex(p => selectedPeople.includes(p.id));
    if (baseIndex === -1) return;
    const merged = { ...currentPeople[baseIndex] };

    for (const field of PERSON_FIELDS.single) {
      merged[field] = peopleToMerge.map(p => p[field]).find(v => v != null && v !== "") ?? null;
    }
    for (const field of PERSON_FIELDS.array) {
      merged[field] = Array.from(new Set(
        peopleToMerge.flatMap(p => [p[field]].flat().filter(Boolean))
      ));
    }

    // Office gets special treatment: merge names, keep other fields from base
    const officeNames = Array.from(new Set(peopleToMerge.map(p => p.office?.name).filter(Boolean)));
    if (officeNames.length > 0) {
      merged.office = { ...(merged.office || {}), name: officeNames.join(" - ") };
    }

    setCurrentPeople(current =>
      current
        .filter(p => !selectedPeople.includes(p.id) || p.id === merged.id)
        .map(p => p.id === merged.id
          ? { ...merged, _dirty: true, _changes: TRACKED_FIELDS, _selected: false }
          : { ...p, _selected: false }
        )
    );
  }

  function handleReset(key) {
    const original = originalPeople.find(p => p.id === key);
    if (original) {
      setCurrentPeople(current => current.map(p => p.id === key ? { ...original } : p));
    }
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
    handleTableDataChange,
    handleTableDataReorder,
  };
}