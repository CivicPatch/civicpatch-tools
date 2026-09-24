import { describe, it, expect } from "vitest";
import {
  attentionOf,
  byRank,
  foundNobody,
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
import { postsFor } from "../components/people/person-cards.js";

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
  const office = (over = {}) => ({
    post_id: "post-5",
    organization_id: "org-1",
    role_id: "council-member",
    role_label: "Council Member",
    post_label: "Council Member, District 5",
    division_ocdid: "ocd-division/country:us/state:wa/place:x/council_district:5",
    label: null,
    source_labels: [],
    ...over,
  });
  const withOffices = (memberships: unknown[]) =>
    card({ newRecord: { id: "p1", name: "A", memberships } });

  // These three verified that a proposed post was named from `ProposedChange`, because a
  // proposed person held no membership for the card to read. They now verify the same
  // rendering from the record's own memberships: the proposed record is the fold's, and the
  // fold names a post from `PostKey` whether or not a row exists for it yet.
  it("names the post the record holds", () =>
    expect(postsFor(withOffices([office()]))).toBe("Council Member, District 5"));

  it("composes the post label with the membership's own label", () =>
    expect(
      postsFor(
        withOffices([office({ post_label: "Council Member, At-Large", label: "Seat 3" })]),
      ),
    ).toBe("Council Member, At-Large, Seat 3"));

  it("reads a published person's memberships the same way", () =>
    expect(postsFor(withOffices([office({ post_label: "Mayor", role_id: "mayor" })]))).toBe(
      "Mayor",
    ));

  it("says nothing rather than repeating the joined office string", () =>
    expect(postsFor(card())).toBe(""));
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
  // Sections came from `ProposedChange` until 2026-09-23. They come from the records' own
  // memberships now, which is why these read a card with a proposed side rather than a
  // separate list of proposals.
  const office = (
    organizationId: string,
    roleId: string,
    roleLabel = roleId,
  ) => ({
    post_id: `${organizationId}:${roleId}`,
    organization_id: organizationId,
    role_id: roleId,
    role_label: roleLabel,
    post_label: roleLabel,
    division_ocdid: "ocd-division/country:us/state:wa/place:x",
    label: null,
  });
  const holding = (personId: string, offices: unknown[], over = {}) =>
    card({
      personId,
      newRecord: { id: personId, name: personId, memberships: offices } as never,
      ...over,
    });

  it("lists a person once per organization they hold an office in", () => {
    const { organizations } = sectionsByOrganization(
      [
        holding("ana", [
          office("council", "council-member", "Council Member"),
          office("mayors-office", "mayor", "Mayor"),
        ]),
      ],
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
      [
        holding("ana", [office("council", "council-member", "Council Member")]),
        holding("bo", [office("council", "mayor", "Mayor")]),
      ],
      roleOrder,
    );

    expect(organizations[0].ranked.map((group) => group.roleLabel)).toEqual([
      "Mayor",
      "Council Member",
    ]);
  });

  it("keeps a post no role matched out of the ranked groups", () => {
    const { organizations } = sectionsByOrganization(
      [holding("fay", [office("council", "unmatched")])],
      roleOrder,
    );

    expect(organizations[0].ranked).toEqual([]);
    expect(organizations[0].unmatched.map((entry) => entry.card.personId)).toEqual(["fay"]);
  });

  it("leaves people holding nothing out of every organization", () => {
    // This verified that both landed in `departing`. It now separates them, because somebody a
    // reviewer just added holds nothing *yet* — filing them under "not found or removed" read
    // as a verdict on a person who had just arrived.
    const { organizations, departing, unplaced } = sectionsByOrganization(
      [card({ personId: "cy", status: PersonStatus.REMOVED }), card({ personId: "dee" })],
      roleOrder,
    );

    expect(organizations).toEqual([]);
    expect(departing.map((entry) => entry.personId)).toEqual(["cy"]);
    expect(unplaced.map((entry) => entry.personId)).toEqual(["dee"]);
  });

  it("keeps a section for a body this scrape emptied, and says nobody was found", () => {
    // The reviewer has to be able to tell "we read this page and it listed nobody" from "we
    // never read it". The section survives because the held side still names the body.
    const leaving = card({
      personId: "gus",
      oldRecord: { id: "gus", memberships: [office("council", "mayor", "Mayor")] } as never,
      newRecord: { id: "gus", name: "gus", memberships: [] } as never,
    });

    const { organizations } = sectionsByOrganization([leaving], roleOrder);

    expect(organizations[0].organizationId).toBe("council");
    expect(foundNobody(organizations[0].ranked.flatMap((group) => group.people))).toBe(true);
  });

  it("orders sections the way the card lists its organizations", () => {
    const { organizations } = sectionsByOrganization(
      [
        holding("ana", [office("council", "council-member", "Council Member")]),
        holding("bo", [office("mayors-office", "mayor", "Mayor")]),
      ],
      roleOrder,
      ["mayors-office", "council"],
    );

    expect(organizations.map((organization) => organization.organizationId)).toEqual([
      "mayors-office",
      "council",
    ]);
  });
});
