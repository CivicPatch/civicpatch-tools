import { useState, useEffect } from "haunted";
import { config } from "../assets/config.js";

const WS_URL = config.apiUrl.replace(/^http/, "ws") + "/ws";

/**
 * useWebSocket - subscribes to a single pub/sub topic over WebSocket
 * @param {string|null} topic - e.g. "merge:{userId}"
 * @param {object} [options] - { autoConnect: bool }
 * @returns {{ data, isConnected, error }}
 */
// Socket stays in the effect closure: in state its identity lands in the dep
// array, so opening one re-runs the effect that opened it.
export function useWebSocket(topic, options = {}) {
  const [data, setData] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);
  const autoConnect = !!options.autoConnect;

  useEffect(() => {
    if (!autoConnect || !topic) return;

    const socket = new WebSocket(WS_URL);
    setError(null);

    socket.onopen = () => {
      setIsConnected(true);
      socket.send(JSON.stringify({ action: "subscribe", topics: [topic] }));
    };

    socket.onmessage = (event) => {
      try {
        setData(JSON.parse(event.data));
      } catch {
        setError("Error parsing WebSocket message.");
      }
    };

    socket.onerror = () => {
      setIsConnected(false);
      setError("WebSocket connection error.");
    };

    socket.onclose = () => setIsConnected(false);

    return () => socket.close();
  }, [topic, autoConnect]);

  return { data, isConnected, error };
}
