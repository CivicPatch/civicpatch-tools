import { test, expect } from "../fixtures/index.js";
import { execSync } from "node:child_process";

test.setTimeout(60000);

test("useWebSocket reconnects with backoff after the server drops the connection", async ({
  authenticatedPage: page,
}) => {
  const socketUrls = [];
  const subscribes = [];
  page.on("websocket", (ws) => {
    if (!ws.url().endsWith("/ws")) return;
    socketUrls.push(ws.url());
    ws.on("framesent", (frame) => {
      try {
        const parsed = JSON.parse(frame.payload);
        if (parsed.action === "subscribe") subscribes.push(parsed);
      } catch {
        // ignore
      }
    });
  });

  await page.goto("/");
  await page.waitForTimeout(1000);
  expect(socketUrls.length).toBe(1);
  expect(subscribes.length).toBe(1);

  // Force-drop every open connection by restarting the backend container.
  execSync("docker restart civicpatch-e2e-civicpatch-org-e2e-1", { stdio: "ignore" });

  // Give the container time to come back up and the client time to retry with backoff.
  await page.waitForTimeout(20000);

  expect(socketUrls.length).toBeGreaterThanOrEqual(2);
  expect(subscribes.length).toBeGreaterThanOrEqual(2);
});
