import { describe, it, expect } from "vitest";
import {
  previousPagesByOrganization,
  flattenPages,
  type RosterPerson,
} from "../pages/jurisdictions-page/scrape-modal/previous-pages.ts";

const COUNCIL = { id: "council", name: "City Council" };
const MAYOR = { id: "mayor", name: "Office of the Mayor" };

const person = (id: string, organizationId: string, urls: string[]): RosterPerson => ({
  id,
  memberships: [{ organization_id: organizationId, source_urls: urls }],
});

describe("previousPagesByOrganization", () => {
  it("groups each organization's pages, the page most people came from first", () => {
    const people = [
      person("a", "council", ["https://x.gov/council", "https://x.gov/bio-a"]),
      person("b", "council", ["https://x.gov/council"]),
      person("m", "mayor", ["https://x.gov/mayor"]),
    ];

    expect(previousPagesByOrganization(people, [COUNCIL, MAYOR])).toEqual([
      { organizationName: "City Council", urls: ["https://x.gov/council", "https://x.gov/bio-a"] },
      { organizationName: "Office of the Mayor", urls: ["https://x.gov/mayor"] },
    ]);
  });

  it("lists a shared page once, under the organization with more people on it", () => {
    const shared = "https://x.gov/elected-officials";
    const people = [
      person("a", "council", [shared]),
      person("b", "council", [shared]),
      person("m", "mayor", [shared]),
    ];

    expect(previousPagesByOrganization(people, [COUNCIL, MAYOR])).toEqual([
      { organizationName: "City Council", urls: [shared] },
      { organizationName: "Office of the Mayor", urls: [] },
    ]);
  });

  it("keeps an organization with no pages, so a url can be added under it", () => {
    expect(previousPagesByOrganization([], [COUNCIL])).toEqual([
      { organizationName: "City Council", urls: [] },
    ]);
  });

  it("puts pages from an organization it was not given under Other", () => {
    const people = [person("a", "gone", ["https://x.gov/old"])];

    expect(previousPagesByOrganization(people, [COUNCIL])).toEqual([
      { organizationName: "City Council", urls: [] },
      { organizationName: "Other", urls: ["https://x.gov/old"] },
    ]);
  });
});

describe("flattenPages", () => {
  it("sends every url once, in the order shown", () => {
    const groups = [
      { organizationName: "City Council", urls: ["https://x.gov/a", "https://x.gov/b"] },
      { organizationName: "Office of the Mayor", urls: ["https://x.gov/b", "https://x.gov/c"] },
    ];

    expect(flattenPages(groups)).toEqual(["https://x.gov/a", "https://x.gov/b", "https://x.gov/c"]);
  });
});
