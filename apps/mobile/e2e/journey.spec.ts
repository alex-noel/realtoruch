import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import { readdir, readFile, stat } from 'node:fs/promises';

// Start the fault trace only after token-bearing links have been consumed.
test.use({ trace: 'off' });

function fixture(action: string, profile: string) {
  return JSON.parse(execFileSync(process.env.E2E_PYTHON!, [join(__dirname, 'fixture.py'), action, profile], { encoding: 'utf8' }));
}

async function mailFor(email: string) {
  const files = await readdir(process.env.E2E_MAIL_DIR!).catch(() => []);
  const messages = await Promise.all(files.filter(f => f.endsWith('.eml')).map(async file => ({
    modified: (await stat(join(process.env.E2E_MAIL_DIR!, file))).mtimeMs,
    content: await readFile(join(process.env.E2E_MAIL_DIR!, file), 'utf8'),
  })));
  return messages.sort((a, b) => a.modified - b.modified)
    .map(({ content }) => content)
    .filter(content => content.includes(email))
    .map(content => content.replace(/=\r?\n/g, '').replace(/=3D/gi, '='));
}
function rentalMail(contents: string[]) {
  return contents.filter(content => !content.includes('Verify your Realtoruch email') && !content.includes('Confirm your Realtoruch email alerts'));
}

test('draw and save a filtered search against a synthetic baseline @cross-browser', async ({ page, context }, info) => {
  const allowed = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
  const blocked: string[] = [];
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.protocol === 'data:' || (url.hostname === '127.0.0.1' && allowed.has(url.port))) await route.continue();
    else { blocked.push(url.origin); await route.abort('blockedbyclient'); }
  });
  fixture('baseline', info.project.name);
  await page.goto('/', { waitUntil: 'commit' });
  await page.getByRole('button', { name: 'Direct offers', exact: true }).click();
  await page.getByRole('button', { name: 'More filters' }).click();
  await page.getByLabel('RENT BELOW · PLN').fill('5000');
  await page.getByLabel('MIN AREA · M²').fill('50');
  await page.getByRole('button', { name: 'Show matching homes' }).click();
  await expect(page.getByText(`T18 baseline ${info.project.name}`).first()).toBeVisible();
  if (info.project.name === 'mobile') await page.getByRole('button', { name: 'Map view' }).click();
  await page.getByRole('button', { name: 'Draw area' }).click();
  const map = page.getByRole('region', { name: 'Map of rental homes' });
  const box = await map.boundingBox();
  expect(box).not.toBeNull();
  for (const [x, y] of [[.2,.2], [.8,.2], [.8,.8], [.2,.8]]) {
    await map.click({ position: { x: box!.width * x, y: box!.height * y } });
  }
  await page.getByRole('button', { name: 'Use this area' }).click();
  await page.getByRole('button', { name: 'Save search', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible();
  await page.getByRole('button', { name: 'New here? Create a free account' }).click();
  await page.getByPlaceholder('you@example.com').fill(`journey-${info.project.name}@example.test`);
  await page.getByPlaceholder('At least 12 characters').fill('synthetic-test-password-123');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Account', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Keep this search close.' })).toBeVisible();
  await expect(page.getByText(/Applied filters: .*Base rent .*5\s*000 PLN.*Area ≥ 50 m².*Direct offers.*Drawn map area/)).toBeVisible();
  await page.getByLabel('SEARCH NAME').fill(`T18 search ${info.project.name}`);
  await page.getByRole('button', { name: 'Save search', exact: true }).last().click();
  await page.getByRole('button', { name: 'Saved searches', exact: true }).first().click();
  await expect(page.getByText(`T18 search ${info.project.name}`)).toHaveCount(1);
  await expect(page.getByText(/0 unread matches · Drawn area/)).toBeVisible();
  await expect(page.getByText(/Applied filters: .*Base rent .*5\s*000 PLN.*Area ≥ 50 m².*Direct offers.*Drawn map area/)).toBeVisible();
  await page.screenshot({ path: info.outputPath('q19-saved-searches.png'), fullPage: true });
  expect(fixture('state', info.project.name).notices).toEqual([]);
  const email = `journey-${info.project.name}@example.test`;
  await page.getByRole('button', { name: 'Notifications', exact: true }).first().click();
  await page.getByRole('button', { name: 'Enable email alerts' }).click();
  await expect(page.getByRole('button', { name: 'Resend confirmation email' })).toBeVisible();
  await page.getByRole('button', { name: 'Resend confirmation email' }).click();
  await expect.poll(async () =>
    (await mailFor(email)).filter(content =>
      content.includes('Confirm your Realtoruch email alerts'),
    ).length,
  ).toBe(1);
  await expect(page.getByRole('status').filter({ hasText: `Check ${email} for a confirmation link.` })).toBeVisible();
  await page.screenshot({ path: info.outputPath('q22-email-confirmation-pending.png'), fullPage: true });
  let confirmation = '';
  await expect.poll(async () => {
    const confirmations = (await mailFor(email)).filter(content =>
      content.includes('Confirm your Realtoruch email alerts'),
    );
    confirmation = confirmations.at(-1)?.match(/#confirm_email=([^\s]+)/)?.[1] || '';
    return !!confirmation;
  }, { timeout: 20_000 }).toBe(true);
  await page.evaluate(token => { window.location.hash = `confirm_email=${token}`; }, confirmation);
  const confirmationResponse = page.waitForResponse(response => response.url().endsWith('/v1/notifications/email/confirm'));
  await page.reload({ waitUntil: 'commit' });
  expect((await confirmationResponse).status()).toBe(200);
  await expect(page.getByText(`Email alerts are on for ${email}.`)).toBeVisible();
  expect(rentalMail(await mailFor(email))).toHaveLength(0);
  const created = fixture('new', info.project.name);
  const id = created.listing_id;
  expect(id).toBeTruthy();
  await expect.poll(() => fixture('state', info.project.name).notices, { timeout: 20_000 }).toEqual([{ kind: 'new_match', listing_id: id }]);
  if (process.env.T18_FAULT_DUPLICATE === '1') {
    await context.tracing.start({ screenshots: true, snapshots: true });
    try {
      fixture('duplicate', info.project.name);
      await page.reload({ waitUntil: 'commit' });
      await page.getByRole('button', { name: 'Notifications', exact: true }).first().click();
      const cards = page.getByText('NEW MATCH', { exact: true });
      await expect(cards).toHaveCount(2);
      await page.screenshot({ path: info.outputPath('synthetic-fault.png'), fullPage: true });
      await expect(cards).toHaveCount(1, { timeout: 1000 });
    } finally {
      await context.tracing.stop({ path: info.outputPath('raw-fault-trace.zip') });
    }
  }
  await expect.poll(async () => rentalMail(await mailFor(email)).length, { timeout: 20_000 }).toBe(1);
  await page.reload({ waitUntil: 'commit' });
  await page.getByRole('button', { name: 'Notifications', exact: true }).first().click();
  await expect(page.getByText('NEW MATCH', { exact: true })).toHaveCount(1);
  await page.getByRole('button', { name: 'Saved searches', exact: true }).first().click();
  await page.getByRole('button', { name: 'View matches' }).click();
  await expect(page.getByText(`T18 synthetic home ${info.project.name}`).first()).toBeVisible();
  if (info.project.name === 'mobile') await page.getByRole('button', { name: 'Map view' }).click();
  const mapMarker = map.locator(`[data-listing-ids~="${id}"]`);
  await expect(mapMarker).toBeVisible();
  if (info.project.name === 'mobile') await page.getByRole('button', { name: 'List view' }).click();
  await page.getByRole('button', { name: `T18 synthetic home ${info.project.name}`, exact: true }).click();
  await page.getByRole('button', { name: 'Save this home' }).click();
  await expect.poll(() => fixture('state', info.project.name).seen).toContainEqual({ listing_id: id, rent_pln: 4500 });
  await expect.poll(() => fixture('state', info.project.name).favorites).toContainEqual({ listing_id: id, price_floor: 4500 });
  await page.getByRole('button', { name: 'Close dialog' }).click();
  fixture('delist', info.project.name);
  await page.reload({ waitUntil: 'commit' });
  await page.getByRole('button', { name: 'Saved homes', exact: true }).first().click();
  await expect(page.getByText(`T18 synthetic home ${info.project.name}`).first()).toBeVisible();
  await expect(page.getByText('DELISTED').first()).toBeVisible();
  await page.getByRole('button', { name: 'Saved searches', exact: true }).first().click();
  await page.getByRole('button', { name: 'View matches' }).click();
  await expect(page.getByText(`T18 baseline ${info.project.name}`).first()).toBeVisible();
  await expect(page.getByRole('button', { name: `T18 synthetic home ${info.project.name}`, exact: true })).toHaveCount(0);
  if (info.project.name === 'mobile') await page.getByRole('button', { name: 'Map view' }).click();
  await expect(map).toBeVisible();
  await expect(mapMarker).toHaveCount(0);
  const repost = fixture('relist', info.project.name);
  expect(repost.listing_id).toBe(id);
  await expect.poll(() => fixture('state', info.project.name).pending, { timeout: 20_000 }).toBe(0);
  expect(fixture('state', info.project.name).notices).toEqual([{ kind: 'new_match', listing_id: id }]);
  expect(rentalMail(await mailFor(email))).toHaveLength(1);
  const dropped = fixture('drop', info.project.name);
  expect(dropped.listing_id).toBe(id);
  await expect.poll(() => fixture('state', info.project.name).notices, { timeout: 20_000 }).toEqual([
    { kind: 'new_match', listing_id: id }, { kind: 'price_drop', listing_id: id },
  ]);
  await expect.poll(() => fixture('state', info.project.name).favorites).toContainEqual({ listing_id: id, price_floor: 4200 });
  await expect.poll(async () => rentalMail(await mailFor(email)).length, { timeout: 20_000 }).toBe(2);
  fixture('delist', info.project.name);
  await expect.poll(() => fixture('state', info.project.name).pending, { timeout: 20_000 }).toBe(0);
  expect(fixture('state', info.project.name).notices).toEqual([{ kind: 'new_match', listing_id: id }, { kind: 'price_drop', listing_id: id }]);
  expect(rentalMail(await mailFor(email))).toHaveLength(2);
  await page.reload({ waitUntil: 'commit' });
  await page.getByRole('button', { name: 'Saved homes', exact: true }).first().click();
  await expect(page.getByText('DELISTED').first()).toBeVisible();
  await page.getByRole('button', { name: 'Notifications', exact: true }).first().click();
  await expect(page.getByText('PRICE DROP ON A SAVED HOME', { exact: true })).toHaveCount(1);
  await page.getByRole('button', { name: 'Saved searches', exact: true }).first().click();
  await page.getByRole('button', { name: 'View matches' }).click();
  await expect(page.getByText(`T18 baseline ${info.project.name}`).first()).toBeVisible();
  await expect(page.getByRole('button', { name: `T18 synthetic home ${info.project.name}`, exact: true })).toHaveCount(0);
  if (info.project.name === 'mobile') await page.getByRole('button', { name: 'Map view' }).click();
  await expect(map).toBeVisible();
  await expect(mapMarker).toHaveCount(0);
  await page.getByRole('button', { name: 'Notifications', exact: true }).first().click();
  await page.getByRole('button', { name: 'Disable email alerts' }).click();
  await expect(page.getByText('Email alerts are off.', { exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath('q22-email-disabled.png'), fullPage: true });
  expect(blocked).toEqual([]);

  await page.getByRole('button', { name: 'Save search', exact: true }).click();
  await page.getByLabel('SEARCH NAME').fill(`T18 keep ${info.project.name}`);
  await page.getByRole('button', { name: 'Save search', exact: true }).last().click();

  let deleteAttempts = 0;
  await context.route('**/v1/me/searches/*', async (route) => {
    if (route.request().method() !== 'DELETE') return route.continue();
    deleteAttempts++;
    if (deleteAttempts === 1)
      return route.fulfill({ status: 503, json: { detail: 'Temporary deletion failure.' } });
    return route.continue();
  });
  await page.getByRole('button', { name: 'Saved searches', exact: true }).first().click();
  await expect(page.getByText(`T18 keep ${info.project.name}`)).toBeVisible();
  await page.getByRole('button', { name: `Remove T18 search ${info.project.name}` }).click();
  await expect(page.getByRole('heading', { name: 'Remove saved search?' })).toBeVisible();
  await expect(page.getByText(`Remove “T18 search ${info.project.name}”?`)).toBeVisible();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.getByText(`T18 search ${info.project.name}`)).toBeVisible();
  await page.getByRole('button', { name: `Remove T18 search ${info.project.name}` }).click();
  await page.getByRole('button', { name: 'Remove search', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Cannot reach the service. Try again.' })).toBeVisible();
  await page.getByRole('button', { name: 'Retry removal', exact: true }).click();
  await expect(page.getByText(`T18 search ${info.project.name}`)).toHaveCount(0);
  await expect(page.getByText(`T18 keep ${info.project.name}`)).toBeVisible();
  expect(deleteAttempts).toBe(2);
});

test('canceling a guest saved-search sign-in creates no saved search', async ({ page, context }, info) => {
  const allowed = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
  const blocked: string[] = [];
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.protocol === 'data:' || (url.hostname === '127.0.0.1' && allowed.has(url.port))) await route.continue();
    else { blocked.push(url.origin); await route.abort('blockedbyclient'); }
  });
  await page.goto('/', { waitUntil: 'commit' });
  await page.getByRole('button', { name: 'Save search', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible();
  await page.getByRole('button', { name: 'Close dialog' }).click();
  await page.locator('button[aria-label="Sign in"]').click();
  await page.getByRole('button', { name: 'New here? Create a free account' }).click();
  const email = `save-cancel-${info.project.name}@example.test`;
  await page.getByPlaceholder('you@example.com').fill(email);
  await page.getByPlaceholder('At least 12 characters').fill('synthetic-test-password-123');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Account', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Saved searches', exact: true }).first().click();
  await expect(page.getByText('Find a search you like, then choose “Save search”.')).toBeVisible();
  expect(blocked).toEqual([]);
});

test('a delayed saved-search removal cannot overwrite the next account draft', async ({ page, context }, info) => {
  const allowed = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.protocol === 'data:' || (url.hostname === '127.0.0.1' && allowed.has(url.port))) await route.continue();
    else await route.abort('blockedbyclient');
  });
  await page.goto('/', { waitUntil: 'commit' });
  await page.locator('button[aria-label="Sign in"]').click();
  await page.getByRole('button', { name: 'New here? Create a free account' }).click();
  await page.getByPlaceholder('you@example.com').fill(`delete-owner-${info.project.name}@example.test`);
  await page.getByPlaceholder('At least 12 characters').fill('synthetic-test-password-123');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Account', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Discover homes', exact: true }).click();
  await page.getByRole('button', { name: 'Save search', exact: true }).click();
  await page.getByLabel('SEARCH NAME').fill(`Owner A search ${info.project.name}`);
  await page.getByRole('button', { name: 'Save search', exact: true }).last().click();
  await page.getByRole('button', { name: 'Saved searches', exact: true }).first().click();

  let markDeleteStarted!: () => void;
  const deleteStarted = new Promise<void>((resolve) => { markDeleteStarted = resolve; });
  let releaseDelete!: () => void;
  const deleteGate = new Promise<void>((resolve) => { releaseDelete = resolve; });
  await context.route('**/v1/me/searches/*', async (route) => {
    if (route.request().method() !== 'DELETE') return route.continue();
    markDeleteStarted();
    await deleteGate;
    return route.continue();
  });
  const deleteResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'DELETE' && response.url().includes('/v1/me/searches/'),
    { timeout: 60_000 },
  );
  await page.getByRole('button', { name: `Remove Owner A search ${info.project.name}` }).click();
  await page.getByRole('button', { name: 'Remove search', exact: true }).click();
  await deleteStarted;
  await page.getByRole('button', { name: 'Close dialog' }).click();
  await page.getByRole('button', { name: 'Account', exact: true }).click();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.locator('button[aria-label="Sign in"]')).toBeVisible();

  await page.locator('button[aria-label="Sign in"]').click();
  await page.getByRole('button', { name: 'New here? Create a free account' }).click();
  await page.getByPlaceholder('you@example.com').fill(`delete-next-${info.project.name}@example.test`);
  await page.getByPlaceholder('At least 12 characters').fill('synthetic-test-password-123');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Account', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Discover homes', exact: true }).click();
  await page.getByRole('button', { name: 'Save search', exact: true }).click();
  await page.getByLabel('SEARCH NAME').fill(`Owner B draft ${info.project.name}`);

  releaseDelete();
  expect((await deleteResponse).status()).toBe(401);
  await expect(page.getByRole('heading', { name: 'Keep this search close.' })).toBeVisible();
  await expect(page.getByLabel('SEARCH NAME')).toHaveValue(`Owner B draft ${info.project.name}`);
  await expect(page.getByText(`Owner A search ${info.project.name}`)).toHaveCount(0);
});
