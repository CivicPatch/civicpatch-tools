import { useState, useEffect } from "haunted";
import { config } from "../assets/config.js";

const WS_URL = config.apiUrl.replace(/^http/, "ws") + "/ws";

// Exponential backoff, capped, with jitter so many tabs reconnecting after one server
// restart don't all retry on the same tick.
const RECONNECT_BASE_DELAY_MS = 1000;
const RECONNECT_MAX_DELAY_MS = 30_000;

function reconnectDelay(attempt) {
  const delay = Math.min(RECONNECT_BASE_DELAY_MS * 2 ** attempt, RECONNECT_MAX_DELAY_MS);
  return delay * (0.8 + Math.random() * 0.4);
}

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

    let stopped = false;
    let socket = null;
    let reconnectTimer = null;
    let attempt = 0;

    const connect = () => {
      socket = new WebSocket(WS_URL);
      setError(null);

      socket.onopen = () => {
        attempt = 0;
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
        setError("WebSocket connection error.");
      };

      // A network blip is common enough that giving up until the next full page load
      // would be the wrong default — retry with backoff instead. A connection the server
      // closed on purpose (e.g. an expired cookie, code 1008) fails the same way again,
      // so the backoff cap keeps that case cheap rather than looping tight.
      socket.onclose = () => {
        setIsConnected(false);
        if (stopped) return;
        reconnectTimer = window.setTimeout(connect, reconnectDelay(attempt));
        attempt += 1;
      };
    };

    connect();

    return () => {
      stopped = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      if (socket) socket.close();
    };
  }, [topic, autoConnect]);

  return { data, isConnected, error };
}
