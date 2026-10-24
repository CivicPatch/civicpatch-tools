import { describe, it, expect } from "vitest";
import { afterLoginPath } from "../components/email-login/after-login-path.js";

const ORIGIN = "https://civicpatch.org";

describe("afterLoginPath", () => {
  it("goes home with no next", () => {
    expect(afterLoginPath("", ORIGIN)).toBe("/");
  });

  it("goes to a path on this site, query included", () => {
    expect(afterLoginPath("?next=%2Foauth%2Fconsent%3Fauthorization_id%3Dabc", ORIGIN)).toBe(
      "/oauth/consent?authorization_id=abc",
    );
  });

  it.each([
    "https://evil.example",
    "//evil.example",
    "/\\evil.example",
    "/\t/evil.example",
    "/\n/evil.example",
    "/\r/evil.example",
  ])("goes home rather than to %j", (next) => {
    expect(afterLoginPath(`?next=${encodeURIComponent(next)}`, ORIGIN)).toBe("/");
  });

  it("goes home when next is not a URL at all", () => {
    expect(afterLoginPath(`?next=${encodeURIComponent("http://[")}`, ORIGIN)).toBe("/");
  });

  it("never hands javascript: to the browser", () => {
    expect(afterLoginPath(`?next=${encodeURIComponent("javascript:alert(1)")}`, ORIGIN)).toBe("/");
  });
});
