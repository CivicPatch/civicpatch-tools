import { describe, it, expect } from "vitest";
import { canManageApiKeys } from "../pages/settings-page/api-key-access.js";

const maintainer = {
  authenticated: true,
  display_name: "wandering-meadow",
  permissions: { can_write_config: true },
};

describe("canManageApiKeys", () => {
  it("shows the section to a maintainer", () => {
    expect(canManageApiKeys(maintainer)).toBe(true);
  });

  it("hides it from a contributor", () => {
    expect(
      canManageApiKeys({ ...maintainer, permissions: { can_write_config: false } }),
    ).toBe(false);
  });

  it("hides it when permissions are absent", () => {
    expect(canManageApiKeys({ ...maintainer, permissions: undefined })).toBe(false);
  });

  it("hides it from a signed-out visitor", () => {
    expect(canManageApiKeys({ ...maintainer, authenticated: false })).toBe(false);
  });

  it("hides it until a display name is set", () => {
    expect(canManageApiKeys({ ...maintainer, display_name: null })).toBe(false);
  });

  it("fails closed when the user blob could not be parsed", () => {
    expect(canManageApiKeys(null)).toBe(false);
  });

  it("is not fooled by a truthy non-boolean permission", () => {
    expect(
      canManageApiKeys({
        ...maintainer,
        permissions: { can_write_config: "yes" as unknown as boolean },
      }),
    ).toBe(false);
  });
});
