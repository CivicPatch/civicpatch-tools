import { describe, it, expect } from "vitest";
import {
  attentionOf,
  byRank,
  issueTypesOf,
  runsOf,
  sectionsByOrganization,
  sourceMapFor,
  tallyOf,
  visibleFields,
} from "../components/review-overview/overview-model.js";
import {
  PersonStatus,
  type PersonStatusKey,
  type PersonCard,
} from "../components/people/person-cards.js";
import { FIELD_SCHEMA, type SurvivingField } from "../components/fields/field-model.js";
import { postsFor, proposalsByPersonId } from "../components/people/person-cards.js";

const spec = (key: string) => {
  const found = FIELD_SCHEMA.find((field) => field.key === key);
  if (!found) throw new Error(`no such field: ${key}`);
  return found;
};

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
});

describe("issueTypesOf — what an issue is, in short", () => {
  it("humanizes the issue code for display", () => {
    expect(
      issueTypesOf(card({ issues: [{ code: "unverified_post", message: "" }] })),
    ).toEqual(["unverified post"]);
  });
  it("drops a code the status badge already says, so it isn't shown twice", () => {
    expect(
      issueTypesOf(card({ issues: [{ code: "moved_person", message: "" }] })),
    ).toEqual([]);
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
    expect(shown).toEqual(["phones", "end_date"]);
  });
});

describe("postsFor", () => {
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
        organization_id: "org-1",
        disposition: "new",
        post: {
          id: null,
          role_id: "council-member",
          role_label: "Council Member",
          division_ocdid: "ocd-division/country:us/state:wa/place:x/council_district:5",
          label: "Council Member, District 5",
          meta_is_tracked: true,
        },
        membership_label: null,
        from_post: null,
      },
    ]);
    expect(postsFor(card(), proposals)).toBe("Council Member, District 5");
  });
  it("composes the post label with the membership's own label", () => {
    const proposals = proposalsByPersonId([
      {
        person_id: "p1",
        organization_id: "org-1",
        disposition: "new",
        post: {
          id: null,
          role_id: "council-member",
          role_label: "Council Member",
          division_ocdid: "ocd-division/country:us/state:wa/place:x",
          label: "Council Member, At-Large",
          meta_is_tracked: true,
        },
        membership_label: "Seat 3",
        from_post: null,
      },
    ]);
    expect(postsFor(card(), proposals)).toBe("Council Member, At-Large, Seat 3");
  });
  it("falls back to a published person's memberships when nothing is proposed", () =>
    expect(
      postsFor(
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
    expect(postsFor(card(), proposalsByPersonId([]))).toBe(""));
});

describe("proposalsByPersonId", () => {
  const change = (postOver = {}) => ({
    person_id: "p1",
    organization_id: "org-1",
    disposition: "new" as const,
    post: {
      id: null,
      role_id: "council-member",
      role_label: "Council Member",
      division_ocdid: "ocd-division/country:us/state:wa/place:x",
      label: "Council Member, At-Large",
      meta_is_tracked: true,
      ...postOver,
    },
    membership_label: null,
    from_post: null,
  });
  it("keeps every proposal for a person, not just the last", () => {
    const byPerson = proposalsByPersonId([
      change({ role_id: "mayor", role_label: "Mayor" }),
      change({ role_id: "council-member" }),
    ]);
    expect(byPerson.get("p1")).toHaveLength(2);
  });
  it("has no entry for a person nothing was proposed for", () =>
    expect(proposalsByPersonId([]).get("p1")).toBeUndefined());
});

describe("tallyOf — the roster's shape, at a glance", () => {
  it("counts each status present, never a zero-count entry", () => {
    const cards = [
      card({ status: PersonStatus.ADDED }),
      card({ status: PersonStatus.ADDED }),
      card({ status: PersonStatus.UNCHANGED }),
    ];
    expect(tallyOf(cards)).toEqual([
      { status: PersonStatus.ADDED, label: "added", count: 2 },
      { status: PersonStatus.UNCHANGED, label: "unchanged", count: 1 },
    ]);
  });
  it("orders review-worthy statuses ahead of unchanged", () => {
    const cards = [
      card({ status: PersonStatus.UNCHANGED }),
      card({ status: PersonStatus.RESTORED }),
      card({ status: PersonStatus.DELETED }),
      card({ status: PersonStatus.REMOVED }),
      card({ status: PersonStatus.CHANGED }),
      card({ status: PersonStatus.ADDED }),
    ];
    expect(tallyOf(cards).map((entry) => entry.status)).toEqual([
      PersonStatus.ADDED,
      PersonStatus.CHANGED,
      PersonStatus.REMOVED,
      PersonStatus.DELETED,
      PersonStatus.RESTORED,
      PersonStatus.UNCHANGED,
    ]);
  });
  it("is empty for an empty roster", () => expect(tallyOf([])).toEqual([]));
});

describe("sectionsByOrganization — a section per organization, roles inside it", () => {
  const roleOrder = ["mayor", "council-member"];
  const proposedIn = (
    personId: string,
    organizationId: string,
    roleId: string,
    roleLabel = roleId,
  ) => ({
    person_id: personId,
    organization_id: organizationId,
    disposition: "unchanged" as const,
    post: {
      id: null,
      role_id: roleId,
      role_label: roleLabel,
      division_ocdid: "ocd-division/country:us/state:wa/place:x",
      label: roleLabel,
      meta_is_tracked: true,
    },
    membership_label: null,
    from_post: null,
  });

  it("lists a person once per organization they were proposed in", () => {
    const ana = card({ personId: "ana" });
    const { organizations } = sectionsByOrganization(
      [ana],
      proposalsByPersonId([
        proposedIn("ana", "council", "council-member", "Council Member"),
        proposedIn("ana", "mayors-office", "mayor", "Mayor"),
      ]),
      roleOrder,
    );

    expect(organizations.map((organization) => organization.organizationId).sort()).toEqual([
      "council",
      "mayors-office",
    ]);
    expect(
      organizations.flatMap((organization) =>
        organization.ranked.flatMap((group) =>
          group.people.map((entry) => [organization.organizationId, group.roleLabel, entry.card.personId]),
        ),
      ),
    ).toEqual([
      ["council", "Council Member", "ana"],
      ["mayors-office", "Mayor", "ana"],
    ]);
  });

  it("groups by role inside an organization, ranked first", () => {
    const { organizations } = sectionsByOrganization(
      [card({ personId: "ana" }), card({ personId: "bo" })],
      proposalsByPersonId([
        proposedIn("ana", "council", "council-member", "Council Member"),
        proposedIn("bo", "council", "mayor", "Mayor"),
      ]),
      roleOrder,
    );

    expect(organizations[0].ranked.map((group) => group.roleLabel)).toEqual([
      "Mayor",
      "Council Member",
    ]);
  });

  it("keeps a post no role matched out of the ranked groups", () => {
    const { organizations } = sectionsByOrganization(
      [card({ personId: "fay" })],
      proposalsByPersonId([proposedIn("fay", "council", "unmatched")]),
      roleOrder,
    );

    expect(organizations[0].ranked).toEqual([]);
    expect(organizations[0].unmatched.map((entry) => entry.card.personId)).toEqual(["fay"]);
  });

  it("leaves people nobody proposed anything for out of every organization", () => {
    const { organizations, departing } = sectionsByOrganization(
      [card({ personId: "cy", status: PersonStatus.REMOVED }), card({ personId: "dee" })],
      proposalsByPersonId([]),
      roleOrder,
    );

    expect(organizations).toEqual([]);
    expect(departing.map((entry) => entry.personId).sort()).toEqual(["cy", "dee"]);
  });
});
