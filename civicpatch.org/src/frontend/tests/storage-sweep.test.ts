import { describe, it, expect } from "vitest";
import { sweepExpired, sweepExpiredStorageDaily } from "../utils/storage-sweep.js";
import { STORAGE_KEYS } from "../utils/storage-keys.js";

const NOW = 1_700_000_000_000;
const HOUR = 60 * 60 * 1000;

// Mirrors what use-local-storage.js writes.
const entry = (value: unknown, expiresAt: number | null) =>
  JSON.stringify({ __value: value, __expiresAt: expiresAt });

function fakeStorage(initial: Record<string, string> = {}) {
  const map = new Map(Object.entries(initial));
  return {
    get length() {
      return map.size;
    },
    key: (i: number) => [...map.keys()][i],
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => void map.set(k, v),
    removeItem: (k: string) => void map.delete(k),
    keys: () => [...map.keys()],
  };
}

describe("sweepExpired", () => {
  it("drops entries whose expiry has passed", () => {
    const storage = fakeStorage({ "review:issue-checks:req-1": entry({}, NOW - HOUR) });
    expect(sweepExpired(storage, NOW)).toEqual(["review:issue-checks:req-1"]);
    expect(storage.keys()).toEqual([]);
  });

  it("keeps entries that have not expired yet", () => {
    const storage = fakeStorage({ "review:issue-checks:req-1": entry({}, NOW + HOUR) });
    sweepExpired(storage, NOW);
    expect(storage.keys()).toEqual(["review:issue-checks:req-1"]);
  });

  it("keeps the PERSIST_FOREVER singletons, which carry a null expiry", () => {
    const storage = fakeStorage({ [STORAGE_KEYS.DEFAULT_STATE]: entry("nj", null) });
    sweepExpired(storage, NOW);
    expect(storage.keys()).toEqual([STORAGE_KEYS.DEFAULT_STATE]);
  });

  // Removing inside the walk reindexes the store, so the second of two adjacent
  // expired keys would be skipped.
  it("drops every expired key when they are adjacent", () => {
    const storage = fakeStorage({
      a: entry({}, NOW - HOUR),
      b: entry({}, NOW - HOUR),
      c: entry({}, NOW - HOUR),
    });
    sweepExpired(storage, NOW);
    expect(storage.keys()).toEqual([]);
  });

  it("leaves values written before the envelope existed", () => {
    const storage = fakeStorage({ [STORAGE_KEYS.THEME]: '"dark"', junk: "not json" });
    sweepExpired(storage, NOW);
    expect(storage.keys()).toEqual([STORAGE_KEYS.THEME, "junk"]);
  });
});

describe("sweepExpiredStorageDaily", () => {
  it("sweeps and stamps on a store that has never been swept", () => {
    const storage = fakeStorage({ stale: entry({}, NOW - HOUR) });
    expect(sweepExpiredStorageDaily(storage, NOW)).toEqual(["stale"]);
    expect(storage.getItem(STORAGE_KEYS.SWEPT_AT)).toBe(String(NOW));
  });

  it("does nothing again within the day", () => {
    const storage = fakeStorage({ [STORAGE_KEYS.SWEPT_AT]: String(NOW) });
    storage.setItem("stale", entry({}, NOW - HOUR));
    expect(sweepExpiredStorageDaily(storage, NOW + HOUR)).toEqual([]);
    expect(storage.getItem("stale")).not.toBeNull();
  });

  it("sweeps again once a day has passed", () => {
    const storage = fakeStorage({ [STORAGE_KEYS.SWEPT_AT]: String(NOW) });
    storage.setItem("stale", entry({}, NOW - HOUR));
    expect(sweepExpiredStorageDaily(storage, NOW + 25 * HOUR)).toEqual(["stale"]);
  });

  // A stamp inside the envelope would be swept by the walk it just started.
  it("never collects its own stamp", () => {
    const storage = fakeStorage();
    sweepExpiredStorageDaily(storage, NOW);
    sweepExpiredStorageDaily(storage, NOW + 25 * HOUR);
    expect(storage.getItem(STORAGE_KEYS.SWEPT_AT)).toBe(String(NOW + 25 * HOUR));
  });
});
