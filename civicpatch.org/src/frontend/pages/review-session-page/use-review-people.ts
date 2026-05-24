import { useState, useEffect } from "haunted";
import { generatePersonId } from "../../api.js";
import { buildOtherNames } from "../../utils/name-utils.js";
import { usePeopleState } from "../../components/edit-people/hooks/use-people-state.js";
import { blankPerson, resolvePeopleMatches } from "../../components/edit-people/people-editing.js";
import { type CurrentEntry } from "./review-state.js";

// People-editing for the review card: the same add/resolve/link actions the full
// editor (<civ-editable-people-list>) uses, scoped to the entry under review.
export function useReviewPeople(currentEntry: CurrentEntry | null) {
  const proposed = currentEntry?.pr_people?.proposed ?? [];
  const jurisdictionOcdid = currentEntry?.jurisdiction?.ocdid ?? null;

  const people = usePeopleState({ people: proposed });
  const { assignPeople, addPerson, updatePerson } = people;

  const [resolvedMatches, setResolvedMatches] = useState({});

  async function handleAdd() {
    const personId = await generatePersonId();
    addPerson(blankPerson(personId, jurisdictionOcdid, proposed));
  }

  function handleLinkPerson(e) {
    const { personId, proposedPerson, existingPeople } = e.detail;
    const existingPerson = existingPeople.find((p) => p.id === personId);
    const other_names = buildOtherNames(proposedPerson, existingPerson);
    updatePerson(proposedPerson.id, { id: personId, _isNew: false, other_names });
  }

  useEffect(() => {
    if (!proposed.length || !jurisdictionOcdid) {
      assignPeople([]);
      setResolvedMatches({});
      return;
    }
    resolvePeopleMatches(jurisdictionOcdid, proposed)
      .then(({ tagged, matchMap }) => {
        assignPeople(tagged);
        setResolvedMatches(matchMap);
      })
      .catch(() => {
        assignPeople(proposed);
        setResolvedMatches({});
      });
  }, [currentEntry?.pr_people]);

  return { ...people, resolvedMatches, handleAdd, handleLinkPerson };
}
