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
  type PersonCard,
} from "../components/people/person-cards.js";
import { FIELD_SCHEMA, type SurvivingField } from "../components/fields/field-model.js";
import { cardSubtitle, proposalsByPersonId } from "../components/people/person-cards.js";

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

const card = (over: Partial<PersonCard> = {}): PersonCard =>
  ({
    personId: "p",
    status: PersonStatus.CHANGED,
    oldRecord: null,
    newRecord: null,
    surviving: [],
    issues: [],
    ...over,
  }) as PersonCard;

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

  it("ranks the office ahead of contact details, and both ahead of name", () => {
    const ordered = [
      surviving("name"),
      surviving("emails"),
          ]
      .sort(byRank)
      .map((field) => field.field.key);

    expect(ordered).toEqual(["emails", "name"]);
  });

  it("an error on a low-ranked field still outranks a clean high-ranked one", () => {
    const ordered = [
            surviving("image", { error: "missing" }),
    ]
      .sort(byRank)
      .map((field) => field.field.key);

    expect(ordered).toEqual(["image"]);
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

describe("cardSubtitle — where a person serves", () => {
  const card = (over = {}) => ({
    personId: "p1",
    status: "changed",
    oldRecord: null,
    newRecord: { id: "p1", name: "A" },
    surviving: [],
    issues: [],
    ...over,
  }) as never;

  it("names the proposed post, because a proposed person holds no membership yet", () => {
    const proposals = proposalsByPersonId([
      {
        person_id: "p1",
        disposition: "new",
        role_id: "council-member",
        role_label: "Council Member",
        division_ocdid: "ocd-division/country:us/state:wa/place:x/council_district:5",
        label: null,
      },
    ]);

    // The role's label, not its slug: an id is storage.
    expect(cardSubtitle(card(), proposals)).toBe("Council Member, District 5");
  });

  it("appends the membership label after the post", () => {
    const proposals = proposalsByPersonId([
      {
        person_id: "p1",
        disposition: "new",
        role_id: "council-member",
        role_label: "Council Member",
        division_ocdid: "ocd-division/country:us/state:wa/place:x",
        label: "Seat 3",
      },
    ]);

    expect(cardSubtitle(card(), proposals)).toBe("Council Member, At-Large, Seat 3");
  });

  it("falls back to a published person's memberships when nothing is proposed", () =>
    expect(
      cardSubtitle(
        card({
          newRecord: {
            id: "p1",
            name: "A",
            memberships: [
              {
                post_id: "x",
                role_id: "mayor",
                division_ocdid: "ocd-division/country:us/state:wa/place:x",
                label: null,
                post_label: "Mayor",
                role_label: "Mayor",
                source_labels: ["Mayor"],
              },
            ],
          },
        }),
        proposalsByPersonId([]),
      ),
    ).toBe("Mayor"));

  it("says nothing rather than repeating the joined office string", () =>
    // `office.name` remains the last resort only until the review surfaces stop being sent it.
    expect(cardSubtitle(card(), proposalsByPersonId([]))).toBe(""));
});

describe("proposalsByPersonId", () => {
  const change = (over = {}) => ({
    person_id: "p1",
    disposition: "new",
    role_id: "council-member",
    role_label: "Council Member",
    division_ocdid: "ocd-division/country:us/state:wa/place:x",
    label: null,
    ...over,
  });

  it("keeps every proposal for a person, not just the last", () => {
    // A plain Map keyed on person_id dropped all but one, so anyone proposed onto two posts
    // showed one of them at random.
    const byPerson = proposalsByPersonId([
      change({ role_id: "mayor", role_label: "Mayor" }),
      change({ role_id: "council-member" }),
    ]);
    expect(byPerson.get("p1")).toHaveLength(2);
  });

  it("has no entry for a person nothing was proposed for", () =>
    expect(proposalsByPersonId([]).get("p1")).toBeUndefined());
});
