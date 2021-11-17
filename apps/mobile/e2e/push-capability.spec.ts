import { expect, test } from "@playwright/test";

async function isolateLocalServices(page: import("@playwright/test").Page, context: import("@playwright/test").BrowserContext) {
  const allowed = new Set((process.env.E2E_ALLOWED_PORTS || "").split(","));
  const blocked: string[] = [];
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.protocol === "data:" || (url.hostname === "127.0.0.1" && allowed.has(url.port))) await route.continue();
    else { blocked.push(url.origin); await route.abort("blockedbyclient"); }
  });
  await page.addInitScript(() => {
    (window as typeof window & { __pushPromptCalls?: number }).__pushPromptCalls = 0;
    try {
      Object.defineProperty(Notification, "requestPermission", {
        configurable: true,
        value: () => {
          (window as typeof window & { __pushPromptCalls?: number }).__pushPromptCalls!++;
          return Promise.resolve("granted");
        },
      });
    } catch { /* Browser may expose a non-configurable prompt method. */ }
  });
  return blocked;
}

async function createSyntheticUser(page: import("@playwright/test").Page, profile: string, suffix: string, openNotifications = true) {
  await page.goto("/", { waitUntil: "commit" });
  await page.locator('button[aria-label="Sign in"]').click();
  await page.getByRole("button", { name: "New here? Create a free account" }).click();
  await page.getByPlaceholder("you@example.com").fill(`q23-push-${profile}-${suffix}@example.test`);
  await page.getByPlaceholder("At least 12 characters").fill("synthetic-test-password-123");
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page.getByRole("button", { name: "Account", exact: true })).toBeVisible();
  if (openNotifications) await page.getByRole("button", { name: "Notifications", exact: true }).first().click();
}

test("disabled server configuration never prompts for browser push permission", async ({ page, context }, info) => {
  const blocked = await isolateLocalServices(page, context);
  await page.route(`${process.env.E2E_API_URL}/v1/notifications/config`, (route) =>
    route.fulfill({ json: { web_push_enabled: false, vapid_public_key: "" } }),
  );
  await createSyntheticUser(page, info.project.name, "disabled");
  await expect(page.getByText("Browser push is not configured yet. Your alerts are saved in the inbox.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Enable device alerts" })).toBeDisabled();
  expect(await page.evaluate(() => (window as typeof window & { __pushPromptCalls?: number }).__pushPromptCalls)).toBe(0);
  expect(blocked).toEqual([]);
});

test("unsupported browser shows recovery guidance without prompting", async ({ page, context }, info) => {
  const blocked = await isolateLocalServices(page, context);
  await createSyntheticUser(page, info.project.name, "unsupported", false);
  await page.evaluate(() => { Reflect.deleteProperty(window, "PushManager"); });
  await page.getByRole("button", { name: "Notifications", exact: true }).first().click();
  await expect(page.getByText("This browser does not support push notifications. Your in-app inbox still works.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Enable device alerts" })).toBeDisabled();
  expect(await page.evaluate(() => (window as typeof window & { __pushPromptCalls?: number }).__pushPromptCalls)).toBe(0);
  expect(blocked).toEqual([]);
});
