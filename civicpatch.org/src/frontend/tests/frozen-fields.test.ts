import { describe, it, expect } from "vitest";
import {
  foldVisible,
  visibleFields,
  isFieldVisible,
  frozenFieldKeys,
  nextFrozen,
  pruneToLiving,
  EMPTY_FROZEN,
  INITIAL_FROZEN_STATE,
  type FrozenFields,
} from "../components/person-editor/frozen-fields.js";
import {
  FieldReason,
  type FieldReasonKey,
  type FieldSpec,
  type ScalarDiffState,
  type SurvivingField,
} from "../components/fields/field-model.js";

const field = (key: string): FieldSpec => ({ key, label: key, type: "text" });

const surviving = (
  key: string,
  reason: FieldReasonKey,
  state: ScalarDiffState = "changed",
  error: string | null = null,
): SurvivingField => ({ field: field(key), state, reason, error });

const card = (personId: string, ...fields: SurvivingField[]) => ({
  personId,
  surviving: fields,
});

describe("foldVisible", () => {
  it("seeds an empty map from a card's surviving fields", () => {
    const frozen = foldVisible(EMPTY_FROZEN, [
      card("a", surviving("name", FieldReason.DIFF), surviving("emails", FieldReason.DIFF)),
    ]);
    expect(frozenFieldKeys(frozen, "a")).toEqual(["name", "emails"]);
  });

  it("keeps fields that stop surviving — the never-leave half of the rule", () => {
    const seeded = foldVisible(EMPTY_FROZEN, [card("a", surviving("end_date", FieldReason.ERROR))]);
    // The reviewer fixes it, so end_date no longer surfaces on its own.
    const after = foldVisible(seeded, [card("a")]);
    expect(isFieldVisible(after, "a", "end_date")).toBe(true);
  });

  it("adds a field that surfaces later — the may-join half", () => {
    const seeded = foldVisible(EMPTY_FROZEN, [card("a", surviving("name", FieldReason.DIFF))]);
    const after = foldVisible(seeded, [
      card("a", surviving("name", FieldReason.DIFF), surviving("end_date", FieldReason.ERROR)),
    ]);
    expect(frozenFieldKeys(after, "a")).toEqual(["name", "end_date"]);
  });

  it("keeps the reason a field FIRST appeared under, not the latest one", () => {
    const seeded = foldVisible(EMPTY_FROZEN, [card("a", surviving("end_date", FieldReason.DIFF))]);
    const after = foldVisible(seeded, [card("a", surviving("end_date", FieldReason.ERROR))]);
    expect(visibleFields(after, "a").get("end_date")).toBe(FieldReason.DIFF);
  });

  it("returns the SAME reference when nothing new appeared", () => {
    const seeded = foldVisible(EMPTY_FROZEN, [card("a", surviving("name", FieldReason.DIFF))]);
    const again = foldVisible(seeded, [card("a", surviving("name", FieldReason.DIFF))]);
    expect(again).toBe(seeded);
  });

  it("returns a new reference when anything is added", () => {
    const seeded = foldVisible(EMPTY_FROZEN, [card("a", surviving("name", FieldReason.DIFF))]);
    const grown = foldVisible(seeded, [card("a", surviving("emails", FieldReason.DIFF))]);
    expect(grown).not.toBe(seeded);
  });

  it("does not mutate the map it was given", () => {
    const seeded = foldVisible(EMPTY_FROZEN, [card("a", surviving("name", FieldReason.DIFF))]);
    foldVisible(seeded, [card("a", surviving("emails", FieldReason.DIFF))]);
    expect(frozenFieldKeys(seeded, "a")).toEqual(["name"]);
  });

  it("keeps people independent", () => {
    const frozen = foldVisible(EMPTY_FROZEN, [
      card("a", surviving("name", FieldReason.DIFF)),
      card("b", surviving("emails", FieldReason.ISSUE)),
    ]);
    expect(frozenFieldKeys(frozen, "a")).toEqual(["name"]);
    expect(frozenFieldKeys(frozen, "b")).toEqual(["emails"]);
  });

  it("treats a person it has never seen as having no visible fields", () => {
    expect(frozenFieldKeys(EMPTY_FROZEN, "nobody")).toEqual([]);
    expect(isFieldVisible(EMPTY_FROZEN, "nobody", "name")).toBe(false);
  });

  it("survives the full error round trip: hidden → errors → fixed → still shown", () => {
    // Loads with only `name` differing; end_date is collapsed.
    let frozen: FrozenFields = foldVisible(EMPTY_FROZEN, [card("a", surviving("name", FieldReason.DIFF))]);
    expect(isFieldVisible(frozen, "a", "end_date")).toBe(false);

    // Editing start_date raises the term-order error on end_date.
    frozen = foldVisible(frozen, [
      card("a", surviving("name", FieldReason.DIFF), surviving("end_date", FieldReason.ERROR, "same", "Term end is before term start")),
    ]);
    expect(isFieldVisible(frozen, "a", "end_date")).toBe(true);

    // Fixing it clears the error — and the row must stay, to show it resolved.
    frozen = foldVisible(frozen, [card("a", surviving("name", FieldReason.DIFF))]);
    expect(isFieldVisible(frozen, "a", "end_date")).toBe(true);
    expect(visibleFields(frozen, "a").get("end_date")).toBe(FieldReason.ERROR);
  });
});

describe("nextFrozen", () => {
  const CARD_A = "req-a";
  const CARD_B = "req-b";

  it("stays empty while a card's people are still loading", () => {
    const state = nextFrozen(INITIAL_FROZEN_STATE, CARD_A, []);
    expect(frozenFieldKeys(state.frozen, "p1")).toEqual([]);
  });

  it("seeds when people arrive a render later, as resolvePeopleMatches makes them", () => {
    const loading = nextFrozen(INITIAL_FROZEN_STATE, CARD_A, []);
    const seeded = nextFrozen(loading, CARD_A, [card("p1", surviving("name", FieldReason.DIFF))]);
    expect(frozenFieldKeys(seeded.frozen, "p1")).toEqual(["name"]);
  });

  it("seeding late matches seeding directly — which is why no arming step is needed", () => {
    const cards = [card("p1", surviving("name", FieldReason.DIFF), surviving("emails", FieldReason.DIFF))];
    const late = nextFrozen(nextFrozen(INITIAL_FROZEN_STATE, CARD_A, []), CARD_A, cards);
    const direct = nextFrozen(INITIAL_FROZEN_STATE, CARD_A, cards);
    expect(frozenFieldKeys(late.frozen, "p1")).toEqual(frozenFieldKeys(direct.frozen, "p1"));
  });

  it("grows within a card as fields surface", () => {
    const seeded = nextFrozen(INITIAL_FROZEN_STATE, CARD_A, [card("p1", surviving("name", FieldReason.DIFF))]);
    const grown = nextFrozen(seeded, CARD_A, [
      card("p1", surviving("name", FieldReason.DIFF), surviving("end_date", FieldReason.ERROR)),
    ]);
    expect(frozenFieldKeys(grown.frozen, "p1")).toEqual(["name", "end_date"]);
  });

  it("returns the same state reference when nothing changed", () => {
    const seeded = nextFrozen(INITIAL_FROZEN_STATE, CARD_A, [card("p1", surviving("name", FieldReason.DIFF))]);
    expect(nextFrozen(seeded, CARD_A, [card("p1", surviving("name", FieldReason.DIFF))])).toBe(seeded);
  });

  it("starts over on a new card — advancing IS a new load", () => {
    const seeded = nextFrozen(INITIAL_FROZEN_STATE, CARD_A, [card("p1", surviving("name", FieldReason.DIFF))]);
    const next = nextFrozen(seeded, CARD_B, [card("p2", surviving("emails", FieldReason.DIFF))]);
    expect(frozenFieldKeys(next.frozen, "p1")).toEqual([]);
    expect(frozenFieldKeys(next.frozen, "p2")).toEqual(["emails"]);
  });

  it("does not carry a previous card's freeze into one that is still loading", () => {
    const seeded = nextFrozen(INITIAL_FROZEN_STATE, CARD_A, [card("p1", surviving("name", FieldReason.DIFF))]);
    const loading = nextFrozen(seeded, CARD_B, []);
    expect(frozenFieldKeys(loading.frozen, "p1")).toEqual([]);
    expect(loading.changesetId).toBe(CARD_B);
  });
});

describe("pruneToLiving", () => {
  const frozen = foldVisible(EMPTY_FROZEN, [
    card("p1", surviving("name", FieldReason.DIFF)),
    card("p2", surviving("emails", FieldReason.DIFF)),
  ]);

  it("drops a person who left the card", () => {
    const next = pruneToLiving(frozen, new Set(["p1"]));
    expect(frozenFieldKeys(next, "p1")).toEqual(["name"]);
    expect(frozenFieldKeys(next, "p2")).toEqual([]);
  });

  it("returns the same reference when everyone is still there", () => {
    expect(pruneToLiving(frozen, new Set(["p1", "p2"]))).toBe(frozen);
  });
});

describe("nextFrozen prunes absorbed people", () => {
  const CARD = "req-merge";

  // A merge collapses two rows into one. The absorbed id keeps no entry, so it
  // cannot resurrect with stale reasons if that id is ever reused.
  it("drops the absorbed person's frozen set", () => {
    const before = nextFrozen(INITIAL_FROZEN_STATE, CARD, [
      card("survivor", surviving("name", FieldReason.DIFF)),
      card("absorbed", surviving("emails", FieldReason.DIFF)),
    ]);
    const after = nextFrozen(before, CARD, [card("survivor", surviving("name", FieldReason.DIFF))]);
    expect(frozenFieldKeys(after.frozen, "absorbed")).toEqual([]);
    expect(frozenFieldKeys(after.frozen, "survivor")).toEqual(["name"]);
  });

  // The async gap: an empty list means the people have not arrived, not that
  // everyone left, so it must not wipe what is already frozen.
  it("keeps everyone while the card is reloading", () => {
    const seeded = nextFrozen(INITIAL_FROZEN_STATE, CARD, [
      card("p1", surviving("name", FieldReason.DIFF)),
    ]);
    const reloading = nextFrozen(seeded, CARD, []);
    expect(frozenFieldKeys(reloading.frozen, "p1")).toEqual(["name"]);
  });
});
