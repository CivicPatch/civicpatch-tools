import { useState, useEffect } from "haunted";

export function useDirtyPeople(currentRequest) {
  const [isDirty, setIsDirty] = useState(false);
  const [pendingPeople, setPendingPeople] = useState(null);

  useEffect(() => {
    setIsDirty(false);
    setPendingPeople(null);
  }, [currentRequest]);

  const handleDirtyChange = (e) => {
    setIsDirty(e.detail.dirty);
    setPendingPeople(e.detail.people);
  };

  return { isDirty, setIsDirty, pendingPeople, handleDirtyChange };
}
