import { describe, it, expect } from "vitest";
import { getIssueDetail } from "../pages/issues-page/utils.js";

describe("getIssueDetail", () => {
  it("shows the stored error string", () => {
    expect(getIssueDetail({ error: "some pipeline error" })).toBe("some pipeline error");
  });

  it("is empty when the issue records no error", () => {
    expect(getIssueDetail({ mergeable_state: null })).toBe("");
  });

  it("is empty when the issue has no data at all", () => {
    expect(getIssueDetail(null)).toBe("");
  });
});
