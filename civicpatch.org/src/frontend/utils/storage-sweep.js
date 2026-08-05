// Reclaims expired localStorage entries. useLocalStorage only expires a key when
// something reads it, so a key nobody opens again needs collecting from outside.
//
// Storage and clock are arguments rather than globals so this is testable; the
// hook in hooks/use-storage-sweep.js supplies the real ones.

import { STORAGE_KEYS } from "./storage-keys.js";

const SWEEP_INTERVAL_MS = 24 * 60 * 60 * 1000;

// The {__value, __expiresAt} envelope is written by use-local-storage.js. Its own
// read path also gates on the caller's ttl, which a sweep has no equivalent of —
// hence a separate predicate rather than a shared one.
function isExpiredEntry(raw, now) {
  try {
    const parsed = JSON.parse(raw);
    return parsed?.__expiresAt != null && now > parsed.__expiresAt;
  } catch {
    return false; // not ours, or written before the envelope existed
  }
}

// Walks the whole store rather than a known prefix, so a key that gains a TTL
// later is swept without having to be registered here. Keys are collected before
// removal — removing mid-loop reindexes the store and skips the next entry.
export function sweepExpired(storage, now) {
  const expired = [];
  for (let i = 0; i < storage.length; i++) {
    const key = storage.key(i);
    if (isExpiredEntry(storage.getItem(key), now)) expired.push(key);
  }
  for (const key of expired) storage.removeItem(key);
  return expired;
}

// The stamp is a bare number rather than the envelope: it is the sweep's own
// bookkeeping, and staying outside the envelope means the sweep can never
// collect the record of when it last ran.
export function sweepExpiredStorageDaily(storage, now) {
  const sweptAt = Number(storage.getItem(STORAGE_KEYS.SWEPT_AT));
  if (sweptAt && now - sweptAt < SWEEP_INTERVAL_MS) return [];
  storage.setItem(STORAGE_KEYS.SWEPT_AT, String(now));
  return sweepExpired(storage, now);
}
