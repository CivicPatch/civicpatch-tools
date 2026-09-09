import { describe, it, expect } from "vitest";
import {
  buildPersonCards,
  postsFor,
  cardFields,
  needsReview,
  publishSet,
  blockingErrors,
  byDivision,
  PersonStatus,
} from "../components/people/person-cards.js";
import { isContextField, type Issue } from "../components/fields/field-model.js";

const person = (id: string, over: Record<string, unknown> = {}) => ({
  id,
  name: `Person ${id}`,
    emails: [],
  phones: [],
  urls: [],
  other_names: [],
  source_urls: ["https://x.gov/council"],
  ...over,
});

const build = (over: Partial<Parameters<typeof buildPersonCards>[0]> = {}) =>
  buildPersonCards({
    existing: [],
    currentPeople: [],
    removedIds: new Set(),
    restoredIds: new Set(),
    issues: [],
    ...over,
  });

const statuses = (cards: { personId: string; status: string }[]) =>
  cards.map((c) => [c.personId, c.status]);

describe("buildPersonCards — status", () => {
  it("classifies changed, added, removed and unchanged", () => {
    const cards = build({
      existing: [person("a"), person("b"), person("d")],
      currentPeople: [
        person("a", { start_date: "2030" }),
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
    expect(statuses(cards)).toEqual([["a", PersonStatus.DELETED]]);
  });
  it("keeps a card for an added person the reviewer deleted", () => {
    const cards = build({ currentPeople: [person("c")], removedIds: new Set(["c"]) });
    expect(statuses(cards)).toEqual([["c", PersonStatus.DELETED]]);
  });
  it("marks someone restored, who would otherwise read as unchanged", () => {
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

describe("buildPersonCards — records", () => {
  it("gives a scrape-dropped person no new record, so their fields read as cleared", () => {
    const cards = build({ existing: [person("a")], currentPeople: [] });
    expect(cards[0].newRecord).toBeNull();
    expect(cards[0].oldRecord).toBeTruthy();
  });
  it("gives an added person no old record", () => {
    const cards = build({ currentPeople: [person("c")] });
    expect(cards[0].oldRecord).toBeNull();
  });
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

describe("buildPersonCards — order", () => {
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

describe("buildPersonCards — surviving fields and issues", () => {
  it("collapses an unchanged person to nothing", () => {
    const cards = build({ existing: [person("a")], currentPeople: [person("a")] });
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
      field: "post_id" };
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a")],
      issues: [issue],
    });
    expect(cards[0].issues).toEqual([issue]);
    expect(cards[0].surviving.map((s) => [s.field.key, s.reason])).toEqual([
      ["post_id", "issue"],
      ["source_urls", "context"],
    ]);
  });
  it("does not give one person's issue to another", () => {
    const issue: Issue = { code: "new_person", message: "…", person_ids: ["a"] };
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
  it("is true when only a context field is in error", () => {
    const noSources = { existing: [person("a", { source_urls: [] })], currentPeople: [person("a", { source_urls: [] })] };
    const card = only(build(noSources));
    expect(card.surviving.every((field) => isContextField(field.field))).toBe(true);
    expect(needsReview(card)).toBe(true);
  });
  it("is true for a person carrying only a row-level issue", () => {
    const issue: Issue = { code: "new_person", message: "…", person_ids: ["a"] };
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
      currentPeople: [person("a", { name: "" })],
    });
    expect(blockingErrors(cards).map((e) => e.name)).toEqual(["(unnamed)"]);
  });
});

describe("byDivision", () => {
  const AT_LARGE = "ocd-division/country:us/state:nh/place:concord";
  const ward = (n: number) => `${AT_LARGE}/ward:${n}`;
  const JURIS = "ocd-jurisdiction/country:us/state:nh/place:concord/government";
  const serving = (division_ocdid: string) => ({
    memberships: [{ division_ocdid }],
  });
  it("puts at-large first, then wards in numeric order", () => {
    const cards = build({
      currentPeople: [
        person("w10", serving(ward(10))),
        person("w2", serving(ward(2))),
        person("mayor", serving(AT_LARGE)),
      ],
    });
    expect(byDivision(cards, JURIS).map((c) => c.personId)).toEqual(["mayor", "w2", "w10"]);
  });
});

describe("postsFor — what a card calls the person's post", () => {
  const card = (record: Record<string, unknown>) =>
    ({ personId: "p1", newRecord: record, oldRecord: null }) as never;
  it("falls back to labels, not a joined office name", () => {
    expect(postsFor(card({ labels: ["Mayor", "Council Member"] }))).toBe(
      "Mayor; Council Member",
    );
  });
  it("keeps every spelling a page gave, rather than collapsing them", () => {
    expect(
      postsFor(
        card({
          labels: [
            "Councilmember Position 8",
            "Council Member Position 8",
            "Council Member Position 8 (Citywide)",
          ],
        }),
      ),
    ).toBe(
      "Councilmember Position 8; Council Member Position 8; Council Member Position 8 (Citywide)",
    );
  });
  it("prefers memberships when the person holds one", () => {
    expect(
      postsFor(
        card({
          labels: ["Mayor"],
          memberships: [{ post_label: "Mayor of Alpha", label: null }],
        }),
      ),
    ).toBe("Mayor of Alpha");
  });
  it("is empty when nothing is known", () => {
    expect(postsFor(card({}))).toBe("");
  });
  it("prefers the reviewer's own post_id pick over memberships and proposals", () => {
    const posts = [{ id: "post-1", label: "Council President" }] as never;
    expect(
      postsFor(
        card({
          post_id: "post-1",
          memberships: [{ post_label: "Council Member", label: null }],
        }),
        undefined,
        posts,
      ),
    ).toBe("Council President");
  });
  it("falls through to memberships when the pick doesn't resolve to a known post", () => {
    const posts = [{ id: "post-1", label: "Council President" }] as never;
    expect(
      postsFor(
        card({
          post_id: "not-a-real-post",
          memberships: [{ post_label: "Council Member", label: null }],
        }),
        undefined,
        posts,
      ),
    ).toBe("Council Member");
  });
});
