import { describe, it, expect } from "vitest";
// @ts-expect-error — api-errors.js is plain JS without type declarations
import { parseSaveError } from "../api-errors.js";

describe("parseSaveError", () => {
  it("names the person + field and strips pydantic's 'Value error,' prefix", () => {
    const body = { detail: [{ id: "p2", name: "Jane Smith", field: "phones", message: "Value error, Invalid phone number: '(000) 000-0000'" }] };
    expect(parseSaveError(body, 422)).toBe("Jane Smith — phones: Invalid phone number: '(000) 000-0000'");
  });

  it("falls back to field-only when the person has no name", () => {
    const body = { detail: [{ id: "p1", name: null, field: "emails", message: "bad" }] };
    expect(parseSaveError(body, 422)).toBe("emails: bad");
  });

  it("handles a framework (FastAPI) validation error shape", () => {
    const body = { detail: [{ loc: ["body", "request_id"], msg: "Field required" }] };
    expect(parseSaveError(body, 422)).toBe("request_id: Field required");
  });

  it("uses our {error} body when there is no validation detail", () => {
    expect(parseSaveError({ error: "Failed to update pull request data on GitHub" }, 500)).toBe(
      "Failed to update pull request data on GitHub",
    );
  });

  it("falls back to the status when the body is empty", () => {
    expect(parseSaveError({}, 422)).toBe("HTTP 422");
  });
});
