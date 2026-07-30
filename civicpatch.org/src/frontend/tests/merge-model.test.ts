import { describe, it, expect } from "vitest";
import {
  chooseSurvivor,
  planMerge,
  setChoice,
  applyMergePlan,
  joinOfficeNames,
  mergeCards,
  MergeChoice,
} from "../components/review/merge-model.js";
import { RailStatus, type ReviewCard } from "../components/review/review-cards.js";

const DIVISION = "ocd-division/country:us/state:nh/place:concord/ward:1";

const person = (id: string, over: Record<string, unknown> = {}) => ({
  id,
  name: `Person ${id}`,
  office: { name: "Council Member", division_ocdid: DIVISION },
  other_names: [],
  emails: [],
  phones: [],
  urls: [],
  source_urls: [],
  ...over,
});

// Only the two record sides matter to the survivor rule; `surviving` and
// `issues` are irrelevant here, so they stay empty.
const card = (
  personId: string,
  { old: oldRecord = null, now: newRecord = null, status = RailStatus.CHANGED } : {
    old?: any;
    now?: any;
    status?: string;
  },
): ReviewCard => ({
  personId,
  status: status as ReviewCard["status"],
  oldRecord,
  newRecord,
  surviving: [],
  issues: [],
});

const existing = (id: string, over: Record<string, unknown> = {}) =>
  card(id, { old: person(id, over), now: person(id, over) });
const added = (id: string, over: Record<string, unknown> = {}) =>
  card(id, { now: person(id, over), status: RailStatus.ADDED });
const removed = (id: string, over: Record<string, unknown> = {}) =>
  card(id, { old: person(id, over), status: RailStatus.REMOVED });

describe("chooseSurvivor", () => {
  it("prefers the record already in the database over a scraped one", () => {
    expect(chooseSurvivor(added("a"), existing("b")).personId).toBe("b");
    expect(chooseSurvivor(existing("b"), added("a")).personId).toBe("b");
  });

  it("prefers the record this scrape still matched when both are durable", () => {
    expect(chooseSurvivor(removed("a"), existing("b")).personId).toBe("b");
  });

  it("falls back to frozen order when both are durable and both matched", () => {
    expect(chooseSurvivor(existing("a"), existing("b")).personId).toBe("a");
  });

  it("falls back to frozen order when neither id is durable", () => {
    expect(chooseSurvivor(added("a"), added("b")).personId).toBe("a");
    expect(chooseSurvivor(removed("a"), removed("b")).personId).toBe("a");
  });
});

describe("planMerge defaults", () => {
  it("pre-presses single fields to the candidate's value", () => {
    const plan = planMerge(existing("a"), added("b", { name: "Alma Whitfield" }));
    const name = plan.fields.find((f) => f.field.key === "name")!;
    expect(name.choice).toBe(MergeChoice.REPLACE);
    expect(name.candidateValue).toBe("Alma Whitfield");
  });

  it("never lets an empty candidate displace a filled survivor", () => {
    const plan = planMerge(
      existing("a", { start_date: "2023-01-03" }),
      added("b", { start_date: "" }),
    );
    const start = plan.fields.find((f) => f.field.key === "start_date")!;
    expect(start.choice).toBe(MergeChoice.KEEP);
  });

  it("pre-presses list fields to keep both", () => {
    const plan = planMerge(
      existing("a", { emails: ["a@x.gov"] }),
      added("b", { emails: ["b@x.gov"] }),
    );
    const emails = plan.fields.find((f) => f.field.key === "emails")!;
    expect(emails.choice).toBe(MergeChoice.BOTH);
  });

  it("marks agreeing fields same and leaves them on the survivor", () => {
    const plan = planMerge(existing("a"), added("b", { name: "Person a" }));
    const name = plan.fields.find((f) => f.field.key === "name")!;
    expect(name.same).toBe(true);
    expect(name.choice).toBe(MergeChoice.KEEP);
  });

  it("offers a third option on office name only", () => {
    const plan = planMerge(existing("a"), added("b"));
    const office = plan.fields.find((f) => f.field.key === "office.name")!;
    const emails = plan.fields.find((f) => f.field.key === "emails")!;
    expect(office.choices).toContain(MergeChoice.BOTH);
    expect(office.choices).toContain(MergeChoice.REPLACE);
    expect(emails.choices).not.toContain(MergeChoice.REPLACE);
  });
});

describe("joinOfficeNames", () => {
  // Two merged Mayors becoming "Mayor - Mayor" makes
  // _check_duplicate_unique_roles read one person as two holders of the role.
  it("dedupes so a role cannot duplicate itself", () => {
    expect(joinOfficeNames("Mayor", "Mayor")).toBe("Mayor");
  });

  it("keeps genuinely different roles, split on the separator", () => {
    expect(joinOfficeNames("Mayor", "Council Member")).toBe("Mayor - Council Member");
    expect(joinOfficeNames("Mayor - Clerk", "Clerk")).toBe("Mayor - Clerk");
  });

  it("drops blanks rather than emitting a dangling separator", () => {
    expect(joinOfficeNames("Mayor", "")).toBe("Mayor");
    expect(joinOfficeNames("", "")).toBe("");
  });
});

describe("applyMergePlan", () => {
  it("keeps the survivor's id", () => {
    const survivor = existing("a");
    const absorbed = added("b");
    const merged = applyMergePlan(planMerge(survivor, absorbed), survivor, absorbed);
    expect(merged.id).toBe("a");
  });

  it("files the displaced name as an alias rather than losing it", () => {
    const survivor = existing("a", { name: "Alma Ruiz-Whitfield" });
    const absorbed = added("b", { name: "Alma Ruiz Whitfield" });
    const merged = applyMergePlan(planMerge(survivor, absorbed), survivor, absorbed);
    expect(merged.name).toBe("Alma Ruiz Whitfield");
    expect(merged.other_names).toContain("Alma Ruiz-Whitfield");
    expect(merged.other_names).not.toContain("Alma Ruiz Whitfield");
  });

  it("unions list fields without duplicating shared values", () => {
    const survivor = existing("a", { emails: ["shared@x.gov", "a@x.gov"] });
    const absorbed = added("b", { emails: ["shared@x.gov", "b@x.gov"] });
    const merged = applyMergePlan(planMerge(survivor, absorbed), survivor, absorbed);
    expect(merged.emails).toEqual(["shared@x.gov", "a@x.gov", "b@x.gov"]);
  });

  it("honours a choice the reviewer changed", () => {
    const survivor = existing("a", { name: "Alma Ruiz-Whitfield" });
    const absorbed = added("b", { name: "Alma Ruiz Whitfield" });
    const plan = setChoice(planMerge(survivor, absorbed), "name", MergeChoice.KEEP);
    const merged = applyMergePlan(plan, survivor, absorbed);
    expect(merged.name).toBe("Alma Ruiz-Whitfield");
    expect(merged.other_names).toContain("Alma Ruiz Whitfield");
  });

  it("joins office names through the dedupe when asked to keep both", () => {
    const survivor = existing("a", {
      office: { name: "Mayor", division_ocdid: DIVISION },
    });
    const absorbed = added("b", {
      office: { name: "Mayor", division_ocdid: DIVISION },
    });
    const plan = setChoice(planMerge(survivor, absorbed), "office.name", MergeChoice.BOTH);
    const merged = applyMergePlan(plan, survivor, absorbed);
    expect(merged.office?.name).toBe("Mayor");
  });

  it("drops the stale CDN copy when the photo is replaced", () => {
    const survivor = existing("a", { cdn_image: "https://cdn/old.jpg", image: null });
    const absorbed = added("b", { image: "https://city.gov/new.jpg" });
    const merged = applyMergePlan(planMerge(survivor, absorbed), survivor, absorbed);
    expect(merged.image).toBe("https://city.gov/new.jpg");
    expect(merged.cdn_image).toBeNull();
  });

  it("merges a person the scrape dropped, which has only an old side", () => {
    const survivor = existing("a", { emails: ["a@x.gov"] });
    const absorbed = removed("b", { emails: ["b@x.gov"] });
    const merged = applyMergePlan(planMerge(survivor, absorbed), survivor, absorbed);
    expect(merged.emails).toEqual(["a@x.gov", "b@x.gov"]);
  });
});

describe("fields that are never a choice", () => {
  // Aliases are what make a merge durable: matching consults them, so the
  // absorbed name resolves to the survivor next scrape. A reviewer who could
  // choose "keep" here would silently un-merge the pair a week later.
  it("offers no choice on other_names or source_urls", () => {
    const plan = planMerge(existing("a"), added("b"));
    for (const key of ["other_names", "source_urls"]) {
      const entry = plan.fields.find((f) => f.field.key === key)!;
      expect(entry.choices).toEqual([MergeChoice.BOTH]);
      expect(entry.choice).toBe(MergeChoice.BOTH);
    }
  });

  it("unions sources even when the reviewer tries to keep only the survivor's", () => {
    const survivor = existing("a", { source_urls: ["https://x.gov/a"] });
    const absorbed = added("b", { source_urls: ["https://x.gov/b"] });
    const plan = setChoice(planMerge(survivor, absorbed), "source_urls", MergeChoice.KEEP);
    const merged = applyMergePlan(plan, survivor, absorbed);
    expect(merged.source_urls).toEqual(["https://x.gov/a", "https://x.gov/b"]);
  });
});

describe("setChoice", () => {
  // Without the guard `both` on a date reaches the office-name join and
  // produces "2023-01-03 - 2023-01-01".
  it("ignores a choice the field does not offer", () => {
    const survivor = existing("a", { start_date: "2023-01-03" });
    const absorbed = added("b", { start_date: "2023-01-01" });
    const plan = setChoice(planMerge(survivor, absorbed), "start_date", MergeChoice.BOTH);
    const merged = applyMergePlan(plan, survivor, absorbed);
    expect(merged.start_date).toBe("2023-01-01");
  });
});

describe("defaults when both records are curated", () => {
  // existing + added is the link case: the scrape is the fresher read, so it
  // wins. existing + existing is two curated records, where neither is.
  it("keeps the survivor's values when the candidate is not a fresh scrape", () => {
    const plan = planMerge(
      existing("a", { name: "Alma Ruiz-Whitfield" }),
      existing("b", { name: "Alma Whitfield" }),
    );
    const name = plan.fields.find((f) => f.field.key === "name")!;
    expect(name.choice).toBe(MergeChoice.KEEP);
  });

  it("still lets the scrape win when the candidate has no database history", () => {
    const plan = planMerge(
      existing("a", { name: "Alma Ruiz-Whitfield" }),
      added("b", { name: "Alma Whitfield" }),
    );
    expect(plan.fields.find((f) => f.field.key === "name")!.choice).toBe(MergeChoice.REPLACE);
  });

  it("keeps the survivor's values when the candidate is one the scrape dropped", () => {
    const plan = planMerge(
      existing("a", { name: "Alma Ruiz-Whitfield" }),
      removed("b", { name: "Alma Whitfield" }),
    );
    expect(plan.fields.find((f) => f.field.key === "name")!.choice).toBe(MergeChoice.KEEP);
  });
});

describe("updated_at", () => {
  it("never leaves the merged record looking older than what it absorbed", () => {
    const survivor = existing("a", { updated_at: "2024-01-01T00:00:00+00:00" });
    const absorbed = added("b", { updated_at: "2026-07-29T00:00:00+00:00" });
    const merged = applyMergePlan(planMerge(survivor, absorbed), survivor, absorbed) as any;
    expect(merged.updated_at).toBe("2026-07-29T00:00:00+00:00");
  });
});

// These assertions were written against buildLinkUpdates, which is gone: link is
// now mergeCards with the defaults untouched. Same claims, one implementation.
describe("link behaviour, via mergeCards", () => {
  // The target is the record already in the database; the added person is the
  // scraped one adopting its id.
  const link = (added: any, target: any) =>
    mergeCards(
      card("old", { old: target, status: RailStatus.REMOVED }),
      card("new", { now: added, status: RailStatus.ADDED }),
    ) as any;

  it("adopts the target's id", () => {
    expect(link({ id: "new", name: "Bob" }, { id: "old", name: "Robert" }).id).toBe("old");
  });

  it("keeps the added person's name as the primary one", () => {
    expect(link({ id: "new", name: "Bob" }, { id: "old", name: "Robert" }).name).toBe("Bob");
  });

  it("folds the target's old name into other_names as an alias", () => {
    expect(
      link({ id: "new", name: "Bob Smith" }, { id: "old", name: "Robert Smith" }).other_names,
    ).toContain("Robert Smith");
  });

  it("keeps both the target's and the added person's existing aliases", () => {
    const aliases = link(
      { id: "new", name: "Bob", other_names: ["Bobby"] },
      { id: "old", name: "Robert", other_names: ["Rob"] },
    ).other_names;
    expect(aliases).toContain("Rob");
    expect(aliases).toContain("Bobby");
    expect(aliases).toContain("Robert");
  });

  it("drops the added person's own name from the aliases", () => {
    expect(
      link({ id: "new", name: "Bob" }, { id: "old", name: "Bob", other_names: ["Bob"] }).other_names,
    ).not.toContain("Bob");
  });

  it("dedupes aliases", () => {
    const aliases = link(
      { id: "new", name: "Bob", other_names: ["Rob"] },
      { id: "old", name: "Robert", other_names: ["Rob", "Robert"] },
    ).other_names;
    expect(aliases).toEqual([...new Set(aliases)]);
  });
});

