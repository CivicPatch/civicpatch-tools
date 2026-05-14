/**
 * Budget guard: the homepage's total wire transfer must stay under a fixed cap.
 *
 * Captures encoded (compressed) response sizes via Chrome DevTools Protocol —
 * this is the actual byte count over the network, not the decoded body size.
 *
 * On failure, prints the top 10 heaviest assets so the regression is obvious.
 *
 * Update MAX_TRANSFER_BYTES when an intentional change crosses the threshold.
 */

import { test, expect } from "@playwright/test";

// Baseline as of 2026-05-13: ~3.85 MB, ~134 requests on cold load.
// Budget is set ~15% above baseline as a regression guard.
// Tighten as the page shrinks; bump deliberately when an intentional change crosses it.
const MAX_TRANSFER_BYTES = 4.5 * 1024 * 1024; // 4.5 MB
const MAX_REQUESTS = 160;

test.describe("Homepage size budget", () => {
  test("cold load transfers under the byte budget", async ({ page, context }) => {
    const cdp = await context.newCDPSession(page);
    await cdp.send("Network.enable");

    const responses = new Map(); // requestId -> { url, mime, encodedDataLength }
    cdp.on("Network.responseReceived", (event) => {
      const existing = responses.get(event.requestId) ?? {};
      responses.set(event.requestId, {
        ...existing,
        url: event.response.url,
        mime: event.response.mimeType,
      });
    });
    cdp.on("Network.loadingFinished", (event) => {
      const existing = responses.get(event.requestId) ?? {};
      responses.set(event.requestId, {
        ...existing,
        encodedDataLength: event.encodedDataLength,
      });
    });

    await page.addInitScript(() => localStorage.clear());
    await page.goto("/", { waitUntil: "networkidle" });

    let total = 0;
    const breakdown = [];
    for (const r of responses.values()) {
      if (typeof r.encodedDataLength === "number") {
        total += r.encodedDataLength;
        breakdown.push({ url: r.url, bytes: r.encodedDataLength, mime: r.mime });
      }
    }

    if (total > MAX_TRANSFER_BYTES) {
      const top = breakdown
        .sort((a, b) => b.bytes - a.bytes)
        .slice(0, 10)
        .map(({ url, bytes, mime }) =>
          `  ${(bytes / 1024).toFixed(1).padStart(8)} KB  [${(mime ?? "").padEnd(28)}]  ${url}`
        )
        .join("\n");
      console.log(`\nTop 10 by size:\n${top}\n`);
    }

    const totalMb = (total / 1024 / 1024).toFixed(2);
    const budgetMb = (MAX_TRANSFER_BYTES / 1024 / 1024).toFixed(2);
    expect(
      total,
      `Homepage transferred ${totalMb} MB (budget: ${budgetMb} MB)`
    ).toBeLessThanOrEqual(MAX_TRANSFER_BYTES);

    expect(
      breakdown.length,
      `Homepage made ${breakdown.length} requests (budget: ${MAX_REQUESTS})`
    ).toBeLessThanOrEqual(MAX_REQUESTS);
  });
});
