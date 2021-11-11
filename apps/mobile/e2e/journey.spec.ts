import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import { readdir, readFile } from 'node:fs/promises';

// Start the fault trace only after token-bearing links have been consumed.
test.use({ trace: 'off' });

function fixture(action: string, profile: string) {
  return JSON.parse(execFileSync(process.env.E2E_PYTHON!, [join(__dirname, 'fixture.py'), action, profile], { encoding: 'utf8' }));
}

async function mailFor(email: string) {
  const files = await readdir(process.env.E2E_MAIL_DIR!).catch(() => []);
  const contents = await Promise.all(files.filter(f => f.endsWith('.eml')).map(f => readFile(join(process.env.E2E_MAIL_DIR!, f), 'utf8')));
  return contents.filter(content => content.includes(email)).map(content => content.replace(/=\r?\n/g, '').replace(/=3D/gi, '='));
}
function rentalMail(contents: string[]) {
  return contents.filter(content => !content.includes('Verify your Realtoruch email') && !content.includes('Confirm your Realtoruch email alerts'));
}

test('draw and save a filtered search against a synthetic baseline', async ({ page, context }, info) => {
  const allowed = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
  const blocked: string[] = [];
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.protocol === 'data:' || (url.hostname === '127.0.0.1' && allowed.has(url.port))) await route.continue();
    else { blocked.push(url.origin); await route.abort('blockedbyclient'); }
  });
  fixture('baseline', info.project.name);
  await page.goto('/', { waitUntil: 'commit' });
  await page.locator('button[aria-label="Sign in"]').click();
  await page.getByRole('button', { name: 'New here? Create a free account' }).click();
  await page.getByPlaceholder('you@example.com').fill(`journey-${info.project.name}@example.test`);
  await page.getByPlaceholder('At least 12 characters').fill('synthetic-test-password-123');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Account', exact: true })).toBeVisible();
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
  await page.getByLabel('SEARCH NAME').fill(`T18 search ${info.project.name}`);
  await page.getByRole('button', { name: 'Save search', exact: true }).last().click();
  await page.getByRole('button', { name: 'Saved searches', exact: true }).first().click();
  await expect(page.getByText(`T18 search ${info.project.name}`)).toBeVisible();
  await expect(page.getByText(/0 unread matches · Drawn area/)).toBeVisible();
  expect(fixture('state', info.project.name).notices).toEqual([]);
  const email = `journey-${info.project.name}@example.test`;
  await page.getByRole('button', { name: 'Notifications', exact: true }).first().click();
  await page.getByRole('button', { name: 'Enable email alerts' }).click();
  let confirmation = '';
  await expect.poll(async () => {
    confirmation = (await mailFor(email)).join('\n').match(/#confirm_email=([^\s]+)/)?.[1] || '';
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
  await expect(page.getByRole('button', { name: `T18 synthetic home ${info.project.name}, 4500 zł` })).toBeVisible();
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
  await expect(page.getByRole('button', { name: `T18 synthetic home ${info.project.name}, 4500 zł` })).toHaveCount(0);
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
  await expect(page.getByRole('button', { name: `T18 synthetic home ${info.project.name}, 4200 zł` })).toHaveCount(0);
  expect(blocked).toEqual([]);
});
