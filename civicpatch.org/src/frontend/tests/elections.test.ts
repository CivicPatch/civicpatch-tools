import { describe, it, expect } from "vitest";
import {
  groupByState,
  isSoon,
  type Election,
} from "../pages/changeset-summaries-page/elections.ts";

const entry = (over: Partial<Election> = {}): Election => ({
  date: "2026-11-03",
  state: "wa",
  title: "General Election",
  note: null,
  ...over,
});

describe("groupByState", () => {
  it("groups entries under their state, sorted by date within each group", () => {
    const grouped = groupByState([
      entry({ state: "tx", date: "2027-03-01" }),
      entry({ state: "wa", date: "2027-12-27" }),
      entry({ state: "wa", date: "2026-10-21" }),
    ]);
    expect([...grouped.keys()].sort()).toEqual(["tx", "wa"]);
    expect(grouped.get("wa")?.map((e) => e.date)).toEqual(["2026-10-21", "2027-12-27"]);
  });

  it("returns an empty map for no entries", () => {
    expect(groupByState([]).size).toBe(0);
  });
});

describe("isSoon", () => {
  it("is true for a date within the alert window", () => {
    const soon = new Date();
    soon.setUTCDate(soon.getUTCDate() + 10);
    expect(isSoon(soon.toISOString().slice(0, 10))).toBe(true);
  });

  it("is false for a date past the alert window", () => {
    const distant = new Date();
    distant.setUTCDate(distant.getUTCDate() + 365);
    expect(isSoon(distant.toISOString().slice(0, 10))).toBe(false);
  });
});
