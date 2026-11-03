import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchRoles } from "../api.js";

describe("fetchRoles", () => {
  const fetchStub = vi.fn();

  beforeEach(() => {
    fetchStub.mockResolvedValue({ ok: true, json: async () => ({ data: { roles: [] } }) });
    vi.stubGlobal("fetch", fetchStub);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchStub.mockReset();
  });

  const requestedUrl = () => fetchStub.mock.calls[0][0];

  it("asks for every role when given nothing", async () => {
    await fetchRoles();
    expect(requestedUrl()).toBe("/api/v1/roles");
  });

  it("asks for a level and its state", async () => {
    await fetchRoles({ level: "counties", state: "vt" });
    expect(requestedUrl()).toBe("/api/v1/roles?level=counties&state=vt");
  });

  it("leaves out a state with no level", async () => {
    await fetchRoles({ state: "vt" });
    expect(requestedUrl()).toBe("/api/v1/roles");
  });

  it("asks for one jurisdiction's roles", async () => {
    await fetchRoles({ jurisdictionOcdid: "ocd-jurisdiction/country:us/state:vt/place:whiting/government" });
    const url = new URL(requestedUrl(), "http://localhost");
    expect(url.searchParams.get("jurisdiction_ocdid")).toBe(
      "ocd-jurisdiction/country:us/state:vt/place:whiting/government",
    );
  });
});
