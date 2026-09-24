import { describe, it, expect } from "vitest";
import {
  cardKey,
  personIdIn,
  buildPersonCards,
  postsFor,
  postNameFor,
  membershipLabelFor,
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

describe("buildPersonCards — office visibility", () => {
  // `post_id` is never a raw scraped value, so a plain field diff never surfaces it — these
  // lock down the cases `officeSurvivingField` adds it back for. These read the proposed
  // record's own memberships since 2026-09-23; they read a separate `ProposedChange` before,
  // because the post did not exist yet and only the derivation could name it.
  const office = (over: Record<string, unknown> = {}) => ({
    post_id: "post-1",
    organization_id: "org-1",
    role_id: "council-member",
    role_label: "Council Member",
    post_label: "Council Member",
    label: "Council Member",
    ...over,
  });
  const officeKeys = (cards: ReturnType<typeof buildPersonCards>) =>
    cards[0].surviving.filter((s) => s.field.key === "post_id").map((s) => s.reason);
  const officeStates = (cards: ReturnType<typeof buildPersonCards>) =>
    cards[0].surviving.filter((s) => s.field.key === "post_id").map((s) => s.state);

  it("surfaces a first appearance, which a field diff has nothing to compare", () => {
    const cards = build({
      currentPeople: [person("a", { memberships: [office()] })],
    });
    expect(officeKeys(cards)).toEqual(["diff"]);
    // Matches every other field on a brand-new person, which reads "added" too — not
    // "changed", which would read as a modification to something that already existed.
    expect(officeStates(cards)).toEqual(["added"]);
  });

  it("surfaces a move the same way", () => {
    const cards = build({
      existing: [person("a", { memberships: [{ post_id: "old", label: "Mayor" }] })],
      currentPeople: [person("a", { memberships: [office()] })],
    });
    expect(officeKeys(cards)).toEqual(["diff"]);
    expect(officeStates(cards)).toEqual(["changed"]);
  });

  it("surfaces a recomposed label even though the seat did not move", () => {
    const cards = build({
      existing: [
        person("a", { memberships: [
          { post_id: "post-1", label: "Council Member", organization_id: "org-1" },
        ] }),
      ],
      currentPeople: [
        person("a", { memberships: [office({ label: "Council Member, Deputy" })] }),
      ],
    });
    expect(officeKeys(cards)).toEqual(["diff"]);
    expect(officeStates(cards)).toEqual(["changed"]);
  });

  it("stays quiet when the seat and the label both match what was held", () => {
    const cards = build({
      existing: [
        person("a", { memberships: [
          { post_id: "post-1", label: "Council Member", organization_id: "org-1" },
        ] }),
      ],
      currentPeople: [person("a", { memberships: [office()] })],
    });
    expect(officeKeys(cards)).toEqual([]);
  });

  it("stays quiet when nobody holds an office at all, the jurisdiction page's case", () => {
    const cards = build({
      existing: [person("a")],
      currentPeople: [person("a")],
    });
    expect(officeKeys(cards)).toEqual([]);
  });

  it("does not double up when an issue already anchored post_id", () => {
    const issue: Issue = {
      code: "moved_person",
      message: "…",
      person_ids: ["a"],
      field: "post_id",
    };
    const cards = build({
      existing: [person("a", { memberships: [{ post_id: "old", label: "Mayor" }] })],
      currentPeople: [person("a", { memberships: [office()] })],
      issues: [issue],
    });
    expect(officeKeys(cards)).toEqual(["issue"]);
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
  it("prefers the reviewer's own post_id pick over the memberships", () => {
    const posts = [{ id: "post-1", label: "Council President" }] as never;
    expect(
      postsFor(
        card({
          post_id: "post-1",
          memberships: [{ post_label: "Council Member", label: null }],
        }),
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
        posts,
      ),
    ).toBe("Council Member");
  });
  it("composes the post's own name with the membership's own label", () => {
    expect(
      postsFor(
        card({
          memberships: [{ post_label: "Council Member, District 5", label: "Chair" }],
        }),
      ),
    ).toBe("Council Member, District 5, Chair");
  });
});

describe("postNameFor / membershipLabelFor — the two split apart", () => {
  const card = (record: Record<string, unknown>) =>
    ({ personId: "p1", newRecord: record, oldRecord: null }) as never;
  it("postNameFor is just the post, never the membership's own label", () => {
    expect(
      postNameFor(
        card({
          memberships: [{ post_label: "Council Member, District 5", label: "Chair" }],
        }),
      ),
    ).toBe("Council Member, District 5");
  });
  it("membershipLabelFor is just what the occupant's own labels added", () => {
    expect(
      membershipLabelFor(
        card({
          memberships: [{ post_label: "Council Member, District 5", label: "Chair" }],
        }),
      ),
    ).toBe("Chair");
  });
  it("membershipLabelFor is empty once a reviewer has picked a post — that pick names no label", () => {
    expect(
      membershipLabelFor(
        card({
          post_id: "post-1",
          memberships: [{ post_label: "Council Member", label: "Chair" }],
        }),
      ),
    ).toBe("");
  });
});

describe("cardKey", () => {
  it("names the person alone when no body is in play", () => {
    // A review card is one person: the scrape either found them or it did not.
    expect(cardKey({ personId: "p1" })).toBe("p1");
  });

  it("names the person in the body for a roster row", () => {
    expect(cardKey({ personId: "p1", organizationId: "org-council" })).toBe("p1:org-council");
  });

  it("reads back whom a key is about, either way", () => {
    expect(personIdIn("p1:org-council")).toBe("p1");
    expect(personIdIn("p1")).toBe("p1");
  });
});
