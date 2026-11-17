import { test, expect } from "@playwright/test";

test("on-demand sections recover after a failed chunk download", async ({ page, context }) => {
  const allowed = new Set((process.env.E2E_ALLOWED_PORTS || "").split(","));
  const attempts = { Insights: 0, NotificationInbox: 0 };
  const blocked: string[] = [];
  await context.route("**/*", async route => {
    const url = new URL(route.request().url());
    if (url.protocol === "data:" || url.protocol === "blob:") return route.continue();
    if (url.hostname !== "127.0.0.1" || !allowed.has(url.port)) {
      blocked.push(url.origin); return route.abort("blockedbyclient");
    }
    for (const name of Object.keys(attempts) as (keyof typeof attempts)[]) {
      if (url.pathname.includes(`/web/${name}-`) && url.pathname.endsWith(".js")) {
        if (++attempts[name] === 1) return route.abort("failed");
      }
    }
    return route.continue();
  });
  await page.goto("/", { waitUntil: "commit" });
  await page.getByRole("button", { name: "Rent insights", exact: true }).click();
  await expect(page.getByText("Could not load insights. Check your connection and retry.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Retry insights screen", exact: true }).click();
  await expect(page.getByText("Could not load insights. Check your connection and retry.", { exact: true })).toHaveCount(0);
  await expect(page.getByText("A little perspective on price.", { exact: true })).toBeVisible();
  await expect.poll(() => attempts.Insights).toBe(2);
  await page.getByRole("button", { name: "Notifications", exact: true }).click();
  await expect(page.getByText("Could not load notifications. Check your connection and retry.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Retry notifications screen", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign in for notifications", exact: true })).toBeVisible();
  expect(attempts.NotificationInbox).toBe(2);
  expect(blocked).toEqual([]);
});
