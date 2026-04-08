import { useState, useEffect } from "haunted";

export function usePeople(jurisdiction_ocdid) {
  const [people, setPeople] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const refetch = async () => {
    if (!jurisdiction_ocdid) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const encodedOcdid = encodeURIComponent(jurisdiction_ocdid);
      const response = await fetch(
        `/api/v1/people?jurisdiction_ocdid=${encodedOcdid}`,
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch people: ${response.statusText}`);
      }

      const result = await response.json();
      setPeople(result.data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      if (!jurisdiction_ocdid) {
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const encodedOcdid = encodeURIComponent(jurisdiction_ocdid);
        const response = await fetch(
          `/api/v1/people?jurisdiction_ocdid=${encodedOcdid}`,
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch people: ${response.statusText}`);
        }

        const result = await response.json();

        if (!cancelled) {
          setPeople(result.data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    fetchData();

    return () => {
      cancelled = true;
    };
  }, [jurisdiction_ocdid]);

  return { people, isLoading, error, refetch };
}
