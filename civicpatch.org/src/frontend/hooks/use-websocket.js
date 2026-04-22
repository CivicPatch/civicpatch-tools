import { useState, useEffect, useCallback } from "haunted";
import { config } from "../assets/config.js";

const WS_URL = config.apiUrl.replace(/^http/, "ws") + "/ws";

/**
 * useWebSocket - subscribes to a single pub/sub topic over WebSocket
 * @param {string|null} topic - e.g. "merge:{userId}"
 * @param {object} [options] - { autoConnect: bool }
 * @returns {{ data, isConnected, error, connect, disconnect }}
 */
export function useWebSocket(topic, options = {}) {
  const [data, setData] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);
  const [ws, setWs] = useState(null);

  const connect = useCallback(() => {
    if (ws || !topic) return;
    try {
      const socket = new WebSocket(WS_URL);
      setWs(socket);
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

      socket.onclose = () => {
        setIsConnected(false);
        setWs(null);
      };
    } catch {
      setError("Failed to initialize WebSocket.");
    }
  }, [ws, topic]);

  const disconnect = useCallback(() => {
    if (ws) {
      ws.close();
      setWs(null);
      setIsConnected(false);
    }
  }, [ws]);

  useEffect(() => {
    if (options.autoConnect) {
      connect();
    }
    return () => {
      if (ws) ws.close();
    };
  }, [options.autoConnect, connect, ws]);

  return { data, isConnected, error, connect, disconnect };
}
