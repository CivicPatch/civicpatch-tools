import { describe, it, expect } from "vitest";
import {
  buildReviewCards,
  cardFields,
  groupCards,
  RailStatus,
} from "../components/review/review-cards.js";
import { type Issue } from "../components/people-diff/diff-model.js";

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
    deletedIds: new Set(),
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
      ["a", RailStatus.CHANGED],
      ["b", RailStatus.UNCHANGED],
      ["c", RailStatus.ADDED],
      ["d", RailStatus.REMOVED],
    ]);
  });

  it("names the reviewer as the actor when they removed someone", () => {
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a")],
      deletedIds: new Set(["a"]),
    });
    // The scrape found them; the reviewer dropped them. §11.3 keeps the two
    // departures distinct in state even though both read alike on screen.
    expect(statuses(cards)).toEqual([["a", RailStatus.DELETED]]);
  });

  it("drops an added person the reviewer deleted — a net no-op", () => {
    const cards = build({ currentPeople: [person("c")], deletedIds: new Set(["c"]) });
    expect(cards).toEqual([]);
  });

  it("marks someone restored, who would otherwise read as unchanged", () => {
    // Restoring copies the old record into the list, so both sides compare
    // identical — this is the case restoredIds exists for.
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a")],
      restoredIds: new Set(["a"]),
    });
    expect(statuses(cards)).toEqual([["a", RailStatus.RESTORED]]);
  });

  it("prefers restored over deleted when an id is somehow in both", () => {
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a")],
      deletedIds: new Set(["a"]),
      restoredIds: new Set(["a"]),
    });
    expect(statuses(cards)).toEqual([["a", RailStatus.RESTORED]]);
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
    expect(cards[0].surviving).toEqual([]);
  });

  it("surfaces only what changed", () => {
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a", { emails: ["x@y.gov"] })],
    });
    expect(cards[0].surviving.map((s) => s.field.key)).toEqual(["emails"]);
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

describe("needsReview / groupCards", () => {
  const changed = (id: string) => ({
    existing: [person(id)],
    currentPeople: [person(id, { emails: ["x@y.gov"] })],
  });

  it("puts a person with surviving fields in To review", () => {
    const { toReview, unchanged } = groupCards(build(changed("a")));
    expect(toReview.map((c) => c.personId)).toEqual(["a"]);
    expect(unchanged).toEqual([]);
  });

  it("puts an untouched person in Unchanged", () => {
    const cards = build({ existing: [person("a")], currentPeople: [person("a")] });
    const { toReview, unchanged } = groupCards(cards);
    expect(toReview).toEqual([]);
    expect(unchanged.map((c) => c.personId)).toEqual(["a"]);
  });

  it("puts a person carrying only a row-level issue in To review", () => {
    // No field moved and nothing is deleted — the issue is the whole reason.
    const issue: Issue = { code: "extra_official", message: "…", person_ids: ["a"] };
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a")],
      issues: [issue],
    });
    expect(groupCards(cards).toReview.map((c) => c.personId)).toEqual(["a"]);
  });

  it("puts a person who is only deleted in To review — the one decision on the card", () => {
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a")],
      deletedIds: new Set(["a"]),
    });
    expect(groupCards(cards).toReview.map((c) => c.personId)).toEqual(["a"]);
  });

  it("orders by status: changed, added, unchanged, removed", () => {
    const cards = build({
      existing: [person("gone"), person("same"), person("chg")],
      currentPeople: [
        person("same"),
        person("chg", { emails: ["x@y.gov"] }),
        person("new"),
      ],
    });
    const { toReview, unchanged } = groupCards(cards);
    expect(toReview.map((c) => c.personId)).toEqual(["chg", "new", "gone"]);
    expect(unchanged.map((c) => c.personId)).toEqual(["same"]);
  });

  it("puts issue-carrying cards first within their bucket", () => {
    const issue: Issue = { code: "extra_official", message: "…", person_ids: ["b"] };
    const cards = build({
      existing: [person("a"), person("b")],
      currentPeople: [
        person("a", { emails: ["a@y.gov"] }),
        person("b", { emails: ["b@y.gov"] }),
      ],
      issues: [issue],
    });
    // Both changed; b carries the issue, so b leads.
    expect(groupCards(cards).toReview.map((c) => c.personId)).toEqual(["b", "a"]);
  });
});
