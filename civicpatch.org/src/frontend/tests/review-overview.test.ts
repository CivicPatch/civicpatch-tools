import { describe, it, expect } from "vitest";
import {
  attentionOf,
  byRank,
  runsOf,
  sourceMapFor,
  visibleFields,
} from "../components/review-overview/overview-model.js";
import {
  PersonStatus,
  type PersonStatusKey,
  type ReviewCard,
} from "../components/review/review-cards.js";
import { FIELD_SCHEMA, type SurvivingField } from "../components/review/field-model.js";

const spec = (key: string) => {
  const found = FIELD_SCHEMA.find((field) => field.key === key);
  if (!found) throw new Error(`no such field: ${key}`);
  return found;
};

// `reason` is derived from `error` in survivingFields, never set independently —
// so the fixture derives it too. An errored field with reason "diff" cannot exist.
const surviving = (
  key: string,
  over: Partial<SurvivingField> = {},
): SurvivingField => {
  const base: SurvivingField = {
    field: spec(key),
    state: "changed",
    reason: "diff",
    error: null,
    ...over,
  };
  return base.error ? { ...base, reason: "error" } : base;
};

const card = (over: Partial<ReviewCard> = {}): ReviewCard =>
  ({
    personId: "p",
    status: PersonStatus.CHANGED,
    oldRecord: null,
    newRecord: null,
    surviving: [],
    issues: [],
    ...over,
  }) as ReviewCard;

describe("byRank — what a reviewer sees first", () => {
  it("puts an error ahead of an issue, and both ahead of a plain diff", () => {
    const ordered = [
      surviving("emails", { reason: "diff" }),
      surviving("phones", { reason: "issue" }),
      surviving("urls", { error: "bad" }),
    ]
      .sort(byRank)
      .map((field) => field.field.key);

    expect(ordered).toEqual(["urls", "phones", "emails"]);
  });

  it("ranks office and division ahead of contact details, and both ahead of name", () => {
    const ordered = [
      surviving("name"),
      surviving("emails"),
      surviving("office.division_ocdid"),
      surviving("office.name"),
    ]
      .sort(byRank)
      .map((field) => field.field.key);

    expect(ordered).toEqual([
      "office.name",
      "office.division_ocdid",
      "emails",
      "name",
    ]);
  });

  it("an error on a low-ranked field still outranks a clean high-ranked one", () => {
    const ordered = [
      surviving("office.name"),
      surviving("image", { error: "missing" }),
    ]
      .sort(byRank)
      .map((field) => field.field.key);

    expect(ordered).toEqual(["image", "office.name"]);
  });
});

describe("attentionOf — the second axis", () => {
  it("reports an error over an issue, because an error blocks publishing", () => {
    expect(
      attentionOf(
        card({
          surviving: [
            surviving("emails", { reason: "issue" }),
            surviving("phones", { error: "bad" }),
          ],
        }),
      ),
    ).toBe("error");
  });

  it("is null when nothing needs a person", () => {
    expect(attentionOf(card({ surviving: [surviving("emails")] }))).toBeNull();
  });

  // The case that lets the tint follow status alone: an untouched person can still
  // carry an issue, and the chip is what surfaces it.
  it("still reports an issue on a card with no changes", () => {
    expect(
      attentionOf(
        card({
          status: PersonStatus.UNCHANGED,
          surviving: [surviving("emails", { state: "same", reason: "issue" })],
        }),
      ),
    ).toBe("issue");
  });
});

describe("runsOf — folding without losing seat order", () => {
  const at = (status: PersonStatusKey, id: string) =>
    card({ personId: id, status });

  it("collapses consecutive untouched people into one run", () => {
    const runs = runsOf([
      at(PersonStatus.CHANGED, "a"),
      at(PersonStatus.UNCHANGED, "b"),
      at(PersonStatus.UNCHANGED, "c"),
      at(PersonStatus.ADDED, "d"),
    ]);

    expect(runs.map((run) => [run.folded, run.cards.map((c) => c.personId)])).toEqual([
      [false, ["a"]],
      [true, ["b", "c"]],
      [false, ["d"]],
    ]);
  });

  it("gives a separate run to each gap, so position is never rearranged", () => {
    const runs = runsOf([
      at(PersonStatus.UNCHANGED, "a"),
      at(PersonStatus.CHANGED, "b"),
      at(PersonStatus.UNCHANGED, "c"),
    ]);

    expect(runs).toHaveLength(3);
    expect(runs.flatMap((run) => run.cards.map((c) => c.personId))).toEqual([
      "a",
      "b",
      "c",
    ]);
  });

  it("folds only `unchanged` — a departure is a decision and keeps its card", () => {
    const runs = runsOf([
      at(PersonStatus.REMOVED, "a"),
      at(PersonStatus.DELETED, "b"),
      at(PersonStatus.RESTORED, "c"),
    ]);

    expect(runs.every((run) => !run.folded)).toBe(true);
  });
});

describe("sourceMapFor — a url keeps its number everywhere", () => {
  const withSources = (id: string, urls: string[]) =>
    card({ personId: id, newRecord: { source_urls: urls } as never });

  it("numbers by first appearance across the whole card, not per person", () => {
    const map = sourceMapFor([
      withSources("a", ["one.gov", "two.gov"]),
      withSources("b", ["two.gov", "three.gov"]),
    ]);

    expect(map.get("one.gov")?.number).toBe(1);
    expect(map.get("two.gov")?.number).toBe(2);
    expect(map.get("three.gov")?.number).toBe(3);
  });

  it("gives the same url the same colour on every person citing it", () => {
    const map = sourceMapFor([
      withSources("a", ["shared.gov"]),
      withSources("b", ["other.gov", "shared.gov"]),
    ]);

    expect(map.get("shared.gov")?.colorClass).toBe("color-1");
    expect(map.get("other.gov")?.colorClass).toBe("color-2");
  });

  it("ignores a person the scrape lost, who has no new-side record", () => {
    const map = sourceMapFor([
      card({ personId: "gone", status: PersonStatus.REMOVED, newRecord: null }),
      withSources("a", ["one.gov"]),
    ]);

    expect(map.get("one.gov")?.number).toBe(1);
    expect(map.size).toBe(1);
  });
});

describe("visibleFields — what the card shows is what it opens", () => {
  it("drops context fields and ranks the rest", () => {
    const shown = visibleFields(
      card({
        surviving: [
          surviving("source_urls", { state: "same", reason: "context" }),
          surviving("end_date"),
          surviving("phones"),
        ],
      }),
    ).map((field) => field.field.key);

    // Schema order would give end_date first; the card leads with phones, so
    // opening it must focus phones too.
    expect(shown).toEqual(["phones", "end_date"]);
  });
});
