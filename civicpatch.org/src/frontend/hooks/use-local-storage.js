import { useState } from "haunted";

const ONE_DAY_MS = 24 * 60 * 60 * 1000;

export const PERSIST_FOREVER = null;

function readStored(key, ttl) {
  const raw = localStorage.getItem(key);
  if (raw === null) return { found: false };
  try {
    const parsed = JSON.parse(raw);
    if (parsed !== null && typeof parsed === "object" && "__value" in parsed) {
      if (ttl !== null && parsed.__expiresAt !== null && Date.now() > parsed.__expiresAt) {
        localStorage.removeItem(key);
        return { found: false };
      }
      return { found: true, value: parsed.__value };
    }
    // legacy: value stored without TTL wrapper
    return { found: true, value: parsed };
  } catch {
    return { found: true, value: raw };
  }
}

function writeStored(key, value, ttl) {
  const entry = {
    __value: value,
    __expiresAt: ttl === null ? null : Date.now() + ttl,
  };
  localStorage.setItem(key, JSON.stringify(entry));
}

export function useLocalStorage(key, defaultValue, { ttl = ONE_DAY_MS } = {}) {
  const [value, setValueState] = useState(() => {
    const stored = readStored(key, ttl);
    if (stored.found) return stored.value;
    return typeof defaultValue === "function" ? defaultValue() : defaultValue;
  });

  const setValue = (newValue) => {
    setValueState(newValue);
    writeStored(key, newValue, ttl);
  };

  return [value, setValue];
}
