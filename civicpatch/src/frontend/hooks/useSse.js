import { useState, useEffect, useCallback } from "haunted";

/**
 * useSSE - Generalized Server-Sent Events hook
 * @param {string|function} endpoint - SSE endpoint URL or function that returns a URL
 * @param {object} [options] - Optional config (e.g., autoConnect)
 * @returns {object} { data, isConnected, error, connect, disconnect }
 */
export function useSSE(endpoint, options = {}) {
  const [data, setData] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);
  const [eventSource, setEventSource] = useState(null);

  const getUrl = useCallback(
    () => (typeof endpoint === "function" ? endpoint() : endpoint),
    [endpoint]
  );

  const connect = useCallback(() => {
    if (eventSource) return;
    const url = getUrl();
    try {
      const es = new EventSource(url);
      setEventSource(es);
      setError(null);

      es.onopen = () => setIsConnected(true);

      es.onmessage = (event) => {
        try {
          setData(JSON.parse(event.data));
        } catch (e) {
          setError("Error parsing SSE data.");
        }
      };

      es.onerror = (e) => {
        console.error("SSE error:", e);
        setIsConnected(false);
        setError("SSE connection error.");
      };
    } catch (e) {
      setError("Failed to initialize SSE.");
    }
  }, [eventSource, getUrl]);

  const disconnect = useCallback(() => {
    if (eventSource) {
      eventSource.close();
      setEventSource(null);
      setIsConnected(false);
    }
  }, [eventSource]);

  // Auto-connect if options.autoConnect is true
  useEffect(() => {
    if (options.autoConnect) {
      connect();
    }
    // Cleanup on unmount
    return () => {
      if (eventSource) eventSource.close();
    };
  }, [options.autoConnect, connect, eventSource]);

  return { data, isConnected, error, connect, disconnect };
}