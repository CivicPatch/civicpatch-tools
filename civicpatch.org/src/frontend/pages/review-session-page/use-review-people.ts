import { useEffect } from "haunted";
import { generatePersonId } from "../../api.js";
import { usePeopleState } from "../../components/edit-people/hooks/use-people-state.js";
import { emptyPerson, resolvePeopleMatches } from "../../components/edit-people/people-editing.js";
import { type CurrentEntry } from "./review-state.js";

// People-editing for the review card: the same add/resolve/link actions the full
// editor (<civ-editable-people-list>) uses, scoped to the entry under review.
export function useReviewPeople(currentEntry: CurrentEntry | null) {
  const proposed = currentEntry?.pr_people?.proposed ?? [];
  const jurisdictionOcdid = currentEntry?.jurisdiction?.ocdid ?? null;

  const people = usePeopleState({ people: proposed });
  const { assignPeople, addPerson } = people;

  // Returns the new id so the caller can open the editor on them — adding a person
  // is the start of filling them in, not an end in itself.
  async function handleAdd(): Promise<string> {
    const personId = await generatePersonId();
    addPerson(emptyPerson(personId, jurisdictionOcdid));
    return personId;
  }

  useEffect(() => {
    if (!proposed.length || !jurisdictionOcdid) {
      assignPeople([]);
      return;
    }
    resolvePeopleMatches(jurisdictionOcdid, proposed)
      .then(({ tagged }) => assignPeople(tagged))
      .catch(() => assignPeople(proposed));
  }, [currentEntry?.pr_people]);

  return { ...people, handleAdd };
}
