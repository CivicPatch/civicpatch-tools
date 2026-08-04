import { describe, it, expect } from "vitest";
import {
  buildReviewCards,
  cardFields,
  needsReview,
  publishSet,
  blockingErrors,
  bySeat,
  PersonStatus,
} from "../components/review/review-cards.js";
import { type Issue } from "../components/review/field-model.js";

const DIVISION = "ocd-division/country:us/state:nh/place:concord/ward:1";

// Division is required, so a record without one surfaces an `error` on every
// card and drowns out what each test is actually asserting. Real records always
// carry one — resolve_division is typed `-> str` and always returns a division.
const person = (id: string, over: Record<string, unknown> = {}) => ({
  id,
  name: `Person ${id}`,
  office: { name: "Council Member", division_ocdid: DIVISION },
  emails: [],
  phones: [],
  urls: [],
  other_names: [],
  ...over,
});

const build = (over: Partial<Parameters<typeof buildReviewCards>[0]> = {}) =>
  buildReviewCards({
    existing: [],
    currentPeople: [],
    removedIds: new Set(),
    restoredIds: new Set(),
    issues: [],
    ...over,
  });

const statuses = (cards: { personId: string; status: string }[]) =>
  cards.map((c) => [c.personId, c.status]);

describe("buildReviewCards — status", () => {
  it("classifies changed, added, removed and unchanged", () => {
    const cards = build({
      existing: [person("a"), person("b"), person("d")],
      currentPeople: [
        person("a", { office: { name: "Mayor", division_ocdid: DIVISION } }),
        person("b"),
        person("c"),
      ],
    });
    expect(statuses(cards)).toEqual([
      ["a", PersonStatus.CHANGED],
      ["b", PersonStatus.UNCHANGED],
      ["c", PersonStatus.ADDED],
      ["d", PersonStatus.REMOVED],
    ]);
  });

  it("names the reviewer as the actor when they removed someone", () => {
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a")],
      removedIds: new Set(["a"]),
    });
    // The scrape found them; the reviewer dropped them. §11.3 keeps the two
    // departures distinct in state even though both read alike on screen.
    expect(statuses(cards)).toEqual([["a", PersonStatus.DELETED]]);
  });

  it("keeps a card for an added person the reviewer deleted", () => {
    const cards = build({ currentPeople: [person("c")], removedIds: new Set(["c"]) });
    expect(statuses(cards)).toEqual([["c", PersonStatus.DELETED]]);
  });

  it("marks someone restored, who would otherwise read as unchanged", () => {
    // Restoring copies the old record into the list, so both sides compare
    // identical — this is the case restoredIds exists for.
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a")],
      restoredIds: new Set(["a"]),
    });
    expect(statuses(cards)).toEqual([["a", PersonStatus.RESTORED]]);
  });

  it("prefers restored over deleted when an id is somehow in both", () => {
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a")],
      removedIds: new Set(["a"]),
      restoredIds: new Set(["a"]),
    });
    expect(statuses(cards)).toEqual([["a", PersonStatus.RESTORED]]);
  });
});

describe("buildReviewCards — records", () => {
  it("gives a scrape-dropped person no new record, so their fields read as cleared", () => {
    const cards = build({ existing: [person("a")], currentPeople: [] });
    expect(cards[0].newRecord).toBeNull();
    expect(cards[0].oldRecord).toBeTruthy();
  });

  it("gives an added person no old record", () => {
    const cards = build({ currentPeople: [person("c")] });
    expect(cards[0].oldRecord).toBeNull();
  });

  // A reviewer removal is a decision about a row that is still in the list, so
  // the record has to survive it — with no old side to fall back on, nulling the
  // new one would leave an unnamed card nobody could identify or restore.
  it("keeps the record of an added person the reviewer deleted", () => {
    const cards = build({ currentPeople: [person("c")], removedIds: new Set(["c"]) });
    expect(cards[0].newRecord).toMatchObject({ id: "c", name: "Person c" });
  });

  it("still clears the new record when the scrape dropped someone the reviewer did not", () => {
    const cards = build({ existing: [person("a")], currentPeople: [] });
    expect(cards[0].status).toBe(PersonStatus.REMOVED);
    expect(cards[0].newRecord).toBeNull();
  });
});

describe("buildReviewCards — order", () => {
  it("keeps each card in its currentPeople slot, so editing never re-sorts", () => {
    const cards = build({
      existing: [person("a"), person("b")],
      currentPeople: [person("b"), person("a")],
    });
    expect(cards.map((c) => c.personId)).toEqual(["b", "a"]);
  });

  it("trails people the scrape dropped, who have no slot", () => {
    const cards = build({
      existing: [person("gone"), person("a")],
      currentPeople: [person("a")],
    });
    expect(cards.map((c) => c.personId)).toEqual(["a", "gone"]);
  });
});

describe("buildReviewCards — surviving fields and issues", () => {
  it("collapses an unchanged person to nothing", () => {
    const cards = build({ existing: [person("a")], currentPeople: [person("a")] });
    // source_urls is always visible, so an unchanged person collapses to it alone.
    expect(cards[0].surviving.map((s) => s.field.key)).toEqual(["source_urls"]);
  });

  it("surfaces only what changed", () => {
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a", { emails: ["x@y.gov"] })],
    });
    expect(cards[0].surviving.map((s) => s.field.key)).toEqual(["emails", "source_urls"]);
  });

  it("anchors an issue to its person and keeps its field visible", () => {
    const issue: Issue = {
      code: "duplicate_unique_role",
      message: "…",
      person_ids: ["a"],
      field: "office.name",
    };
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a")],
      issues: [issue],
    });
    expect(cards[0].issues).toEqual([issue]);
    expect(cards[0].surviving.map((s) => [s.field.key, s.reason])).toEqual([
      ["office.name", "issue"],
      ["source_urls", "context"],
    ]);
  });

  it("does not give one person's issue to another", () => {
    const issue: Issue = { code: "extra_official", message: "…", person_ids: ["a"] };
    const cards = build({
      existing: [person("a"), person("b")],
      currentPeople: [person("a"), person("b")],
      issues: [issue],
    });
    expect(cards.find((c) => c.personId === "b")!.issues).toEqual([]);
  });
});

describe("cardFields", () => {
  it("reduces cards to what the freeze folds", () => {
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a", { emails: ["x@y.gov"] })],
    });
    expect(cardFields(cards)).toEqual([
      { personId: "a", surviving: cards[0].surviving },
    ]);
  });
});

describe("needsReview", () => {
  const changed = (id: string) => ({
    existing: [person(id)],
    currentPeople: [person(id, { emails: ["x@y.gov"] })],
  });

  const only = (cards: ReturnType<typeof build>) => cards[0];

  it("is true for a person with surviving fields", () => {
    expect(needsReview(only(build(changed("a"))))).toBe(true);
  });

  it("is false for an untouched person", () => {
    const cards = build({ existing: [person("a")], currentPeople: [person("a")] });
    expect(needsReview(only(cards))).toBe(false);
  });

  it("is true for a person carrying only a row-level issue", () => {
    // No field moved and nothing is deleted — the issue is the whole reason.
    const issue: Issue = { code: "extra_official", message: "…", person_ids: ["a"] };
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a")],
      issues: [issue],
    });
    expect(needsReview(only(cards))).toBe(true);
  });

  it("is true for a person who is only deleted — the one decision on the card", () => {
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a")],
      removedIds: new Set(["a"]),
    });
    expect(needsReview(only(cards))).toBe(true);
  });
});

describe("publishSet / blockingErrors", () => {
  it("is everyone with a record, minus those the reviewer dropped", () => {
    const cards = build({
      existing: [person("a"), person("gone")],
      currentPeople: [person("a"), person("b")],
      removedIds: new Set(["b"]),
    });
    // `gone` has no new-side record so is already absent; `b` was dropped.
    expect(publishSet(cards).map((c) => c.personId)).toEqual(["a"]);
  });

  it("includes someone restored — they have a record again", () => {
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a")],
      restoredIds: new Set(["a"]),
    });
    expect(publishSet(cards).map((c) => c.personId)).toEqual(["a"]);
  });

  it("finds nothing wrong with a complete record", () => {
    const cards = build({ existing: [person("a")], currentPeople: [person("a")] });
    expect(blockingErrors(cards)).toEqual([]);
  });

  it("reports a required field even though the collapse rule may hide it", () => {
    // This is the whole point of scanning the schema rather than the visible
    // rows: a hidden field can still block publishing (§9).
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a", { name: "" })],
    });
    expect(blockingErrors(cards).map((e) => [e.fieldLabel, e.message])).toEqual([
      ["Name", "Required"],
    ]);
  });

  it("ignores errors on someone being dropped", () => {
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a", { name: "" })],
      removedIds: new Set(["a"]),
    });
    expect(blockingErrors(cards)).toEqual([]);
  });

  it("names the person, so the reviewer knows where to go", () => {
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a", { name: "", office: { name: "", division_ocdid: DIVISION } })],
    });
    expect(blockingErrors(cards).map((e) => e.name)).toEqual(["(unnamed)", "(unnamed)"]);
  });
});

describe("bySeat", () => {
  const AT_LARGE = "ocd-division/country:us/state:nh/place:concord";
  const ward = (n: number) => `${AT_LARGE}/ward:${n}`;
  const JURIS = "ocd-jurisdiction/country:us/state:nh/place:concord/government";

  it("puts at-large first, then wards in numeric order", () => {
    const cards = build({
      currentPeople: [
        person("w10", { office: { name: "Council", division_ocdid: ward(10) } }),
        person("w2", { office: { name: "Council", division_ocdid: ward(2) } }),
        person("mayor", { office: { name: "Mayor", division_ocdid: AT_LARGE } }),
      ],
    });
    // Numeric, not lexical — ward 2 before ward 10.
    expect(bySeat(cards, JURIS).map((c) => c.personId)).toEqual(["mayor", "w2", "w10"]);
  });
});
