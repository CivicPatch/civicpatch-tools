import { describe, it, expect } from "vitest";
import {
  takeSnapshot,
  planRevert,
  isUnchangedSince,
} from "../components/review/person-snapshot.js";

const record = (over: Record<string, unknown> = {}) => ({
  id: "a",
  name: "Maria",
  office: { name: "Mayor", division_ocdid: "ocd-division/country:us/state:nh/place:x" },
  emails: [],
  ...over,
});

const ids = (...values: string[]) => new Set(values);

describe("takeSnapshot", () => {
  it("copies the record rather than holding it", () => {
    const live: any = record();
    const snap = takeSnapshot("a", live, ids(), ids());
    // Every keystroke mutates the live record; a held reference would make the
    // snapshot track the very edits it exists to undo.
    live.name = "Marie";
    expect((snap.record as any).name).toBe("Maria");
  });

  it("captures the departure flags, not only the values", () => {
    const snap = takeSnapshot("a", record(), ids("a"), ids());
    expect(snap.isDeleted).toBe(true);
    expect(snap.isRestored).toBe(false);
  });
});

describe("planRevert", () => {
  it("hands back the whole record, so every touched field is restored at once", () => {
    const snap = takeSnapshot("a", record(), ids(), ids());
    expect(planRevert(snap, ids(), ids()).updates).toMatchObject({ name: "Maria" });
  });

  it("undeletes someone deleted since the modal opened", () => {
    const snap = takeSnapshot("a", record(), ids(), ids());
    const plan = planRevert(snap, ids("a"), ids());
    expect(plan.undelete).toBe(true);
    expect(plan.delete).toBe(false);
  });

  it("re-deletes someone who was deleted at open and has since been undeleted", () => {
    const snap = takeSnapshot("a", record(), ids("a"), ids());
    const plan = planRevert(snap, ids(), ids());
    expect(plan.delete).toBe(true);
    expect(plan.undelete).toBe(false);
  });

  it("undoes a restore made inside the modal", () => {
    const snap = takeSnapshot("a", record(), ids(), ids());
    expect(planRevert(snap, ids(), ids("a")).undoRestore).toBe(true);
  });

  it("puts back a restore that was undone inside the modal", () => {
    const snap = takeSnapshot("a", record(), ids(), ids("a"));
    expect(planRevert(snap, ids(), ids()).restore).toBe(true);
  });

  it("asks for nothing when nothing moved", () => {
    const snap = takeSnapshot("a", record(), ids(), ids());
    const plan = planRevert(snap, ids(), ids());
    expect([plan.delete, plan.undelete, plan.restore, plan.undoRestore]).toEqual([
      false, false, false, false,
    ]);
  });

  it("restores values and flags together — half of each is an impossible state", () => {
    // Someone restored at open, then edited and un-restored. Putting the values
    // back without the flag would leave them reading as unchanged while having
    // no record to publish (§12).
    const snap = takeSnapshot("a", record({ name: "Maria" }), ids(), ids("a"));
    const plan = planRevert(snap, ids(), ids());
    expect(plan.updates).toMatchObject({ name: "Maria" });
    expect(plan.restore).toBe(true);
  });
});

describe("isUnchangedSince", () => {
  it("is true when neither values nor flags moved", () => {
    const snap = takeSnapshot("a", record(), ids(), ids());
    expect(isUnchangedSince(snap, record(), ids(), ids())).toBe(true);
  });

  it("is false when a value moved", () => {
    const snap = takeSnapshot("a", record(), ids(), ids());
    expect(isUnchangedSince(snap, record({ name: "Marie" }), ids(), ids())).toBe(false);
  });

  it("is false when only a flag moved", () => {
    const snap = takeSnapshot("a", record(), ids(), ids());
    expect(isUnchangedSince(snap, record(), ids("a"), ids())).toBe(false);
  });
});
