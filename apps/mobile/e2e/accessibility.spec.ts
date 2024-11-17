import { execFileSync } from "node:child_process";
import { writeFile } from "node:fs/promises";
import {
  expect,
  test,
  type BrowserContext,
  type Locator,
  type Page,
} from "@playwright/test";
import type { History, Listing, Summary } from "../src/types";

const web = process.env.E2E_WEB_URL!;
const api = process.env.E2E_API_URL!;
const auth = process.env.E2E_AUTH_URL!;
const first = "T20 home 001";
const second = "T20 home 002";
const timestamp = "2026-01-01T00:00:00Z";
const tile = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jR1sAAAAASUVORK5CYII=",
  "base64",
);
const homes: Listing[] = Array.from({ length: 100 }, (_, i) => {
  const n = String(i + 1).padStart(3, "0");
  return {
    id: `t20-${n}`,
    title: `T20 home ${n}`,
    city: "Kraków",
    address: `Example Street ${i + 1}`,
    district: "Krowodrza",
    region: "małopolskie",
    description:
      "A synthetic rental for the local accessibility and loading fixture.",
    lat: 50.06 + i / 10000,
    lon: 19.94 + i / 10000,
    area_m2: 55,
    rooms: 2,
    floor: 2,
    rent_pln: 4000 + i * 20,
    fees_pln: 500,
    deposit_pln: null,
    commission_pln: i ? 0 : null,
    total_monthly_pln: 4500 + i * 20,
    advertiser_type: i === 1 ? "agency" : "private",
    property_type: "apartment",
    status: "active",
    images: [`${web}/t20-image/${n}.png`],
    amenities: [],
    is_demo: false,
    first_seen: timestamp,
    last_seen: timestamp,
    risk_score: 0,
    risk_flags: [],
    sources: [],
  };
});

test("Q13 costs distinguish unknown and zero and primary actions precede descriptions", async ({ page, context }, info) => {
  await allowOwned(context);
  await page.setViewportSize({ width: info.project.name === "mobile" ? 390 : 1440, height: 844 });
  let fees: number | null = null;
  let active = true;
  await page.route(`${api}/v1/listings/t20-001`, route => route.fulfill({ json: {
    ...homes[0], fees_pln: fees, total_monthly_pln: fees === null ? null : homes[0].rent_pln,
    status: active ? "active" : "inactive", description: "A long description. ".repeat(100),
    sources: [{ name: "fixture", url: "https://example.test/listing", rent_pln: 4000, fees_pln: fees, commission_pln: null, advertiser_type: "private", status: "active", last_checked: timestamp, match_reason: "fixture" }],
  }, headers: { "Access-Control-Allow-Origin": web } }));
  await page.goto("/");
  const open = () => page.getByRole("button", { name: `View ${first}`, exact: true }).click();
  const dialog = page.getByRole("dialog");
  await open();
  await expect(dialog.getByText("KNOWN COSTS · FEES UNSTATED", { exact: true })).toBeVisible();
  await expect(dialog.getByText("Not stated", { exact: true })).toHaveCount(2);
  await expect(dialog.getByRole("button", { name: "Message Synthetic owner" })).toHaveCount(0);
  const source = dialog.getByRole("button", { name: "View on fixture", exact: true });
  await expect(source).toBeVisible();
  for (const scale of [1, 2]) {
    if (scale === 2) await doubleText(page);
    await reachable(source);
    const order = await source.evaluate(node => {
      const root = node.closest("dialog")!;
      const description = Array.from(root.querySelectorAll("div")).find(item => item.textContent === "The space");
      return !!description && !!(node.compareDocumentPosition(description) & Node.DOCUMENT_POSITION_FOLLOWING);
    });
    expect(order).toBe(true);
    await reachable(dialog.getByRole("button", { name: "Save this home", exact: true }));
  }
  await page.screenshot({ path: info.outputPath("q13-actions.png") });
  await dialog.getByRole("button", { name: "Close dialog", exact: true }).click();
  fees = 0; await open();
  await expect(dialog.getByText("RENT + BUILDING FEES*", { exact: true })).toBeVisible();
  await expect(dialog.getByText("0 zł", { exact: true })).toBeVisible();
  await dialog.getByRole("button", { name: "Close dialog", exact: true }).click();
  active = false; await open();
  await expect(dialog.getByText(/Delisted · Kept/)).toBeVisible();
  await expect(source).toHaveCount(0);
  await expect(dialog.getByRole("link", { name: "Visit fixture" })).toBeDisabled();
});

test("Q10 delayed notification cannot reopen a closed listing", async ({ page, context }, info) => {
  await allowOwned(context);
  await page.route(`${api}/v1/me/notifications*`, route => route.fulfill({ json: {
    items: [{ id: "q10-notice", listing_id: homes[0].id, title: "Q10 notice", kind: "new_listing", created_at: timestamp, read_at: null, listing_status: "active" }],
    unread_count: 1, page: 1, page_size: 30, has_more: false, next_cursor: null,
  }, headers: { "Access-Control-Allow-Origin": web } }));
  await page.goto("/"); await register(page, `q10-notice-${info.project.name}@example.test`);
  await page.getByRole("button", { name: "Notifications", exact: true }).click();
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route(`${api}/v1/listings/${homes[0].id}`, async route => { await held; await route.fallback(); });
  const requested = page.waitForRequest(`${api}/v1/listings/${homes[0].id}`);
  await page.getByRole("button", { name: "View home", exact: true }).click(); await requested;
  await page.getByRole("button", { name: "Discover homes", exact: true }).click();
  await page.getByRole("button", { name: `View ${second}`, exact: true }).click();
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  const response = page.waitForResponse(`${api}/v1/listings/${homes[0].id}`);
  release(); await response;
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("Q04 feedback stays inside details and outside comparison controls", async ({ page, context }, info) => {
  await allowOwned(context);
  await page.goto("/");
  await register(page, `q04-${info.project.name}@example.test`);
  await page.getByRole("button", { name: `Compare ${first}`, exact: true }).click();
  await page.getByRole("button", { name: `Compare ${second}`, exact: true }).click();
  let fail = true;
  await page.route(`${api}/v1/me/favorites/t20-001`, route => fail
    ? route.fulfill({ status: 503, json: { detail: "private upstream text" }, headers: { "Access-Control-Allow-Origin": web } })
    : route.fallback());
  await page.getByRole("button", { name: `View ${first}`, exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Save this home", exact: true }).click();
  const error = dialog.getByRole("alert");
  await expect(error).toBeVisible();
  await expect(error).not.toContainText("private upstream text");
  await page.waitForTimeout(4700);
  await expect(error).toBeVisible();
  await doubleText(page);
  await reachable(dialog.getByRole("button", { name: "Dismiss message", exact: true }));
  await dialog.getByRole("button", { name: "Dismiss message", exact: true }).click();
  await expect(error).toHaveCount(0);
  fail = false;
  const save = dialog.getByRole("button", { name: "Save this home", exact: true });
  await save.click();
  await expect(dialog.getByRole("status")).toHaveText("A good find. Saved to your shortlist.");
  await expect(dialog.getByRole("status")).toHaveCount(1);
  await expect(dialog.getByRole("button", { name: "Remove from saved homes", exact: true })).toBeFocused();
  await dialog.getByRole("button", { name: "Close dialog", exact: true }).click();
  await reachable(page.getByRole("button", { name: "Compare homes →", exact: true }));
  await reachable(page.getByRole("button", { name: "Dismiss message", exact: true }));
  await page.screenshot({ path: info.outputPath("q04-feedback.png") });
});

test("Q14 comparison keeps editable selections and aligned captured metrics", async ({ page, context }, info) => {
  const blocked = await allowOwned(context);
  const narrow = info.project.name === "mobile";
  await page.setViewportSize({ width: narrow ? 320 : 1440, height: 850 });
  const longTitle = "CourtyardApartmentWithTwoRoomsAndASeparateKitchenNearCentralKrakow";
  const longSource = "IndependentSyntheticListingPublisherWithALongSourceName";
  const candidates: Listing[] = [
    { ...homes[0], title: longTitle, fees_pln: null, total_monthly_pln: 4000, sources: [{
      name: longSource, url: `${web}/synthetic-offer`, rent_pln: 4000, fees_pln: null,
      commission_pln: null, advertiser_type: "private", status: "active", last_checked: timestamp,
      match_reason: "Synthetic fixture",
    }] },
    { ...homes[1], images: [] },
    { ...homes[2], status: "inactive" },
    homes[3],
  ];
  const headers = { "Access-Control-Allow-Origin": web };
  let updated = false;
  let detailRequests = 0;
  await page.route(`${api}/v1/listings?*`, route => route.fulfill({
    json: {
      items: updated ? [{ ...candidates[0], rent_pln: 7700, total_monthly_pln: 7700 }, ...candidates.slice(1)] : candidates,
      total: candidates.length, page: 1, page_size: 24, engine: "fixture",
    },
    headers,
  }));
  await page.route(`${api}/v1/listings/${candidates[0].id}`, route => {
    detailRequests++;
    return route.fulfill({ status: 503, json: {}, headers });
  });

  await page.goto("/", { waitUntil: "commit" });
  for (const home of candidates) await button(page, `Compare ${home.title}`).click();
  await expect(page.getByText("Compare up to three homes at a time.", { exact: true })).toBeVisible();
  await button(page, "Dismiss message").click();
  const openCompare = button(page, "Compare homes →");
  const dialog = page.getByRole("dialog", { name: "Side by side" });

  await button(page, `View ${longTitle}`).click();
  const detail = page.getByRole("dialog", { name: "A closer look" });
  await expect(detail.getByText(/Could not load current details/)).toBeVisible();
  await button(detail, "Close dialog").click();
  updated = true;
  await button(page, "Find a home →").click();
  await expect(page.getByText(/7700 zł/).first()).toBeVisible();

  await openCompare.click();
  await expect(dialog).toBeVisible();
  if (narrow) await page.screenshot({ path: info.outputPath("q14-comparison-320px.png") });
  await expect(dialog.getByText(/Listing snapshots from when each home was added/)).toBeVisible();
  expect(detailRequests).toBe(1);
  const table = dialog.getByRole("table", { name: "Home comparison" });
  const row = (name: string) => table.getByRole("row").filter({
    has: page.getByRole("rowheader", { name, exact: true }),
  });
  const base = row("Base rent").getByRole("cell");
  await expect(base).toHaveText(["4000 zł", "4020 zł", "4040 zł"]);
  await expect(row("Availability when selected").getByRole("cell")).toHaveText(["Listed", "Listed", "Delisted"]);
  await expect(row("Building fees").getByRole("cell").first()).toHaveText("Not stated");
  await expect(row("Known monthly costs").getByRole("cell").first()).toHaveText("4000 zł");
  await expect(row("Commission").getByRole("cell").first()).toHaveText("Not stated");
  await expect(row("Sources").getByText(longSource)).toBeVisible();
  await expect(table.getByText("No photo available")).toHaveCount(1);
  const cells = await base.evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().toJSON()));
  const widest = await table.boundingBox();
  expect(widest).not.toBeNull();
  for (const [index, cell] of cells.entries()) {
    expect(cell.top).toBeCloseTo(cells[0].top, 1);
    expect(cell.left).toBeGreaterThanOrEqual(widest!.x);
    expect(cell.right).toBeLessThanOrEqual(widest!.x + widest!.width + 1);
    if (index > 0) expect(cell.left).toBeGreaterThan(cells[index - 1].right);
  }
  const sources = await row("Sources").getByRole("cell").first().evaluate(node => ({
    width: node.clientWidth, scrollWidth: node.scrollWidth,
  }));
  expect(sources.scrollWidth).toBeLessThanOrEqual(sources.width + 1);

  await button(dialog, "Close dialog").click();
  await button(page, `Remove ${candidates[1].title} from comparison`).click();
  await expect(page.getByText("2 of 3 selected", { exact: true })).toBeVisible();
  await openCompare.click();
  await expect(base).toHaveText(["4000 zł", "4040 zł"]);
  expect(detailRequests).toBe(1);
  expect(blocked).toEqual([]);
});

test("Q20 waits for favorite confirmation and distinguishes the saved availability filter", async ({ page, context }, info) => {
  const blocked = await allowOwned(context);
  const headers = { "Access-Control-Allow-Origin": web };
  let failSave!: () => void;
  const firstSave = new Promise<void>(resolve => { failSave = resolve; });
  let finishRemoval!: () => void;
  const removal = new Promise<void>(resolve => { finishRemoval = resolve; });
  let saves = 0;
  let removals = 0;
  await page.route(`${api}/v1/me/favorites/${homes[0].id}`, async route => {
    if (route.request().method() === "PUT" && ++saves === 1) {
      await firstSave;
      return route.fulfill({ status: 503, json: { detail: "synthetic private error" }, headers });
    }
    if (route.request().method() === "DELETE") {
      removals++;
      await removal;
    }
    return route.fallback();
  });
  await page.goto("/");
  await register(page, `q20-favorite-${info.project.name}@example.test`);
  const save = button(page, `Save ${first}`);
  const details = page.getByRole("dialog", { name: "A closer look" });

  await save.evaluate(node => { (node as HTMLElement).click(); (node as HTMLElement).click(); });
  try {
    await expect.poll(() => saves).toBe(1);
    const pending = button(page, `Saving ${first}`);
    await expect(pending).toBeDisabled();
    await expect(pending).toHaveAttribute("aria-pressed", "false");
    await button(page, `View ${first}`).click();
    await expect(button(details, "Saving…")).toBeDisabled();
  } finally {
    failSave();
  }
  await expect(details.getByRole("alert")).toHaveText("Could not save this home.");
  await expect(button(details, "Save this home")).toBeEnabled();
  if (info.project.name === "mobile") {
    await button(details, "Retry save").scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath("q20-save-retry.png") });
  }
  await button(details, "Close dialog").click();
  await expect(button(page, "Retry save")).toBeVisible();
  await button(page, `View ${first}`).click();
  await button(details, "Retry save").click();
  await expect(button(details, "Remove from saved homes")).toBeEnabled();
  expect(saves).toBe(2);
  await button(details, "Close dialog").click();
  await button(page, "Saved homes").click();
  const delisted = "T20 delisted favorite";
  await expect(button(page, first)).toBeVisible();
  await expect(button(page, delisted)).toBeVisible();

  await button(page, "Unavailable").click();
  await expect(button(page, first)).toHaveCount(0);
  await button(page, delisted).click();
  await expect(details.getByText(/Delisted · Kept in your saved homes/)).toBeVisible();
  await button(details, "Close dialog").click();
  await button(page, "Available").click();
  await expect(button(page, delisted)).toHaveCount(0);
  await button(page, `Unsave ${first}`).click();
  try {
    await expect.poll(() => removals).toBe(1);
    const pending = button(page, `Removing ${first}`);
    await expect(pending).toBeDisabled();
    await expect(pending).toHaveAttribute("aria-pressed", "true");
    await expect(button(page, first)).toBeVisible();
  } finally {
    finishRemoval();
  }
  await expect(button(page, first)).toHaveCount(0);
  await expect(page.getByText("No saved homes match this availability filter.", { exact: true })).toBeVisible();
  await expect(page.getByText("Your shortlist starts here.", { exact: true })).toHaveCount(0);
  await button(page, "Show all saved homes").click();
  await expect(button(page, delisted)).toBeVisible();
  await button(page, `Unsave ${delisted}`).click();
  await expect(page.getByText("Your shortlist starts here.", { exact: true })).toBeVisible();
  expect(blocked).toEqual([]);
});

test("Q20 discards a pending favorite when the account changes", async ({ page, context }, info) => {
  const blocked = await allowOwned(context);
  let finish!: () => void;
  const pending = new Promise<void>(resolve => { finish = resolve; });
  const endpoint = `${api}/v1/me/favorites/${homes[0].id}`;
  await page.route(endpoint, async route => {
    await pending;
    return route.fulfill({ status: 503, json: {}, headers: { "Access-Control-Allow-Origin": web } });
  });
  await page.goto("/");
  await register(page, `q20-former-${info.project.name}@example.test`);
  try {
    await button(page, `Save ${first}`).click();
    await expect(button(page, `Saving ${first}`)).toBeDisabled();
    await button(page, "Account").click();
    await button(page, "Sign out").click();
    await expect(button(page, "Sign in")).toBeVisible();
    await register(page, `q20-new-${info.project.name}@example.test`);
    const response = page.waitForResponse(endpoint);
    finish();
    expect((await response).status()).toBe(503);
    await expect(button(page, `Save ${first}`)).toBeEnabled();
    await expect(button(page, "Retry save")).toHaveCount(0);
    await expect(page.getByText("Could not save this home.", { exact: true })).toHaveCount(0);
  } finally {
    finish();
  }
  expect(blocked).toEqual([]);
});

test("Q11 broken photos keep their frame and recover on source changes", async ({ page, context }, info) => {
  const blocked = await allowOwned(context);
  await page.route(`${web}/t20-image/001.png`, route => route.fulfill({ status: 404, body: "missing" }));
  await page.route(`${web}/t20-image/003.png`, route => route.fulfill({ contentType: "image/png", body: "not an image" }));
  await page.route(`${api}/v1/listings/t20-001`, route => route.fulfill({
    json: { ...homes[0], images: [homes[0].images[0], homes[1].images[0], homes[2].images[0]] },
    headers: { "Access-Control-Allow-Origin": web },
  }));
  await page.goto("/", { waitUntil: "commit" });
  await expect(page.getByTestId("listing-photo-fallback").first()).toBeVisible();
  const cardFrame = await page.getByTestId("listing-photo-fallback").first().boundingBox();
  expect(cardFrame?.height).toBeGreaterThanOrEqual(202);
  await page.getByRole("button", { name: `View ${first}`, exact: true }).click();
  const dialog = page.getByRole("dialog");
  const frame = dialog.getByTestId("gallery-photo-frame");
  await expect(frame.getByTestId("listing-photo-fallback")).toBeVisible();
  const failedFrame = await frame.getByTestId("listing-photo-fallback").boundingBox();
  await dialog.getByRole("button", { name: "Photo 2", exact: true }).click();
  const loaded = frame.locator('img[data-testid="listing-photo"]');
  await expect(loaded).toBeVisible();
  await expect.poll(() => loaded.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0);
  const loadedFrame = await loaded.boundingBox();
  expect(Math.abs(loadedFrame!.height - failedFrame!.height)).toBeLessThan(1);
  await dialog.getByRole("button", { name: "Photo 3", exact: true }).click();
  await expect(frame.getByTestId("listing-photo-fallback")).toBeVisible();
  await dialog.getByRole("button", { name: "Photo 2", exact: true }).click();
  await expect(loaded).toBeVisible();
  await dialog.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("button", { name: `Compare ${first}`, exact: true }).click();
  await page.getByRole("button", { name: `Compare ${second}`, exact: true }).click();
  await page.getByRole("button", { name: "Compare homes →", exact: true }).click();
  await expect(dialog.getByTestId("listing-photo-fallback")).toBeVisible();
  await page.screenshot({ path: info.outputPath("q11-photo-fallback.png"), fullPage: false });
  expect(blocked).toEqual([]);
});

test("Q12 gallery bounds photo loading and keeps keyboard navigation inside its controls", async ({ page, context }, info) => {
  const blocked = await allowOwned(context);
  if (info.project.name === "mobile") await page.setViewportSize({ width: 320, height: 800 });
  const photoUrl = (number: number) => `${web}/t20-image/gallery-${number}.png`;
  const urls = Array.from({ length: 30 }, (_, index) => photoUrl(index + 1));
  const requested = new Set<string>();
  page.on("request", request => {
    if (urls.includes(request.url())) requested.add(request.url());
  });
  await page.route(photoUrl(6), route => route.fulfill({ status: 404, body: "missing" }));
  const detail = (home: Listing, images: string[]) => page.route(`${api}/v1/listings/${home.id}`, route => route.fulfill({
    json: { ...home, images },
    headers: { "Access-Control-Allow-Origin": web },
  }));
  await detail(homes[0], urls);
  await detail(homes[2], []);
  await page.goto("/", { waitUntil: "commit" });
  const dialog = page.getByRole("dialog", { name: "A closer look" });
  const frame = dialog.getByTestId("gallery-photo-frame");
  const previous = button(dialog, "Previous photo");
  const next = button(dialog, "Next photo");
  const closeDialog = button(dialog, "Close dialog");
  const position = (index: number, count: number) => dialog.getByText(`Photo ${index} of ${count}`, { exact: true });
  const thumbnails = dialog.getByRole("button", { name: /^Photo \d+$/ });
  const thumbnail = (number: number) => button(dialog, `Photo ${number}`);

  await button(page, first).click();
  await expect(position(1, 30)).toBeVisible();
  await expect(previous).toBeDisabled();
  await expect(thumbnails).toHaveCount(5);
  await expect(thumbnail(1)).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => [...requested].sort()).toEqual(urls.slice(0, 5).sort());
  await expect(thumbnails.last()).toBeInViewport({ ratio: 1 });
  if (info.project.name === "mobile")
    await page.screenshot({ path: info.outputPath("q12-gallery-320px.png") });

  await closeDialog.focus();
  await page.keyboard.press("ArrowRight");
  await expect(position(1, 30)).toBeVisible();
  await next.focus();
  await page.keyboard.press("ArrowRight");
  await expect(position(2, 30)).toBeVisible();
  await expect(next).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(position(1, 30)).toBeVisible();

  await thumbnail(1).focus();
  for (let number = 2; number <= 6; number++) {
    await page.keyboard.press("ArrowRight");
    await expect(thumbnail(number)).toBeFocused();
  }
  await expect(position(6, 30)).toBeVisible();
  await expect(frame.getByText("Photo unavailable", { exact: true })).toBeVisible();
  await expect(thumbnails).toHaveCount(5);
  expect([...requested].every(url => urls.indexOf(url) < 8)).toBe(true);
  await next.click();
  await expect(frame.locator("img")).toHaveAttribute("src", photoUrl(7));
  await expect.poll(() => frame.locator("img").evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0);

  for (let number = 9; number <= 29; number += 2) await thumbnail(number).click();
  await next.click();
  await expect(position(30, 30)).toBeVisible();
  await expect(next).toBeDisabled();
  await expect(thumbnail(30)).toHaveAttribute("aria-pressed", "true");
  await closeDialog.click();

  await button(page, second).click();
  await expect(position(1, 1)).toBeVisible();
  await expect(frame.locator("img")).toHaveAttribute("src", homes[1].images[0]);
  await expect(previous).toHaveCount(0);
  await expect(next).toHaveCount(0);
  await expect(thumbnails).toHaveCount(0);
  await closeDialog.click();
  await button(page, homes[2].title).click();
  await expect(dialog.getByText("No photos available", { exact: true })).toBeVisible();
  await expect(frame).toHaveCount(0);
  await expect(next).toHaveCount(0);
  expect(blocked).toEqual([]);
});

test("Q17 rent history is readable for empty, single, flat and 24-month samples", async ({ page, context }, info) => {
  const blocked = await allowOwned(context);
  const narrow = info.project.name === "mobile";
  await page.setViewportSize({ width: narrow ? 320 : 1440, height: 900 });
  const methodology = "Synthetic methodology. Months without observations are not interpolated.";
  const points: History["points"] = Array.from({ length: 24 }, (_, index) => ({
    month: `${2024 + Math.floor(index / 12)}-${String(index % 12 + 1).padStart(2, "0")}`,
    median_rent_pln: 4000 + 40 * index,
    median_per_m2: 69,
    sample_size: index === 23 ? 12 : 50,
    is_demo: index === 3,
  }));
  const historyRequests: URLSearchParams[] = [];
  const headers = { "Access-Control-Allow-Origin": web };
  await page.route(`${api}/v1/market/history?*`, route => {
    const params = new URL(route.request().url()).searchParams;
    historyRequests.push(params);
    const district = params.get("district");
    let sample = points;
    if (params.get("city") === "Warszawa") sample = [points[23]];
    else if (district === "Stare Miasto") sample = [];
    else if (district === "Krowodrza") sample = points.map(point => ({ ...point, median_rent_pln: 4200 }));
    return route.fulfill({ json: { points: sample, methodology }, headers });
  });
  await page.route(`${api}/v1/market/summary?*`, route => {
    const warsaw = new URL(route.request().url()).searchParams.get("city") === "Warszawa";
    const summary: Summary = {
      homes: 100, source_listings: 100, duplicates_removed: 0, private_homes: 100,
      median_rent_pln: 4000, demo: false, cities: ["Kraków", "Warszawa"],
      districts: warsaw ? ["Mokotów"] : ["Stare Miasto", "Krowodrza"],
    };
    return route.fulfill({ json: summary, headers });
  });
  const history: Listing["history"] = Array.from({ length: 12 }, (_, index) => ({
    at: `2026-01-${String(index + 1).padStart(2, "0")}T12:00:00Z`,
    rent_pln: 12000 + 100 * index,
    fees_pln: 500,
    status: "active",
  }));
  await page.route(`${api}/v1/listings/${homes[0].id}`, route => route.fulfill({
    json: { ...homes[0], history }, headers,
  }));

  await page.goto("/", { waitUntil: "commit" });
  const insights = button(page, "Rent insights");
  await insights.click();
  const chart = page.getByRole("img", { name: /Monthly median (base|asking) rent chart/ });
  await chart.scrollIntoViewIfNeeded();
  if (narrow) await page.screenshot({ path: info.outputPath("q17-insights-320px.png") });
  await expect(page.getByText(/Jan 2024 to Dec 2025 · 24 observed months/)).toBeVisible();
  await expect(page.getByText("Includes illustrative data", { exact: true })).toBeVisible();
  await expect(page.getByText("Some months have fewer than 30 observed homes.", { exact: true })).toBeVisible();
  await expect(page.getByText("CHANGE IN OBSERVED SAMPLE MEDIANS", { exact: true })).toBeVisible();
  await expect(page.getByText("+23.0%", { exact: true })).toBeVisible();
  await expect(page.getByText(methodology, { exact: true })).toBeVisible();
  const labels = await chart.locator("text").evaluateAll(nodes =>
    nodes.filter(node => /[A-Z][a-z]+ \d{4}/.test(node.textContent ?? "")).map(node => ({
      label: node.textContent,
      font: parseFloat(getComputedStyle(node).fontSize),
      left: node.getBoundingClientRect().left,
      right: node.getBoundingClientRect().right,
    })),
  );
  expect(labels).toHaveLength(narrow ? 2 : 5);
  expect(labels[0].label).toBe("Jan 2024");
  expect(labels.at(-1)?.label).toBe("Dec 2025");
  for (const [index, label] of labels.entries()) {
    expect(label.font).toBeGreaterThanOrEqual(12);
    expect(label.left).toBeGreaterThanOrEqual(0);
    expect(label.right).toBeLessThanOrEqual(narrow ? 320 : 1440);
    if (index > 0) expect(label.left).toBeGreaterThan(labels[index - 1].right);
  }
  await expect(chart.locator("circle")).toHaveCount(24);
  for (const point of points) {
    const month = new Date(`${point.month}-01T00:00:00Z`).toLocaleDateString("en-GB", {
      month: "short", year: "numeric", timeZone: "UTC",
    });
    await expect(page.getByText(month, { exact: true }).last()).toBeVisible();
  }

  await button(page, "Krowodrza").click();
  await expect(page.getByText("0.0%", { exact: true })).toBeVisible();
  const flatY = await chart.locator("circle").evaluateAll(nodes => nodes.map(node => node.getAttribute("cy")));
  expect(new Set(flatY).size).toBe(1);
  await button(page, "Stare Miasto").click();
  await expect(page.getByText(/No observations for this area yet/)).toBeVisible();
  await expect(chart).toHaveCount(0);
  await expect(page.getByText("CHANGE IN OBSERVED SAMPLE MEDIANS", { exact: true })).toHaveCount(0);

  await button(page, "Discover homes").click();
  await button(page, first).click();
  const dialog = page.getByRole("dialog", { name: "A closer look" });
  await expect(dialog.getByText("Showing the latest 8 of 12 observations.", { exact: true })).toBeVisible();
  await expect(dialog.getByText("12 Jan 2026", { exact: true })).toBeVisible();
  await expect(dialog.getByText("5 Jan 2026", { exact: true })).toBeVisible();
  await expect(dialog.getByText("4 Jan 2026", { exact: true })).toHaveCount(0);
  await expect(dialog.getByText(/13\s100 zł · active/)).toBeVisible();
  await button(dialog, "Close dialog").click();

  const city = page.getByRole("textbox", { name: "City", exact: true });
  await city.fill("Warszawa");
  await city.press("Enter");
  await insights.click();
  await expect(page.getByText(/Dec 2025 · One observed month/)).toBeVisible();
  await expect(chart.locator("circle")).toHaveCount(1);
  await expect(page.getByText("CHANGE IN OBSERVED SAMPLE MEDIANS", { exact: true })).toHaveCount(0);
  await expect(button(page, "Whole city")).toHaveAttribute("aria-pressed", "true");
  await expect(button(page, "Stare Miasto")).toHaveCount(0);
  expect(historyRequests.at(-1)?.get("city")).toBe("Warszawa");
  expect(historyRequests.at(-1)?.get("district")).toBeFalsy();
  expect(blocked).toEqual([]);
});

test("Q15 retry recovers the map component and engine chunks independently", async ({ page, context }, info) => {
  const blocked = await allowOwned(context);
  let allowMap = false;
  let allowEngine = false;
  let mapAttempts = 0;
  let engineAttempts = 0;
  await page.route(/\/PropertyMap-[^/]+\.js$/, route => {
    mapAttempts++;
    return allowMap ? route.continue() : route.abort("failed");
  });
  await page.route(/\/leaflet-src-[^/]+\.js$/, route => {
    engineAttempts++;
    return allowEngine ? route.continue() : route.abort("failed");
  });
  await page.goto("/", { waitUntil: "commit" });
  if (info.project.name === "mobile") await button(page, "Map view").click();
  const map = page.getByRole("region", { name: "Map of rental homes" });
  const failure = page.getByRole("alert").filter({ hasText: "The map couldn't load." });
  await expect(failure).toBeVisible();
  await expect(map).toHaveCount(0);
  expect(mapAttempts).toBe(1);
  expect(engineAttempts).toBe(0);

  allowMap = true;
  await button(page, "Retry map").click();
  await expect.poll(() => engineAttempts).toBe(1);
  await expect(failure).toBeVisible();
  expect(mapAttempts).toBe(2);
  allowEngine = true;
  await button(page, "Retry map").click();
  await expect(map.locator("img.leaflet-tile-loaded").first()).toBeVisible();
  await expect(failure).toHaveCount(0);
  await expect(map.getByRole("link", { name: "OpenStreetMap" })).toBeVisible();
  expect(mapAttempts).toBe(2);
  expect(engineAttempts).toBe(2);
  expect(blocked).toEqual([]);
});

test("Q15 tile recovery preserves the area and offers list and owner coordinate fallbacks", async ({ page, context }, info) => {
  const blocked = await allowOwned(context);
  let failTiles = true;
  let tileAttempts = 0;
  // The loopback fixture serves one tile URL. Give requests distinct URLs as
  // with a real tile grid so success and failure batches cannot share a decode.
  await page.addInitScript(() => {
    let sequence = 0;
    const source = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, "src")!;
    Object.defineProperty(HTMLImageElement.prototype, "src", {
      ...source,
      set(value: string) {
        const url = new URL(value, location.href);
        if (url.origin === location.origin && url.pathname === "/tile.png") {
          url.searchParams.set("fixture-tile", String(++sequence));
          source.set!.call(this, url.href);
        } else {
          source.set!.call(this, value);
        }
      },
    });
  });
  await page.route(url => url.origin === web && url.pathname === "/tile.png", route => {
    tileAttempts++;
    return failTiles && tileAttempts % 8 !== 1 ? route.fulfill({ status: 503 }) : route.continue();
  });
  await page.goto("/", { waitUntil: "commit" });
  const direct = button(page, "Direct offers");
  await direct.click();
  if (info.project.name === "mobile") await button(page, "Map view").click();
  const map = page.getByRole("region", { name: "Map of rental homes" });
  const tileFailure = page.getByRole("alert").filter({ hasText: "Map tiles couldn't load." });
  await expect(tileFailure).toBeVisible();
  expect(tileAttempts).toBeGreaterThan(1);
  const firstPane = await map.locator(".leaflet-map-pane").elementHandle();

  await button(page, "Enter area coordinates").click();
  const editor = page.getByRole("dialog", { name: "Search area coordinates" });
  for (const [lat, lon] of [["50.03", "19.90"], ["50.09", "19.92"], ["50.05", "20.00"]]) {
    await editor.getByLabel("Latitude", { exact: true }).fill(lat);
    await editor.getByLabel("Longitude", { exact: true }).fill(lon);
    await button(editor, "Add vertex").click();
  }
  const search = page.waitForRequest(request => new URL(request.url()).searchParams.has("polygon"));
  await button(editor, "Use this area").click();
  const query = new URL((await search).url()).searchParams;
  expect(query.get("advertiser")).toBe("private");
  expect(JSON.parse(query.get("polygon")!)).toEqual([[19.90, 50.03], [19.92, 50.09], [20.00, 50.05]]);
  await expect(button(page, "Drawn area ×")).toBeVisible();
  await expect(tileFailure).toBeVisible();
  if (info.project.name === "mobile")
    await page.screenshot({ path: info.outputPath("q15-tile-failure.png") });

  failTiles = false;
  await button(page, "Retry map").click();
  await expect(map.locator("img.leaflet-tile-loaded").first()).toBeVisible();
  await expect(tileFailure).toHaveCount(0);
  await expect(map.getByRole("link", { name: "OpenStreetMap" })).toBeVisible();
  await expect(map.locator(".leaflet-map-pane")).toHaveCount(1);
  expect(await firstPane.evaluate(node => node.isConnected)).toBe(false);
  await expect(button(page, "Drawn area ×")).toBeVisible();
  await expect(direct).toHaveAttribute("aria-pressed", "true");
  await button(page, "Redraw area").click();
  await map.click({ position: { x: 90, y: 120 } });
  await expect(page.getByText(/1\/64 points/)).toBeVisible();
  await button(page, "Cancel drawing").click();

  failTiles = true;
  await map.getByRole("button", { name: "Zoom in", exact: true }).click();
  await expect(tileFailure).toBeVisible();
  await button(page, "Show homes as a list").click();
  await expect(map).toHaveCount(0);
  await expect(button(page, first)).toBeVisible();
  await expect(button(page, "Drawn area ×")).toBeVisible();
  await expect(direct).toHaveAttribute("aria-pressed", "true");

  await register(page, `q15-owner-${info.project.name}@example.test`);
  await button(page, "Account").click();
  await button(page, "My rental adverts").click();
  const desk = page.getByRole("dialog", { name: "Your rental desk." });
  await desk.getByLabel("PUBLIC NAME").fill("Synthetic Q15 owner");
  await button(desk, "Save profile").click();
  await button(desk, "Create rental advert").click();
  await expect(desk.getByText("Map tiles couldn't load.", { exact: true })).toBeVisible();
  await expect(desk.getByText("Enter latitude and longitude in the location fields.", { exact: true })).toBeVisible();
  await desk.getByLabel("Location latitude").fill("50,0647");
  await desk.getByLabel("Location longitude").fill("19,945");
  await expect(desk.getByText("Location set", { exact: true })).toBeVisible();
  expect(blocked).toEqual([]);
});

async function allowOwned(context: BrowserContext, fixture = true) {
  const blocked: string[] = [];
  const favorites = new Map<string, Listing>([
    [
      "t20-inactive",
      {
        ...homes[1],
        id: "t20-inactive",
        title: "T20 delisted favorite",
        status: "inactive",
      },
    ],
  ]);
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (![web, api, auth].includes(url.origin) && url.protocol !== "data:") {
      blocked.push(url.origin);
      return route.abort("blockedbyclient");
    }
    const path = url.pathname;
    if (fixture && url.origin === web && path.startsWith("/t20-image/"))
      return route.fulfill({ contentType: "image/png", body: tile });
    if (!fixture || url.origin !== api) return route.continue();

    const json = async (payload: object) =>
      route.fulfill({
        json: payload,
        headers: {
          "Access-Control-Allow-Origin": web,
          "Access-Control-Allow-Credentials": "true",
        },
      });
    if (route.request().method() === "OPTIONS") return route.continue();
    if (path === "/v1/listings") {
      const min = Number(url.searchParams.get("min_price") || 0);
      const page = Number(url.searchParams.get("page") || 1);
      const size = Number(url.searchParams.get("page_size") || 24);
      const matches = homes.filter((home) => home.rent_pln >= min);
      return json({
        items: matches.slice((page - 1) * size, page * size),
        total: matches.length,
        page,
        page_size: size,
        engine: "sql",
      });
    }
    const home = homes.find((item) => path === `/v1/listings/${item.id}`);
    if (home) return json(home);
    if (path === "/v1/me/favorites")
      return json({ items: [...favorites.values()] });
    if (path.startsWith("/v1/me/favorites/t20-")) {
      const item = homes.find((home) => path.endsWith(home.id));
      if (!item) return route.continue();
      if (route.request().method() === "PUT") favorites.set(item.id, item);
      else favorites.delete(item.id);
      return json({ saved: favorites.has(item.id) });
    }
    if (path === "/v1/me/listing-state")
      return json({ seen_ids: [homes[0].id] });
    if (path === "/v1/me/seen/t20-001") return json({ seen: true });
    if (path === "/v1/me/conversations")
      return json({
        next_cursor: null,
        items: [
          {
            id: "t20-thread",
            title: "Fixture conversation",
            listing_id: null,
            updated_at: timestamp,
            unread_count: 0,
            blocked: false,
            can_unblock: false,
          },
        ],
      });
    if (path === "/v1/me/conversations/t20-thread")
      return json({
        id: "t20-thread",
        items: [],
        next_cursor: null,
        blocked: false,
        can_unblock: false,
      });
    return route.continue();
  });
  return blocked;
}

function button(scope: Page | Locator, name: string) {
  return scope.getByRole("button", { name, exact: true });
}

async function keyboardTo(page: Page, target: Locator) {
  await expect(target).toBeVisible();
  for (let i = 0; i < 150; i++) {
    if (await target.evaluate((node) => node === document.activeElement))
      return;
    await page.keyboard.press("Tab");
  }
  await expect(target).toBeFocused();
}

async function keyActivate(page: Page, target: Locator) {
  await keyboardTo(page, target);
  await page.keyboard.press("Enter");
}

async function keyText(page: Page, target: Locator, value: string) {
  await keyboardTo(page, target);
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.insertText(value);
}

async function close(page: Page, dialog: Locator) {
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
}

async function reachable(target: Locator) {
  await target.scrollIntoViewIfNeeded();
  await expect(target).toBeInViewport({ ratio: 0.9 });
  const box = await target.boundingBox();
  expect(box?.x).toBeGreaterThanOrEqual(-1);
  expect(box!.x + box!.width).toBeLessThanOrEqual(
    target.page().viewportSize()!.width + 1,
  );
}

// Chromium's page zoom also changes CSS viewport width. Scale px text and
// line-height independently of viewport size to exercise 200% text alone.
async function doubleText(page: Page) {
  await page.evaluate(() => {
    const sheet = document.createElement("style");
    sheet.id = "t20-text-only";
    document.head.append(sheet);
    let previous = "";
    function collect(rules: CSSRuleList): string[] {
      return Array.from(rules).flatMap((rule) => {
        if (rule instanceof CSSMediaRule)
          return matchMedia(rule.conditionText).matches
            ? collect(rule.cssRules)
            : [];
        if (!(rule instanceof CSSStyleRule)) return [];
        const styles = ["font-size", "line-height"].flatMap((property) => {
          const value = rule.style.getPropertyValue(property).trim();
          return /^[\d.]+px$/.test(value)
            ? [`${property}: ${parseFloat(value) * 2}px !important;`]
            : [];
        });
        return styles.length
          ? [`${rule.selectorText} {${styles.join("")}}`]
          : [];
      });
    }
    function refresh() {
      if (!sheet.isConnected) return;
      const generated = Array.from(document.styleSheets)
        .filter((source) => source.ownerNode !== sheet)
        .flatMap((source) => collect(source.cssRules));
      const inline = new Set<string>();
      for (const element of Array.from(
        document.querySelectorAll<HTMLElement>("[style]"),
      )) {
        for (const [property, name] of [
          ["font-size", "size"],
          ["line-height", "leading"],
        ]) {
          const value = element.style.getPropertyValue(property).trim();
          const attr = `data-t20-${name}`;
          if (/^[\d.]+px$/.test(value)) {
            if (element.getAttribute(attr) !== value)
              element.setAttribute(attr, value);
            inline.add(
              `[${attr}="${value}"][style] {${property}: ${parseFloat(value) * 2}px !important;}`,
            );
          } else if (element.hasAttribute(attr)) {
            element.removeAttribute(attr);
          }
        }
      }
      const output = [...generated, ...inline].join("\n");
      if (output !== previous) sheet.textContent = previous = output;
      requestAnimationFrame(refresh);
    }
    refresh();
  });
}

async function register(page: Page, email: string) {
  await button(page, "Sign in").click();
  await button(page, "New here? Create a free account").click();
  await page.getByLabel("EMAIL", { exact: true }).fill(email);
  await page
    .getByLabel("PASSWORD", { exact: true })
    .fill("synthetic-t20-password-123");
  await button(page, "Create account").click();
  await expect(button(page, "Account")).toBeVisible();
}

test("T20-TC01 primary screens and validation at normal and 200% text size", async ({
  page,
  context,
}, info) => {
  test.setTimeout(180_000);
  const blocked = await allowOwned(context);
  const widths = info.project.name === "desktop" ? [768, 1440] : [320, 390];
  await page.setViewportSize({ width: widths[0], height: 800 });
  await page.goto("/");
  const signIn = button(page, "Sign in");
  await reachable(signIn);
  await signIn.click();
  const authDialog = page.getByRole("dialog", { name: "Welcome back." });
  await reachable(button(authDialog, "Sign in"));
  await close(page, authDialog);
  await register(page, `t20-${info.project.name}@example.test`);

  for (const width of widths) {
    await page.setViewportSize({ width, height: 800 });
    for (const scale of [1, 2]) {
      await test.step(`${width}px · ${scale * 100}% text`, async () => {
        const overflow = async () => {
          const layout = await page.evaluate(() => {
            const root = document.documentElement;
            return {
              width: root.scrollWidth,
              offenders:
                root.scrollWidth > root.clientWidth
                  ? Array.from(root.querySelectorAll("div,button,input"))
                      .filter(
                        (node) =>
                          node.getBoundingClientRect().right >
                            root.clientWidth + 1 &&
                          !node.closest(".leaflet-container"),
                      )
                      .slice(0, 10)
                      .map((node) => node.textContent?.trim().slice(0, 80))
                  : [],
            };
          });
          expect(
            layout.width,
            `Overflow candidates: ${layout.offenders.join(", ")}`,
          ).toBe(width);
        };
        const heading = page.getByRole("heading", {
          name: "Good places. Clear choices.",
        });
        const base = await heading.evaluate((el) =>
          parseFloat(getComputedStyle(el).fontSize),
        );
        if (scale === 2) {
          await doubleText(page);
          await expect
            .poll(() =>
              heading.evaluate((el) =>
                parseFloat(getComputedStyle(el).fontSize),
              ),
            )
            .toBe(base * 2);
        }
        await overflow();
        await reachable(
          page.getByRole("textbox", { name: "City", exact: true }),
        );
        await reachable(button(page, "Find a home →"));
        await reachable(button(page, "More filters"));
        await page.screenshot({ path: info.outputPath(`q01-controls-${width}-${scale}.png`) });
        await button(page, "More filters").click();
        const filter = page.getByRole("dialog", { name: "A home that fits." });
        const min = filter.getByLabel("MIN RENT · PLN");
        await min.fill("5000");
        const max = filter.getByLabel("RENT BELOW · PLN");
        await max.fill("4000");
        await button(filter, "Show matching homes").click();
        await expect(min).toHaveAttribute("aria-invalid", "true");
        await expect(min).toHaveAccessibleDescription(
          "Minimum rent must be below the exclusive rent maximum.",
        );
        await expect(max).toHaveAttribute("aria-invalid", "true");
        await expect(max).toHaveAccessibleDescription(
          "Rent maximum must be above minimum rent.",
        );
        await reachable(button(filter, "Show matching homes"));
        await reachable(button(filter, "Close dialog"));
        await overflow();
        await close(page, filter);

        await button(page, "Map view").click();
        await reachable(button(page, "Enter area coordinates"));
        await expect(
          page.getByRole("region", { name: "Map of rental homes" }),
        ).toBeVisible();
        await overflow();
        await button(page, "List view").click();

        await button(page, first).click();
        const detail = page.getByRole("dialog", { name: "A closer look" });
        await reachable(button(detail, "Save this home"));
        await reachable(button(detail, "Report a concern"));
        await reachable(button(detail, "Close dialog"));
        await overflow();
        await button(detail, "Report a concern").click();
        const report = page.getByRole("dialog", {
          name: "Something worth checking?",
        });
        await reachable(report.getByLabel("WHAT DID YOU NOTICE?"));
        await reachable(button(report, "Submit report"));
        await close(page, report);
        await close(page, detail);

        await button(page, "Saved homes").click();
        await reachable(button(page, "Unsave T20 delisted favorite"));
        await expect(page.getByText("DELISTED", { exact: true })).toBeVisible();
        await overflow();

        await button(page, "Notifications").click();
        await reachable(button(page, "Enable email alerts"));
        await reachable(button(page, "Enable device alerts"));
        await overflow();

        await button(page, "Account").click();
        const account = page.getByRole("dialog", { name: "Your account." });
        await button(account, "Delete account…").click();
        await reachable(account.getByLabel("CURRENT PASSWORD", { exact: true }));
        await reachable(button(account, "Permanently delete my account"));
        await reachable(button(account, "Close dialog"));
        await overflow();
        await button(account, "My rental adverts").click();
        const desk = page.getByRole("dialog", { name: "Your rental desk." });
        const create = button(desk, "Create rental advert");
        if (width === widths[0] && scale === 1) {
          await desk.getByLabel("PUBLIC NAME").fill("Synthetic owner");
          await button(desk, "Save profile").click();
        }
        await create.click();
        await desk
          .getByLabel("TITLE", { exact: true })
          .fill(`Synthetic advert ${width} ${scale}`);
        await desk
          .getByLabel("DESCRIPTION", { exact: true })
          .fill("An accessibility audit fixture with no real occupant.");
        await desk.getByLabel("STREET AND BUILDING").fill("Fixture Street 15");
        const lat = desk.getByLabel("Location latitude");
        await lat.fill("91");
        await expect(lat).toHaveAccessibleDescription(/Enter a latitude/);
        await lat.fill("50.06");
        await desk.getByLabel("Location longitude").fill("19.94");
        await expect(
          desk.getByText("Location set", { exact: true }),
        ).toBeVisible();
        const saveDraft = button(desk, "Save draft");
        await expect(saveDraft).toBeEnabled();
        await reachable(saveDraft);
        await reachable(button(desk, "Close dialog"));
        await overflow();
        if (width === widths[0] && scale === 1) {
          await saveDraft.click();
          await expect(desk.getByText(/DRAFT ·/)).toBeVisible();
        } else {
          await button(desk, "Back to adverts").click();
        }
        await reachable(button(desk, "Publish"));
        await button(desk, "Messages").click();
        await button(desk, "Open conversation: Fixture conversation").click();
        const message = desk.getByLabel("YOUR MESSAGE");
        await message.fill("Local keyboard message draft.");
        await reachable(button(desk, "Send message"));
        await reachable(button(desk, "Close dialog"));
        await overflow();
        if (width === 320 && scale === 2) {
          await button(desk, "Send message").scrollIntoViewIfNeeded();
          await page.screenshot({
            path: info.outputPath("320px-200percent-message.png"),
          });
        }
        await close(page, desk);
        await button(page, "Discover homes").click();
        if (scale === 2)
          await page
            .locator("#t20-text-only")
            .evaluate((node) => node.remove());
      });
    }
  }
  expect(blocked).toEqual([]);
});

test("T20-TC02 opens a listing by keyboard, wraps both directions and restores focus", async ({
  page,
  context,
}) => {
  const blocked = await allowOwned(context);
  await page.goto("/");
  const action = button(page, first);
  await action.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "A closer look" });
  const dismiss = button(dialog, "Close dialog");
  const report = button(dialog, "Report a concern");
  await expect(dismiss).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(report).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(dismiss).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(button(dialog, "Save this home")).toBeFocused();
  await close(page, dialog);
  await expect(action).toBeFocused();
  expect(blocked).toEqual([]);
});

test("T20-TC03 enters, adjusts, removes, finishes and clears a search area by keyboard", async ({
  page,
  context,
}, info) => {
  const blocked = await allowOwned(context, false);
  execFileSync(
    process.env.E2E_PYTHON!,
    ["e2e/fixture.py", "boundaries", info.project.name],
    { stdio: "pipe" },
  );
  await page.goto("/");
  const mapButton = button(page, "Map view");
  await mapButton.focus();
  await page.keyboard.press("Enter");
  const coordinates = button(page, "Enter area coordinates");
  await keyActivate(page, coordinates);
  const dialog = page.getByRole("dialog", { name: "Search area coordinates" });
  const latitude = dialog.getByLabel("Latitude", { exact: true });
  const longitude = dialog.getByLabel("Longitude", { exact: true });
  const add = button(dialog, "Add vertex");
  const finish = button(dialog, "Use this area");
  await keyText(page, latitude, "91");
  await keyText(page, longitude, "19.9");
  await keyActivate(page, add);
  await expect(latitude).toHaveAccessibleDescription(/latitude from/);
  await keyText(page, latitude, "50.02");
  await keyActivate(page, add);
  for (const [lat, lon] of [
    ["50.02", "20.03"],
    ["50.11", "19.9"],
  ]) {
    await keyText(page, latitude, lat);
    await keyText(page, longitude, lon);
    await keyActivate(page, add);
  }
  await keyActivate(page, button(dialog, "Edit vertex 2"));
  await keyText(page, longitude, "20.09");
  await keyActivate(page, button(dialog, "Save vertex"));
  await keyActivate(page, button(dialog, "Remove vertex 3"));
  await keyActivate(page, finish);
  await expect(dialog.getByRole("alert")).toContainText(
    "3 and 64 distinct vertices",
  );
  await keyText(page, latitude, "50.11");
  await keyText(page, longitude, "19.9");
  await keyActivate(page, add);
  const filtered = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.origin === api &&
      url.pathname === "/v1/listings" &&
      url.searchParams.has("polygon")
    );
  });
  await keyActivate(page, finish);
  const response = await filtered;
  expect(response.ok()).toBeTruthy();
  expect(
    JSON.parse(new URL(response.url()).searchParams.get("polygon")!),
  ).toEqual([
    [19.9, 50.02],
    [20.09, 50.02],
    [19.9, 50.11],
  ]);
  const result = await response.json();
  expect(
    result.items.some((home: Listing) =>
      home.title.endsWith(`boundary ${info.project.name} good`),
    ),
  ).toBe(true);
  expect(
    result.items.some((home: Listing) =>
      home.title.endsWith(`boundary ${info.project.name} outside`),
    ),
  ).toBe(false);
  await expect(dialog).toHaveCount(0);
  await expect(button(page, "Edit area coordinates")).toBeFocused();
  const unfiltered = page.waitForResponse(
    (response) =>
      response.url().startsWith(`${api}/v1/listings?`) &&
      !new URL(response.url()).searchParams.has("polygon"),
  );
  await keyActivate(page, button(page, "Clear area"));
  expect((await unfiltered).ok()).toBe(true);
  await expect(coordinates).toBeVisible();
  expect(blocked).toEqual([]);
});

async function textContrast(locator: Locator) {
  return locator.evaluate((node) => {
    const rgb = (value: string) => value.match(/[\d.]+/g)!.map(Number);
    const color = rgb(getComputedStyle(node).color);
    let background = [255, 255, 255];
    for (
      let parent: Element | null = node;
      parent;
      parent = parent.parentElement
    ) {
      const fill = rgb(getComputedStyle(parent).backgroundColor);
      if (fill.length === 3 || fill[3] === 1) {
        background = fill;
        break;
      }
    }
    const luma = (values: number[]) =>
      values
        .slice(0, 3)
        .map((value) => {
          const s = value / 255;
          return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
        })
        .reduce(
          (sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index],
          0,
        );
    const [high, low] = [luma(color), luma(background)].sort((a, b) => b - a);
    return {
      foreground: color.slice(0, 3),
      background: background.slice(0, 3),
      ratio: (high + 0.05) / (low + 0.05),
    };
  });
}

test("T20-TC04 exposes listing states, labels and sufficient contrast in monochrome", async ({
  page,
  context,
}, info) => {
  const blocked = await allowOwned(context);
  await page.goto("/");
  await register(page, `t20-contrast-${info.project.name}@example.test`);
  await page.addStyleTag({
    content: "#root, .app-dialog { filter: grayscale(1); }",
  });
  await expect(button(page, "Discover homes")).toHaveAttribute("aria-current", "page");
  const listMode = button(page, "List view");
  const mapMode = button(page, "Map view");
  await expect(mapMode).toHaveAttribute("aria-pressed", String(info.project.name === "desktop"));
  await listMode.click();
  await expect(listMode).toHaveAttribute("aria-pressed", "true");
  await expect(mapMode).toHaveAttribute("aria-pressed", "false");
  const direct = page.getByText("DIRECT OFFER", { exact: true }).first();
  const agency = page.getByText("AGENCY", { exact: true }).first();
  const commission = page.getByText("Commission not stated", { exact: true });
  const seen = page.getByText("SEEN", { exact: true });
  const measurements: Record<
    string,
    Awaited<ReturnType<typeof textContrast>>
  > = {};
  for (const [label, control] of [
    ["direct", direct],
    ["agency", agency],
    ["commission", commission],
    ["seen", seen],
  ] as const) {
    await expect(control).toBeVisible();
    measurements[label] = await textContrast(control);
  }
  await button(page, `Save ${first}`).click();
  const saved = page.getByRole("button", {
    name: `Unsave ${first}`,
    pressed: true,
  });
  await expect(saved).toBeVisible();
  measurements.saved = await textContrast(
    saved.getByText("Saved", { exact: true }),
  );
  await button(page, `Compare ${second}`).click();
  const compared = page.getByRole("button", {
    name: `Compare ${second}`,
    pressed: true,
  });
  await expect(compared).toBeVisible();
  measurements.compared = await textContrast(
    compared.getByText("Compared", { exact: true }),
  );
  await button(page, "Saved homes").click();
  await expect(button(page, "Saved homes")).toHaveAttribute("aria-current", "page");
  await expect(button(page, "Discover homes")).not.toHaveAttribute("aria-current", "page");
  const delisted = page.getByText("DELISTED", { exact: true });
  await expect(delisted).toBeVisible();
  measurements.delisted = await textContrast(delisted);
  await button(page, "Notifications").click();
  const notifications = page.getByText("YOUR RENTAL UPDATES");
  measurements.notificationLabel = await textContrast(notifications);
  measurements.primaryButton = await textContrast(
    button(page, "Enable email alerts").getByText("Enable email alerts"),
  );
  const input = page.getByRole("textbox", { name: "City", exact: true });
  await button(page, "Discover homes").click();
  await input.focus();
  await page.keyboard.press("Tab");
  const focus = page.getByRole("textbox", {
    name: "Search neighborhood, street or keyword",
  });
  await expect(focus).toBeFocused();
  const outline = await focus.evaluate((node) => {
    const style = getComputedStyle(node);
    return {
      color: style.outlineColor,
      width: style.outlineWidth,
      style: style.outlineStyle,
    };
  });
  expect(outline).toEqual({
    color: "rgb(155, 63, 33)",
    width: "2px",
    style: "solid",
  });
  expect(
    Object.values(measurements).every((sample) => sample.ratio >= 4.5),
  ).toBe(true);
  await writeFile(
    info.outputPath("contrast.json"),
    JSON.stringify({ measurements, outline }, null, 2),
  );
  if (info.project.name === "mobile") {
    await commission.scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath("monochrome-card.png") });
  }
  expect(blocked).toEqual([]);
});

test("T20-TC05 defers unopened map and rental desk code and far-offscreen photos", async ({
  page,
  context,
}) => {
  const blocked = await allowOwned(context);
  await page.setViewportSize({ width: 390, height: 844 });
  const scripts = new Set<string>();
  const photos = new Set<string>();
  page.on("request", (request) => {
    const { pathname } = new URL(request.url());
    if (request.resourceType() === "script")
      scripts.add(pathname.split("/").at(-1)!);
    if (pathname.startsWith("/t20-image/")) photos.add(pathname);
  });
  await page.goto("/");
  await expect(button(page, first)).toBeVisible();
  await expect.poll(() => photos.has("/t20-image/001.png")).toBe(true);
  const lastPhoto = page.getByAltText("Photo of T20 home 024");
  await expect(lastPhoto).toHaveAttribute("loading", "lazy");
  await expect(lastPhoto).toHaveAttribute("width", "400");
  await expect(lastPhoto).toHaveAttribute("height", "210");
  expect(photos.has("/t20-image/024.png")).toBe(false);
  expect(
    [...scripts].some((name) =>
      /PropertyMap|leaflet|MarketplaceDialog/i.test(name),
    ),
  ).toBe(false);
  await lastPhoto.scrollIntoViewIfNeeded();
  await expect.poll(() => photos.has("/t20-image/024.png")).toBe(true);
  await button(page, "Map view").click();
  await expect(
    page.getByRole("region", { name: "Map of rental homes" }),
  ).toBeVisible();
  await expect
    .poll(() => [...scripts].some((name) => /leaflet/i.test(name)))
    .toBe(true);
  expect([...scripts].some((name) => /PropertyMap/i.test(name))).toBe(true);
  expect([...scripts].some((name) => /MarketplaceDialog/i.test(name))).toBe(
    false,
  );
  await register(page, `t20-lazy-${test.info().project.name}@example.test`);
  await button(page, "Account").click();
  await button(page, "My rental adverts").click();
  await expect(
    page.getByRole("dialog", { name: "Your rental desk." }),
  ).toBeVisible();
  expect([...scripts].some((name) => /MarketplaceDialog/i.test(name))).toBe(
    true,
  );
  expect(blocked).toEqual([]);
});

const coldProfile = {
  offline: false,
  latency: 150,
  downloadThroughput: 1_600_000 / 8,
  uploadThroughput: 750_000 / 8,
  connectionType: "cellular3g" as const,
};
const benchmarkViewport = { width: 390, height: 844 };
const warmLimitMs = 200;

async function afterTwoFrames(page: Page) {
  return page.evaluate(
    () =>
      new Promise<number>((resolve) =>
        requestAnimationFrame(() =>
          requestAnimationFrame(() => resolve(performance.now())),
        ),
      ),
  );
}

async function measuredEnter(
  page: Page,
  target: Locator,
  selector: string,
  text?: string,
) {
  await target.focus();
  await expect(target).toBeFocused();
  await page.evaluate(
    ({ selector, text }) => {
      const win = window as Window & { t20Measure?: Promise<number> };
      win.t20Measure = new Promise<number>((resolve, reject) => {
        const observer = new MutationObserver(check);
        let start = 0;
        const timeout = setTimeout(() => {
          observer.disconnect();
          reject(new Error("Measured UI state did not appear"));
        }, 10_000);
        function check() {
          const match = Array.from(document.querySelectorAll(selector)).find(
            (node) =>
              (!text || node.textContent === text) &&
              node.getClientRects().length > 0,
          );
          if (!match) return;
          observer.disconnect();
          clearTimeout(timeout);
          requestAnimationFrame(() =>
            requestAnimationFrame(() => resolve(performance.now() - start)),
          );
        }
        document.addEventListener(
          "keydown",
          () => {
            start = performance.now();
            observer.observe(document.documentElement, {
              childList: true,
              subtree: true,
              attributes: true,
              characterData: true,
            });
            check();
          },
          { capture: true, once: true },
        );
      });
    },
    { selector, text },
  );
  await page.keyboard.press("Enter");
  return page.evaluate(
    () => (window as Window & { t20Measure?: Promise<number> }).t20Measure!,
  );
}

test("T20-TC06 measures 100-result cold loads and 30 warm UI actions", async ({
  browser,
}, info) => {
  test.setTimeout(180_000);
  const cold = [];
  for (let i = 0; i < 3; i++) {
    const context = await browser.newContext({
      baseURL: web,
      viewport: benchmarkViewport,
    });
    try {
      const blocked = await allowOwned(context);
      const page = await context.newPage();
      const cdp = await context.newCDPSession(page);
      await cdp.send("Network.enable");
      await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
      await cdp.send("Network.emulateNetworkConditions", coldProfile);
      await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
      await page.goto("/");
      await expect(
        page.getByText("100 homes in Kraków", { exact: true }),
      ).toBeVisible();
      await expect(button(page, first)).toBeVisible();
      const resultFrameMs = await afterTwoFrames(page);
      const navigation = await page.evaluate(() => ({
        loadEventEndMs: (
          performance.getEntriesByType(
            "navigation",
          )[0] as PerformanceNavigationTiming
        ).loadEventEnd,
        firstContentfulPaintMs:
          performance.getEntriesByName("first-contentful-paint")[0]
            ?.startTime ?? null,
      }));
      cold.push({ resultFrameMs, ...navigation });
      expect(blocked).toEqual([]);
    } finally {
      await context.close();
    }
  }
  const context = await browser.newContext({
    baseURL: web,
    viewport: benchmarkViewport,
  });
  try {
    const blocked = await allowOwned(context);
    const page = await context.newPage();
    await page.goto("/");
    const filters = button(page, "More filters");
    const filterDialog = page.getByRole("dialog", {
      name: "A home that fits.",
    });
    const detailDialog = page.getByRole("dialog", { name: "A closer look" });
    await expect(button(page, first)).toBeVisible();
    await filters.click();
    await close(page, filterDialog);
    await button(page, first).click();
    await close(page, detailDialog);
    await afterTwoFrames(page);
    const samples: { action: string; ms: number }[] = [];
    for (let i = 0; i < 10; i++) {
      samples.push({
        action: "open filters",
        ms: await measuredEnter(
          page,
          filters,
          "dialog[open] h1",
          "A home that fits.",
        ),
      });
      await filterDialog
        .getByLabel("MIN RENT · PLN")
        .fill(String(4020 + i * 20));
      samples.push({
        action: "apply filters",
        ms: await measuredEnter(
          page,
          button(filterDialog, "Show matching homes"),
          '[aria-live="polite"]',
          `${99 - i} homes in Kraków`,
        ),
      });
      samples.push({
        action: "open listing",
        ms: await measuredEnter(
          page,
          button(page, homes[i + 1].title),
          "dialog[open] h1",
          "A closer look",
        ),
      });
      await close(page, detailDialog);
    }
    const sorted = samples.map((sample) => sample.ms).sort((a, b) => a - b);
    const p95Ms = sorted[Math.ceil(sorted.length * 0.95) - 1];
    const report = {
      timestamp: new Date().toISOString(),
      browser: browser.version(),
      viewport: benchmarkViewport,
      fixtureResults: homes.length,
      pageSize: 24,
      coldProfile: { ...coldProfile, cpuRate: 4 },
      cold,
      warmLimitMs,
      p95Ms,
      pass: p95Ms <= warmLimitMs,
      samples,
    };
    await writeFile(
      info.outputPath("web-performance.json"),
      JSON.stringify(report, null, 2),
    );
    expect(blocked).toEqual([]);
    expect(samples).toHaveLength(30);
    expect(p95Ms, "Warm interaction p95 in milliseconds").toBeLessThanOrEqual(
      warmLimitMs,
    );
  } finally {
    await context.close();
  }
});
