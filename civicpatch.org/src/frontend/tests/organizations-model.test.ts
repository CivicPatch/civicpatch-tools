import { describe, it, expect } from "vitest";
import {
  defaultOrganizationId,
  type Organization,
} from "../components/organizations-list/organizations-model.js";

const organization = (id: string, meta_is_default = false): Organization => ({
  id,
  name: id,
  url: null,
  sort_order: 0,
  meta_is_default,
  posts: [],
});

describe("defaultOrganizationId", () => {
  it("is the flagged organization wherever it sits in the list", () => {
    expect(defaultOrganizationId([organization("council"), organization("mayor", true)])).toBe(
      "mayor",
    );
  });

  it("falls back to the first in list order when none is flagged", () => {
    expect(defaultOrganizationId([organization("council"), organization("mayor")])).toBe(
      "council",
    );
  });

  it("is null for a jurisdiction with no organizations", () => {
    expect(defaultOrganizationId([])).toBeNull();
  });
});
