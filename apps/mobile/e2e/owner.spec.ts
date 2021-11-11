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

test('owner publishes, edits, messages a renter and withdraws', async ({ page, context, browser }, info) => {
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
  await page.getByRole('button', { name: 'Publish', exact: true }).click();
  await expect(page.getByText('PUBLISHED', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await page.getByLabel('MONTHLY BASE RENT (PLN)').fill('4200');
  await page.getByRole('button', { name: 'Save and update advert' }).click();
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
