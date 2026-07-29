import { describe, it, expect } from "vitest";
import { parseReviewView, ReviewView } from "../pages/review-routes.js";

describe("parseReviewView", () => {
  it("accepts each of the three views", () => {
    expect(parseReviewView("overview")).toBe(ReviewView.OVERVIEW);
    expect(parseReviewView("detail")).toBe(ReviewView.DETAIL);
    expect(parseReviewView("preview")).toBe(ReviewView.PREVIEW);
  });

  it("falls back to Overview when the param is absent", () => {
    expect(parseReviewView(null)).toBe(ReviewView.OVERVIEW);
    expect(parseReviewView(undefined)).toBe(ReviewView.OVERVIEW);
  });

  it("falls back to Overview for a value that is not a view", () => {
    // URLs are hand-editable and outlive releases — a stale or mistyped view
    // must not render an empty card.
    expect(parseReviewView("")).toBe(ReviewView.OVERVIEW);
    expect(parseReviewView("Detail")).toBe(ReviewView.OVERVIEW);
    expect(parseReviewView("diff")).toBe(ReviewView.OVERVIEW);
  });
});
