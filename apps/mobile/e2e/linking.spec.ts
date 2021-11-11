import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import type { Listing } from "../src/types";

const API_URL = process.env.E2E_API_URL!;
const AUTH_URL = process.env.E2E_AUTH_URL!;

test.use({ trace: "off" });

async function allowLoopback(context: BrowserContext) {
  const ports = new Set((process.env.E2E_ALLOWED_PORTS || "").split(","));
  const blocked: string[] = [];
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (
      url.protocol === "data:" ||
      (url.hostname === "127.0.0.1" && ports.has(url.port))
    ) {
      await route.continue();
    } else {
      blocked.push(url.origin);
      await route.abort("blockedbyclient");
    }
  });
  return blocked;
}

async function register(page: Page, name: string) {
  await page
    .getByRole("button", { name: "New here? Create a free account" })
    .click();
  await page.getByPlaceholder("you@example.com").fill(`${name}@example.test`);
  await page
    .getByPlaceholder("At least 12 characters")
    .fill("synthetic-link-password-123");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
}

test("protected alias resumes after login and warm push opens the same retained home", async ({
  page,
  context,
}, info) => {
  const blocked = await allowLoopback(context);
  const alias = "old-saved-alias";
  const canonical = "canonical-saved-home";
  const title = "T21 retained fixture home";
  const home: Listing = {
    id: canonical,
    title,
    description: "Synthetic retained fixture",
    city: "Kraków",
    district: "",
    region: "",
    address: "",
    lat: null,
    lon: null,
    area_m2: 55,
    rooms: 2,
    floor: null,
    rent_pln: 4_200,
    fees_pln: null,
    deposit_pln: null,
    commission_pln: null,
    total_monthly_pln: null,
    advertiser_type: "private",
    property_type: "apartment",
    status: "inactive",
    images: [],
    amenities: [],
    is_demo: false,
    first_seen: "2026-01-01T10:00:00Z",
    last_seen: "2026-01-01T10:00:00Z",
    risk_score: 0,
    risk_flags: [],
    sources: [],
  };
  const lookedUp: string[] = [];
  const markedSeen: string[] = [];
  await page.route(`${API_URL}/v1/listings/${alias}`, (route) => {
    lookedUp.push(alias);
    return route.fulfill({ json: home });
  });
  await page.route(`${API_URL}/v1/me/favorites`, (route) =>
    route.fulfill({ json: { items: [home] } }),
  );
  await page.route(`${API_URL}/v1/me/seen/*`, (route) => {
    markedSeen.push(
      new URL(route.request().url()).pathname.split("/").at(-1) ?? "",
    );
    return route.fulfill({
      json: { seen: true, listing_id: canonical, rent_pln: home.rent_pln },
    });
  });

  await page.goto(`/?saved_listing=${alias}`, { waitUntil: "commit" });
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
  expect(lookedUp).toEqual([]);
  await register(page, `t21-alias-${info.project.name}`);
  const detail = page.getByRole("dialog");
  await expect(detail.getByText(title, { exact: true })).toBeVisible();
  await expect(
    detail.getByText(/^Delisted · Kept in your saved homes/),
  ).toBeVisible();
  await expect.poll(() => markedSeen).toEqual([canonical]);
  expect(lookedUp).toEqual([alias]);

  await detail.getByRole("button", { name: "Close dialog" }).click();
  await page
    .getByRole("button", { name: "Discover homes", exact: true })
    .click();
  await expect(page.getByRole("button", { name: `View ${title}` })).toHaveCount(
    0,
  );
  await page.evaluate((listing_id) => {
    for (let index = 0; index < 2; index++) {
      navigator.serviceWorker.dispatchEvent(
        new MessageEvent("message", {
          data: { type: "open-listing", listing_id },
        }),
      );
    }
  }, alias);
  await expect(detail.getByText(title, { exact: true })).toBeVisible();
  await expect.poll(() => markedSeen).toEqual([canonical, canonical]);
  expect(lookedUp).toEqual([alias, alias]);

  await page.goto("/?notifications=1", { waitUntil: "commit" });
  await expect(page.getByText("Notifications.", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Account", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toHaveCount(0);
  expect(blocked).toEqual([]);
});

test("account link errors are safe and retryable, with token fragments removed", async ({
  page,
  context,
}, info) => {
  const blocked = await allowLoopback(context);
  const verifyToken = "V".repeat(43);
  const expiredToken = "E".repeat(43);
  const resetToken = "R".repeat(43);
  const tokens = [verifyToken, expiredToken, resetToken];
  let printedToken = false;
  let verifyAttempts = 0;
  let resetAttempts = 0;
  let expiredAttempts = 0;
  page.on("console", (message) => {
    printedToken ||= tokens.some((token) => message.text().includes(token));
  });

  await page.route(`${AUTH_URL}/v1/auth/verify-email`, (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    expect(route.request().postDataJSON().token === verifyToken).toBe(true);
    verifyAttempts++;
    return verifyAttempts === 1
      ? route.fulfill({ status: 503, json: { detail: verifyToken } })
      : route.fulfill({
          json: { message: "Email verified. You can return to your account." },
        });
  });
  await page.route(`${AUTH_URL}/v1/auth/reset-password`, (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    if (route.request().postDataJSON().token === expiredToken) {
      expiredAttempts++;
      return route.fulfill({
        status: 400,
        json: { detail: "This link is invalid or has expired" },
      });
    }
    expect(route.request().postDataJSON().token === resetToken).toBe(true);
    resetAttempts++;
    return resetAttempts === 1
      ? route.fulfill({ status: 503, json: { detail: resetToken } })
      : route.fulfill({
          json: { message: "Password changed. Sign in again on your devices." },
        });
  });

  async function openFragment(fragment: string) {
    await page.evaluate(
      (value) => window.history.replaceState(null, "", "/#" + value),
      fragment,
    );
    await page.reload({ waitUntil: "commit" });
    await expect
      .poll(() => page.evaluate(() => window.location.hash === ""))
      .toBe(true);
  }

  async function enterPassword() {
    await page
      .getByLabel("NEW PASSWORD", { exact: true })
      .fill("new-synthetic-password-123");
    await page
      .getByLabel("REPEAT NEW PASSWORD")
      .fill("new-synthetic-password-123");
    await page
      .getByRole("button", { name: "Change password", exact: true })
      .click();
  }

  await page.goto("/", { waitUntil: "commit" });
  await page.locator('button[aria-label="Sign in"]').click();
  await register(page, `t21-tokens-${info.project.name}`);
  const account = page.getByRole("button", { name: "Account", exact: true });
  await expect(account).toBeVisible();

  await openFragment(`verify_account=${verifyToken}`);
  await expect(
    page.getByText(
      "Could not open this link. Check your connection and try again.",
    ),
  ).toBeVisible();
  await expect(account).toBeVisible();
  await page.getByRole("button", { name: "Retry link", exact: true }).click();
  await expect(
    page.getByText("Email verified. You can return to your account."),
  ).toBeVisible();
  expect(verifyAttempts).toBe(2);
  await expect(account).toBeVisible();

  await openFragment("verify_account=%ZZ");
  await expect(
    page.getByText("This link is invalid or unsupported."),
  ).toBeVisible();
  expect(verifyAttempts).toBe(2);

  await openFragment(`reset_password=${expiredToken}`);
  await enterPassword();
  await expect(
    page.getByText("This link is invalid or has expired.", { exact: true }),
  ).toBeVisible();
  expect(expiredAttempts).toBe(1);
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Close dialog" })
    .click();
  await expect(account).toBeVisible();

  await openFragment(`reset_password=${resetToken}`);
  await enterPassword();
  await expect(
    page.getByText("Cannot reach the service. Try again.", { exact: true }),
  ).toBeVisible();
  await expect(page.locator('button[aria-label="Account"]')).toHaveCount(1);
  await page
    .getByRole("button", { name: "Change password", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
  expect(resetAttempts).toBe(2);

  const savedToken = await page.evaluate((candidates) => {
    const persisted = JSON.stringify({
      url: window.location.href,
      history: window.history.state,
      local: { ...localStorage },
      session: { ...sessionStorage },
      screen: document.body.innerText,
    });
    return candidates.some((candidate) => persisted.includes(candidate));
  }, tokens);
  expect(savedToken).toBe(false);
  expect(printedToken).toBe(false);
  expect(blocked).toEqual([]);
});
