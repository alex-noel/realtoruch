import { test, expect, BrowserContext, Page } from '@playwright/test';
import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';

async function blockOutside(context: BrowserContext, blocked: string[]) {
  const ports = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.protocol === 'data:' || (url.hostname === '127.0.0.1' && ports.has(url.port))) await route.continue();
    else { blocked.push(url.origin); await route.abort('blockedbyclient'); }
  });
}
async function createVerified(page: Page, email: string) {
  await page.goto('/', { waitUntil: 'commit' });
  await page.locator('button[aria-label="Sign in"]').click();
  await page.getByRole('button', { name: 'New here? Create a free account' }).click();
  await page.getByPlaceholder('you@example.com').fill(email);
  await page.getByPlaceholder('At least 12 characters').fill('synthetic-test-password-123');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Account', exact: true })).toBeVisible();
  let token = '';
  await expect.poll(async () => {
    const files = await readdir(process.env.E2E_MAIL_DIR!).catch(() => []);
    for (const name of files.filter(f => f.endsWith('.eml'))) {
      const content = (await readFile(join(process.env.E2E_MAIL_DIR!, name), 'utf8')).replace(/=\r?\n/g, '').replace(/=3D/gi, '=');
      if (content.includes(email)) token = content.match(/#verify_account=([^\s]+)/)?.[1] || '';
    }
    return !!token;
  }, { timeout: 20_000 }).toBe(true);
  await page.evaluate(value => { window.location.hash = `verify_account=${value}`; }, token);
  const response = page.waitForResponse(r => r.url().endsWith('/v1/auth/verify-email'));
  await page.reload({ waitUntil: 'commit' });
  expect((await response).status()).toBe(200);
  await expect(page.getByRole('button', { name: 'Account', exact: true })).toBeVisible();
}

test.describe("moderation decisions", () => {
  test("Q38 confirms the exact home and source and keeps per-report reasons", async ({ page, context }, info) => {
    const blocked: string[] = [];
    await blockOutside(context, blocked);
    const api = process.env.E2E_API_URL!;
    const auth = process.env.E2E_AUTH_URL!;
    const web = process.env.E2E_WEB_URL!;
    const source = {
      id: "fixture-source-a", name: "otodom", title: "Original courtyard advert",
      address: "Fixture Street 1", rent_pln: 4000, url: `${web}/fixture-source`,
    };
    const secondSource = { ...source, id: "fixture-source-b", name: "gratka", title: "Courtyard cross-post" };
    const first = {
      id: "fixture-home-a", title: "Courtyard rental", address: "Fixture Street 1", city: "Kraków",
      description: "Synthetic moderator context", rent_pln: 4000, risk_flags: [], sources: [source, secondSource],
    };
    const second = { ...first, id: "fixture-home-b", title: "Garden rental", address: "Fixture Street 2" };
    const target = { ...first, id: "fixture-target", title: "Target apartment", address: "Fixture Street 3" };
    const created_at = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
    let reports = [
      { id: "fixture-report-a", reason: "Review source evidence for the courtyard rental.", created_at, hidden: false, listing: first },
      { id: "fixture-report-b", reason: "Appeal for the garden rental.", created_at, hidden: true, listing: second },
    ];
    let queueReads = 0;
    let expire = false;
    let finishQueue!: () => void;
    const initialQueue = new Promise<void>(resolve => { finishQueue = resolve; });
    let finishMerge!: () => void;
    const pendingMerge = new Promise<void>(resolve => { finishMerge = resolve; });
    const decisions: { route: string; body: object }[] = [];
    await page.route(`${api}/v1/me/capabilities`, route => route.fulfill({ json: { moderator: true } }));
    await page.route(`${api}/v1/moderation/reports`, async route => {
      queueReads++;
      if (expire) return route.fulfill({ status: 401, json: {} });
      if (queueReads === 1) {
        await initialQueue;
        return route.fulfill({ status: 503, json: { detail: "Synthetic internal detail" } });
      }
      return route.fulfill({ json: { items: queueReads === 2 ? [] : reports } });
    });
    await page.route(`${api}/v1/moderation/listings/*/identity`, route => route.fulfill({
      json: { sources: [source, secondSource], candidates: [target] },
    }));
    await page.route(/\/v1\/moderation\/(?:listings|reports)\/[^/]+\/(?:merge|split|review)$/, async route => {
      const pathname = new URL(route.request().url()).pathname;
      decisions.push({ route: pathname, body: route.request().postDataJSON() });
      if (pathname.endsWith("/merge")) {
        await pendingMerge;
        return route.fulfill({ status: 503, json: { detail: "Synthetic internal detail" } });
      }
      if (pathname.endsWith("/split")) return route.fulfill({ json: { listing_id: "fixture-new-home" } });
      if (pathname.includes("fixture-report-a")) {
        reports = reports.filter(item => item.id !== "fixture-report-a");
        return route.fulfill({ status: 409, json: { detail: "Report is no longer pending" } });
      }
      return route.fulfill({ status: 403, json: { detail: "Synthetic restricted data" } });
    });

    await createVerified(page, `review-fixture-${info.project.name}@example.test`);
    await page.getByRole("button", { name: "Account", exact: true }).click();
    await page.getByRole("button", { name: "My rental adverts", exact: true }).click();
    const desk = page.getByRole("dialog", { name: "Your rental desk." });
    const selected = desk.getByRole("region", { name: "Selected report" });
    const confirmation = desk.getByRole("region", { name: "Confirm moderation decision" });
    const action = (name: string) => desk.getByRole("button", { name, exact: true });
    const reason = selected.getByRole("textbox", { name: "Review reason" });
    await action("Review reports").click();
    try {
      await expect(desk.getByText("Loading reports…", { exact: true })).toBeVisible();
      await expect(desk.getByText("No pending reports.", { exact: true })).toHaveCount(0);
    } finally {
      finishQueue();
    }
    await expect(desk.getByText("Could not load reports.", { exact: true })).toBeVisible();
    await action("Retry queue").click();
    await expect(desk.getByText("No pending reports.", { exact: true })).toBeVisible();
    await action("Refresh queue").click();
    await expect(selected.getByText(/Reported 3 hours ago · Visible/)).toBeVisible();
    const aReason = "Checked exact address and both source descriptions.";
    const bReason = "The appeal includes updated source evidence.";
    await reason.fill(aReason);
    await action("Hide home").click();
    await expect(confirmation.getByText(/Courtyard rental.*Home ID fixture-home-a/)).toBeVisible();
    await expect(confirmation.getByText("Hide this home and close this report.")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(confirmation).toHaveCount(0);
    await expect(action("Hide home")).toBeFocused();
    await action("Report 2 · Garden rental").click();
    await expect(reason).toHaveValue("");
    await reason.fill(bReason);
    await action("Restore visibility").click();
    await expect(confirmation.getByText(/Garden rental.*Home ID fixture-home-b/)).toBeVisible();
    await action("Cancel decision").click();
    expect(decisions).toHaveLength(0);

    await action("Report 1 · Courtyard rental").click();
    await expect(reason).toHaveValue(aReason);
    await action("Review duplicate identity").click();
    await action("Merge into Target apartment").click();
    await expect(confirmation.getByText(/Target apartment.*Home ID fixture-target/)).toBeVisible();
    await expect(confirmation.getByText(/Original courtyard advert.*Source ID fixture-source-a/)).toBeVisible();
    await expect(confirmation.getByText(/Courtyard cross-post.*Source ID fixture-source-b/)).toBeVisible();
    if (info.project.name === "mobile") {
      await confirmation.getByRole("heading").scrollIntoViewIfNeeded();
      await page.screenshot({ path: info.outputPath("q38-targeted-confirmation.png") });
    }
    await action("Confirm merge homes").evaluate(node => {
      (node as HTMLElement).click();
      (node as HTMLElement).click();
    });
    try {
      await expect.poll(() => decisions.length).toBe(1);
      await expect(action("Saving decision…")).toBeDisabled();
      expect(decisions[0]).toEqual({
        route: "/v1/moderation/listings/fixture-home-a/merge",
        body: { target_id: "fixture-target", reason: aReason },
      });
    } finally {
      finishMerge();
    }
    await expect(confirmation.getByRole("alert")).toHaveText("Could not save the decision. Try again or cancel.");
    await action("Cancel decision").click();
    await expect(reason).toHaveValue(aReason);
    await action("Separate otodom source").click();
    await expect(confirmation.getByText(/Move otodom.*Source ID fixture-source-a.*separate home/)).toBeVisible();
    await action("Confirm separate source").click();
    await expect(desk.getByText("Decision saved.", { exact: true })).toBeVisible();
    expect(decisions[1]).toEqual({
      route: "/v1/moderation/listings/fixture-home-a/split",
      body: { source_id: "fixture-source-a", reason: aReason },
    });
    await expect(reason).toHaveValue("");
    await reason.fill(aReason);
    const beforeConflict = queueReads;
    await action("Hide home").click();
    await action("Confirm hide home").click();
    await expect(desk.getByText("This report has already been reviewed.", { exact: true })).toBeVisible();
    await expect(selected.getByRole("heading", { name: "Garden rental" })).toBeVisible();
    expect(queueReads).toBe(beforeConflict + 1);
    expect(decisions[2]).toEqual({
      route: "/v1/moderation/reports/fixture-report-a/review",
      body: { action: "hide", reason: aReason },
    });
    await expect(reason).toHaveValue(bReason);
    await action("Restore visibility").click();
    await action("Confirm restore visibility").click();
    await expect(desk.getByText("Moderator access is required to review reports.")).toBeVisible();
    await expect(selected).toHaveCount(0);
    expect(decisions[3]).toEqual({
      route: "/v1/moderation/reports/fixture-report-b/review",
      body: { action: "restore", reason: bReason },
    });
    expire = true;
    await page.route(`${auth}/v1/auth/refresh`, route => route.fulfill({ status: 401, json: {} }));
    await action("Retry queue").click();
    await expect(desk).toHaveCount(0);
    await expect(page.getByText("Your session ended. Sign in again.")).toBeVisible();
    expect(blocked).toEqual([]);
  });

  test("Q38 ordinary renters cannot open the moderation queue or grant access", async ({ page, context }, info) => {
    const blocked: string[] = [];
    await blockOutside(context, blocked);
    const api = process.env.E2E_API_URL!;
    await createVerified(page, `ordinary-review-${info.project.name}@example.test`);
    const capability = page.waitForResponse(response => response.url() === `${api}/v1/me/capabilities`);
    await page.getByRole("button", { name: "Account", exact: true }).click();
    await page.getByRole("button", { name: "My rental adverts", exact: true }).click();
    const result = await capability;
    expect(await result.json()).toEqual({ moderator: false });
    await expect(page.getByRole("button", { name: "Review reports", exact: true })).toHaveCount(0);
    const authorization = await result.request().headerValue("authorization");
    expect(Boolean(authorization)).toBe(true);
    const headers = { authorization: authorization! };
    expect((await context.request.get(`${api}/v1/moderation/reports`, { headers })).status()).toBe(403);
    expect((await context.request.put(`${api}/v1/me/capabilities`, { headers, data: { moderator: true } })).status()).toBe(405);
    expect((await context.request.post(`${api}/v1/moderation/reports/fixture-report/review`, {
      headers, data: { action: "hide", reason: "Attempt by an ordinary synthetic account." },
    })).status()).toBe(403);
    expect(blocked).toEqual([]);
  });
});

test('owner publishes, edits, messages a renter and withdraws @cross-browser', async ({ page, context, browser }, info) => {
  const blocked: string[] = [];
  await blockOutside(context, blocked);
  const suffix = info.project.name;
  const title = `T18 owner home ${suffix}`;
  await createVerified(page, `owner-${suffix}@example.test`);
  await page.getByRole('button', { name: 'Account', exact: true }).click();
  await page.getByRole('button', { name: 'My rental adverts' }).click();
  await page.getByLabel('PUBLIC NAME').fill(`Owner ${suffix}`);
  await page.getByRole('button', { name: 'Save profile' }).click();
  await page.getByRole('button', { name: 'Create rental advert' }).click();
  await page.getByLabel('TITLE', { exact: true }).fill(title);
  await page.getByLabel('DESCRIPTION', { exact: true }).fill('A synthetic apartment used only for local automated tests.');
  await page.getByLabel('CITY', { exact: true }).fill('Kraków');
  await page.getByLabel('STREET AND BUILDING').fill('Testowa 13');
  await page.getByRole('dialog').getByRole('region', { name: 'Map of rental homes' }).click();
  await page.getByLabel('MONTHLY BASE RENT (PLN)').fill('4500');
  await page.getByLabel('FEES (PLN; LEAVE BLANK IF UNKNOWN)').fill('500');
  await page.getByLabel('AREA (M²)').fill('55');
  await page.getByLabel('ROOMS', { exact: true }).fill('2');
  await page.getByRole('button', { name: 'Save draft' }).click();
  await expect(page.getByText('DRAFT', { exact: false })).toBeVisible();
  let publishAttempts = 0;
  await page.route(`${process.env.E2E_API_URL}/v1/me/adverts/*/publish`, async route => {
    if (++publishAttempts === 1) return route.fulfill({ status: 503, json: { detail: 'offline' } });
    return route.continue();
  });
  await page.getByRole('button', { name: 'Review and publish', exact: true }).click();
  await expect(page.getByText('Review this rental')).toBeVisible();
  expect(publishAttempts).toBe(0);
  await page.getByRole('button', { name: 'Publish advert', exact: true }).click();
  await expect(page.getByText('Review this rental')).toBeVisible();
  await expect(page.getByText('Cannot reach the service. Try again.').first()).toBeVisible();
  await page.getByRole('button', { name: 'Publish advert', exact: true }).click();
  await expect(page.getByText(/^PUBLISHED ·/)).toBeVisible();
  expect(publishAttempts).toBe(2);
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await page.getByLabel('MONTHLY BASE RENT (PLN)').fill('4200');
  let updateCalls = 0;
  await page.route(`${process.env.E2E_API_URL}/v1/me/adverts/*`, async route => {
    if (route.request().method() === 'PUT') {
      updateCalls++;
      if (updateCalls === 1) return route.fulfill({ status: 409, json: { detail: 'This advert changed on another device. Reload before editing.' } });
    }
    return route.continue();
  });
  await page.getByRole('button', { name: 'Review published changes' }).click();
  await expect(page.getByText('Review this rental')).toBeVisible();
  expect(updateCalls).toBe(0);
  await page.getByRole('button', { name: 'Back to editing' }).click();
  await expect(page.getByLabel('MONTHLY BASE RENT (PLN)')).toHaveValue('4200');
  await page.getByRole('button', { name: 'Review published changes' }).click();
  await page.getByRole('button', { name: 'Apply published changes' }).click();
  await page.getByRole('button', { name: 'Use mine for rent_pln' }).click();
  await page.getByRole('button', { name: 'Save selected values' }).click();
  await expect(page.getByText('Review this rental')).toBeVisible();
  const update = page.waitForRequest(request => request.url().includes('/v1/me/adverts/') && request.method() === 'PUT');
  await page.getByRole('button', { name: 'Apply published changes' }).click();
  expect((await update).postDataJSON().advert.rent_pln).toBe(4200);
  expect(updateCalls).toBe(2);
  await expect(page.getByText(/PUBLISHED.*4\s?200/)).toBeVisible();

  const renter = await browser.newContext({ viewport: info.project.use.viewport });
  try {
    await blockOutside(renter, blocked);
    const visitor = await renter.newPage();
    await createVerified(visitor, `renter-${suffix}@example.test`);
    await expect(visitor.getByRole('button', { name: title, exact: true })).toBeVisible();
    await visitor.getByRole('button', { name: title, exact: true }).click();
    await expect(visitor.getByRole('dialog').getByText(/4\s?500/).first()).toBeVisible();
    await expect(visitor.getByRole('dialog').getByText(/4\s?200/).first()).toBeVisible();
    await visitor.getByRole('button', { name: `Message Owner ${suffix}` }).click();
    await visitor.getByLabel('YOUR MESSAGE').fill('Hello, is this synthetic home still available?');
    await visitor.getByRole('button', { name: 'Send message' }).click();
    await expect(visitor.getByText('Hello, is this synthetic home still available?')).toBeVisible();
    await page.bringToFront();
    await page.getByRole('button', { name: 'Messages', exact: true }).click();
    await expect(page.getByText(/1 unread/)).toBeVisible();
    const readResponse = page.waitForResponse(response => response.url().includes('/v1/me/conversations/') && response.url().endsWith('/read') && response.request().method() === 'PUT');
    await page.getByRole('button', { name: /^Open conversation/ }).click();
    await expect(page.getByText('Hello, is this synthetic home still available?')).toBeInViewport();
    expect((await readResponse).status()).toBe(200);
    await page.getByLabel('YOUR MESSAGE').fill('Yes, this is a local test reply.');
    await page.getByRole('button', { name: 'Send message' }).click();
    await expect(page.getByText('Yes, this is a local test reply.')).toBeVisible();
    await page.getByRole('button', { name: 'All conversations' }).click();
    await expect(page.getByText(/1 unread/)).toHaveCount(0);
    await page.getByRole('button', { name: 'My adverts', exact: true }).click();
    await page.getByRole('button', { name: 'Withdraw' }).click();
    await expect(page.getByText('WITHDRAWN', { exact: false })).toBeVisible();
    const discovery = visitor.waitForResponse(r => r.url().includes('/v1/listings?') && r.status() === 200);
    await visitor.reload({ waitUntil: 'commit' });
    await discovery;
    await expect(visitor.getByRole('button', { name: title, exact: true })).toHaveCount(0);
    expect(blocked).toEqual([]);
  } finally { await renter.close(); }
});

test('Q28 owner fields retain raw decimals and validate Poland bounds before saving', async ({ page, context }, info) => {
  await blockOutside(context, []);
  await page.setViewportSize({ width: 320, height: 844 });
  await createVerified(page, `q28-${info.project.name}@example.test`);
  await page.route(`${process.env.E2E_API_URL}/v1/me/adverts`, async route => {
    if (route.request().method() !== 'GET') return route.continue();
    const response = await route.fetch(); const data = await response.json();
    for (const item of data.items || []) item.advert.amenities = ['historic-unknown'];
    await route.fulfill({ response, json: data });
  });
  await page.getByRole('button', { name: 'Account', exact: true }).click();
  await page.getByRole('button', { name: 'My rental adverts' }).click();
  await page.getByLabel('PUBLIC NAME').fill('Q28 owner');
  await page.getByRole('button', { name: 'Save profile' }).click();
  await page.getByRole('button', { name: 'Create rental advert' }).click();
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: /Check \d+ fields/ })).toBeVisible();
  await page.getByRole('button', { name: 'Go to first invalid field' }).click();
  await expect(page.getByLabel('TITLE', { exact: true })).toBeFocused();
  await page.getByLabel('TITLE', { exact: true }).fill('Q28 synthetic rental');
  await page.getByLabel('DESCRIPTION', { exact: true }).fill('A sufficiently long synthetic rental description.');
  await page.getByLabel('STREET AND BUILDING').fill('Testowa 28');
  await page.getByLabel('Location latitude').fill('40');
  await page.getByLabel('Location longitude').fill('19.94');
  await expect(page.getByLabel('Location latitude')).toHaveAccessibleDescription(/from 49 to 55/);
  await page.getByLabel('AREA (M²)').fill('50,');
  await expect(page.getByLabel('AREA (M²)')).toHaveValue('50,');
  await page.getByLabel('AREA (M²)').fill('50,5');
  await page.getByLabel('FEES (PLN; LEAVE BLANK IF UNKNOWN)').fill('0');
  await page.getByLabel('FLOOR', { exact: true }).fill('-2');
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  await page.getByRole('button', { name: 'Go to first invalid field' }).click();
  await expect(page.getByLabel('Location latitude')).toBeFocused();
  await page.getByLabel('Location latitude').fill('50.06');
  const saved = page.waitForResponse(response => response.url().endsWith('/v1/me/adverts') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  const response = await saved; expect(response.status()).toBe(201);
  expect((await response.json()).advert).toMatchObject({ area_m2: 50.5, fees_pln: 0, floor: -2 });
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(page.getByText('Other saved amenity: historic-unknown', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Pets welcome', exact: true }).click();
  const edited = page.waitForRequest(request => request.url().includes('/v1/me/adverts/') && request.method() === 'PUT');
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  expect((await edited).postDataJSON().advert.amenities).toEqual(['historic-unknown', 'pets']);
});
