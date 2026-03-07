import { useState, useEffect } from "haunted";

export function useJurisdiction(jurisdiction_ocdid) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!jurisdiction_ocdid) {
      setIsLoading(false);
      return;
    }

    let cancelled = false;

    async function fetchData() {
      setIsLoading(true);
      setError(null);
      
      try {
        const jurisdictionOcdidFormatted = encodeURIComponent(jurisdiction_ocdid);
        const response = await fetch(
          `/api/api_proxy/jurisdictions?jurisdiction_ocdid=${jurisdictionOcdidFormatted}&with_geom=true`,
        );
        
        if (!response.ok) {
          throw new Error(`Failed to fetch jurisdiction: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (!cancelled) {
          setData({
            data: result.data,
            geo_center: result.geo_center,
          });
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

  return { data, isLoading, error };
}
