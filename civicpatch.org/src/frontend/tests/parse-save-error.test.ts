import { describe, it, expect } from "vitest";
// @ts-expect-error — api-errors.js is plain JS without type declarations
import { parseSaveError } from "../api-errors.js";

const people = [{ id: "p1", name: "Amanda Sandoval" }, { id: "p2", name: "Jane Smith" }];

describe("parseSaveError", () => {
  it("names the person + field and strips pydantic's 'Value error,' prefix", () => {
    const body = { detail: [{ loc: ["body", "data", 1, "phones"], msg: "Value error, Invalid phone number: '(000) 000-0000'" }] };
    expect(parseSaveError(body, 422, people)).toBe("Jane Smith — phones: Invalid phone number: '(000) 000-0000'");
  });

  it("handles a list-element field (loc ends in the element index)", () => {
    const body = { detail: [{ loc: ["body", "data", 0, "urls", 2], msg: "Website must start with 'http://'" }] };
    expect(parseSaveError(body, 422, people)).toBe("Amanda Sandoval — urls: Website must start with 'http://'");
  });

  it("falls back to field-only when the person can't be resolved", () => {
    const body = { detail: [{ loc: ["body", "data", 9, "emails"], msg: "bad" }] };
    expect(parseSaveError(body, 422, people)).toBe("emails: bad");
  });

  it("uses our {error} body when there is no validation detail", () => {
    expect(parseSaveError({ error: "Failed to update pull request data on GitHub" }, 500, people)).toBe(
      "Failed to update pull request data on GitHub",
    );
  });

  it("falls back to the status when the body is empty", () => {
    expect(parseSaveError({}, 422, people)).toBe("HTTP 422");
  });
});
