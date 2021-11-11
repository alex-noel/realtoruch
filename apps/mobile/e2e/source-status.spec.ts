import { expect, test, type BrowserContext } from "@playwright/test";
import type { Listing, SourceHealth } from "../src/types";

const API_URL = process.env.E2E_API_URL!;

function gate() {
  let open!: () => void;
  const wait = new Promise<void>((resolve) => {
    open = resolve;
  });
  return { open, wait };
}

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

function home(id: string, title: string, city: string): Listing {
  return {
    id,
    title,
    city,
    description: "",
    district: "",
    region: "",
    address: "",
    lat: null,
    lon: null,
    area_m2: 55,
    rooms: 2,
    floor: null,
    rent_pln: 4_500,
    fees_pln: null,
    deposit_pln: null,
    commission_pln: null,
    total_monthly_pln: null,
    advertiser_type: "private",
    property_type: "apartment",
    status: "active",
    images: [],
    amenities: [],
    is_demo: false,
    first_seen: "2026-01-01T10:00:00Z",
    last_seen: "2026-01-01T10:00:00Z",
    risk_score: 0,
    risk_flags: [],
    sources: [],
  };
}

function catalog(items: Listing[]) {
  return { items, total: items.length, page: 1, page_size: 50, engine: "sql" };
}

function source(name: string): SourceHealth {
  return {
    name,
    enabled: false,
    cadence_minutes: null,
    last_observed_at: null,
    stored_adverts: 0,
    health: null,
  };
}

test("city responses are fenced independently and fifty visible homes use one private batch", async ({
  page,
  context,
}, info) => {
  const blocked = await allowLoopback(context);
  const krakowSearch = gate();
  const krakowSources = gate();
  const releaseKrakow = gate();
  const bulkStarted = gate();
  const releaseBulk = gate();
  const queries: string[] = [];
  const batches: string[][] = [];
  const inputText = "abcdefghijklmnopqrst";

  // Force late HTTP delivery despite the caller cancellation to exercise the fences.
  await page.addInitScript((apiOrigin) => {
    const fetch = window.fetch;
    window.fetch = (resource, init) => {
      const url =
        typeof resource === "string"
          ? new URL(resource, window.location.href)
          : null;
      const latePaths = ["/v1/listings", "/v1/sources", "/v1/me/listing-state"];
      return url && url.origin === apiOrigin && latePaths.includes(url.pathname)
        ? fetch(resource, { ...init, signal: undefined })
        : fetch(resource, init);
    };
  }, API_URL);

  await page.route(`${API_URL}/v1/listings?*`, async (route) => {
    const query = new URL(route.request().url()).searchParams;
    const city = query.get("city") ?? "";
    const keyword = query.get("q") ?? "";
    if (city === "Kraków") {
      krakowSearch.open();
      await releaseKrakow.wait;
      return route.fulfill({
        json: catalog([home("k1", "Kraków late home", city)]),
      });
    }
    queries.push(keyword);
    const items =
      keyword === inputText
        ? Array.from({ length: 50 }, (_, index) =>
            home(`w${index}`, `Warszawa match ${index}`, city),
          )
        : [home("warsaw", "Warszawa first home", city)];
    return route.fulfill({ json: catalog(items) });
  });
  await page.route(`${API_URL}/v1/sources?*`, async (route) => {
    const city = new URL(route.request().url()).searchParams.get("city");
    if (city === "Kraków") {
      krakowSources.open();
      await releaseKrakow.wait;
      return route.fulfill({
        json: { sources: [source("otodom")], demo_mode: false },
      });
    }
    return route.fulfill({
      json: { sources: [source("morizon")], demo_mode: false },
    });
  });
  await page.route(`${API_URL}/v1/me/listing-state`, async (route) => {
    const { listing_ids } = route.request().postDataJSON();
    batches.push(listing_ids);
    if (listing_ids.length !== 50)
      return route.fulfill({ json: { seen_ids: [] } });
    bulkStarted.open();
    await releaseBulk.wait;
    return route.fulfill({ json: { seen_ids: listing_ids } });
  });

  try {
    await page.goto("/", { waitUntil: "commit" });
    await Promise.all([krakowSearch.wait, krakowSources.wait]);
    await page
      .getByRole("textbox", { name: "City", exact: true })
      .fill("Warszawa");
    await expect(
      page.getByRole("button", { name: "View Warszawa first home" }),
    ).toBeVisible();
    await expect(
      page.getByText("Morizon · Automatic collection unavailable"),
    ).toBeVisible();
    const oldSearch = page.waitForResponse(
      (response) =>
        response.url().includes("/v1/listings?") &&
        new URL(response.url()).searchParams.get("city") === "Kraków",
    );
    const oldSources = page.waitForResponse(
      (response) =>
        response.url().includes("/v1/sources?") &&
        new URL(response.url()).searchParams.get("city") === "Kraków",
    );
    releaseKrakow.open();
    const oldResponses = await Promise.all([oldSearch, oldSources]);
    await Promise.all(oldResponses.map((response) => response.finished()));
    await expect(
      page.getByRole("button", { name: "View Warszawa first home" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "View Kraków late home" }),
    ).toHaveCount(0);
    await expect(
      page.getByText("Otodom · Automatic collection unavailable"),
    ).toHaveCount(0);

    await page.locator('button[aria-label="Sign in"]').click();
    await page
      .getByRole("button", { name: "New here? Create a free account" })
      .click();
    await page
      .getByPlaceholder("you@example.com")
      .fill(`t19-${info.project.name}@example.test`);
    await page
      .getByPlaceholder("At least 12 characters")
      .fill("synthetic-test-password-123");
    await page
      .getByRole("button", { name: "Create account", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Account", exact: true }),
    ).toBeVisible();
    await expect.poll(() => batches).toEqual([["warsaw"]]);

    const keyword = page.getByRole("textbox", {
      name: "Search neighborhood, street or keyword",
    });
    await keyword.pressSequentially(inputText);
    await bulkStarted.wait;
    expect(queries.filter(Boolean)).toEqual([inputText]);
    expect(batches.map((batch) => batch.length)).toEqual([1, 50]);
    await expect(
      page.getByRole("button", { name: "View Warszawa match 49" }),
    ).toHaveCount(1);

    await page.getByRole("button", { name: "Account", exact: true }).click();
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Account", exact: true }),
    ).toHaveCount(0);
    const lateState = page.waitForResponse((response) =>
      response.url().endsWith("/v1/me/listing-state"),
    );
    releaseBulk.open();
    await (await lateState).finished();
    await page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
    await expect(page.getByText("SEEN", { exact: true })).toHaveCount(0);
    await expect(keyword).toHaveValue(inputText);
    await expect(
      page.getByRole("textbox", { name: "City", exact: true }),
    ).toHaveValue("Warszawa");
    await expect(
      page.getByRole("button", { name: "View Warszawa match 49" }),
    ).toHaveCount(1);
    expect(blocked).toEqual([]);
  } finally {
    releaseKrakow.open();
    releaseBulk.open();
  }
});

test("320 px retains results through offline retry and exposes timestamps by keyboard", async ({
  page,
  context,
}) => {
  const blocked = await allowLoopback(context);
  await page.setViewportSize({ width: 320, height: 720 });
  let offline = false;
  const searchQueries: URLSearchParams[] = [];
  await page.route(`${API_URL}/v1/listings?*`, (route) => {
    searchQueries.push(new URL(route.request().url()).searchParams);
    if (offline) return route.abort("internetdisconnected");
    return route.fulfill({
      json: catalog([home("visible", "Retained Kraków home", "Kraków")]),
    });
  });
  const otodom: SourceHealth = {
    ...source("otodom"),
    enabled: true,
    cadence_minutes: 60,
    last_observed_at: "2026-01-01T11:30:00Z",
    health: {
      city: "Kraków",
      status: "failed",
      limited: false,
      started_at: "2026-01-01T11:45:00Z",
      finished_at: "2026-01-01T12:00:00Z",
      last_success_at: "2026-01-01T10:00:00Z",
      errors: [{ kind: "Private error fixture", http_status: 500 }],
    },
  };
  await page.route(`${API_URL}/v1/sources?*`, (route) =>
    route.fulfill({
      json: {
        demo_mode: false,
        sources: [
          otodom,
          { ...source("olx"), stored_adverts: 1 },
          source("gratka"),
          source("morizon"),
          source("fifth"),
          source("sixth"),
          source("seventh"),
        ],
      },
    }),
  );

  await page.goto("/", { waitUntil: "commit" });
  const listing = page.getByRole("button", {
    name: "View Retained Kraków home",
  });
  await expect(listing).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Source collection · Kraków" }),
  ).toBeVisible();
  await expect(page.getByText("Otodom · Collection failed")).toBeVisible();
  await expect(
    page.getByText("Last complete collection is delayed"),
  ).toBeVisible();
  await expect(
    page.getByText("OLX · Automatic collection unavailable"),
  ).toBeVisible();
  await expect(
    page.getByText("1 stored advert. Stored adverts can include imports."),
  ).toBeVisible();
  await expect(page.getByText("Private error fixture")).toHaveCount(0);
  await expect(
    page.getByText("seventh · Automatic collection unavailable"),
  ).toHaveCount(0);
  await expect(
    page.getByText("Showing 6 of 7 configured sources."),
  ).toBeVisible();
  const timestamps = page.getByRole("button", {
    name: "Show collection timestamps",
  });
  await expect(
    page.getByText("Last complete collection · 2026-01-01T10:00:00Z"),
  ).toHaveCount(0);
  await timestamps.focus();
  await expect(timestamps).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(
    page.getByText("Last complete collection · 2026-01-01T10:00:00Z"),
  ).toBeVisible();
  await expect(
    page.getByText("Latest attempt · 2026-01-01T12:00:00Z"),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Hide collection timestamps" }),
  ).toHaveAttribute("aria-expanded", "true");

  const filters = page.getByRole("button", { name: "More filters" });
  await filters.click();
  const rent = page.getByRole("textbox", { name: "RENT BELOW · PLN" });
  await rent.fill("3000");
  await page.getByRole("button", { name: "Close dialog" }).click();
  await filters.click();
  await expect(rent).toHaveValue("");
  await rent.fill("5000");
  const area = page.getByRole("textbox", { name: "MIN AREA · M²" });
  await area.fill("50");
  expect(searchQueries).toHaveLength(1);

  offline = true;
  await page.getByRole("button", { name: "Show matching homes" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Could not update homes" }),
  ).toBeVisible();
  await expect(listing).toBeVisible();
  await expect(
    page.getByText(/^Showing previous results loaded /),
  ).toBeVisible();
  expect(searchQueries[1].get("max_price")).toBe("5000");
  expect(searchQueries[1].get("max_price_exclusive")).toBe("true");
  expect(searchQueries[1].get("min_area")).toBe("50");

  const retry = page.getByRole("button", { name: "Retry search" });
  await retry.focus();
  await expect(retry).toBeFocused();
  offline = false;
  await page.keyboard.press("Enter");
  await expect(retry).toHaveCount(0);
  await expect(listing).toBeVisible();
  await expect(page.getByText(/^Showing previous results loaded /)).toHaveCount(
    0,
  );
  expect(searchQueries).toHaveLength(3);
  expect(searchQueries[2].toString()).toBe(searchQueries[1].toString());
  await expect(filters).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    320,
  );
  expect(blocked).toEqual([]);
});
