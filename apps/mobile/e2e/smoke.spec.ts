import { test, expect } from '@playwright/test';
import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';

test('export loads local catalog and opens sign-in', async ({ page, context }) => {
  const allowed = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
  const blocked: string[] = [];
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.protocol === 'data:' || (url.hostname === '127.0.0.1' && allowed.has(url.port))) {
      await route.continue();
    } else {
      blocked.push(url.origin);
      await route.abort('blockedbyclient');
    }
  });
  const anonymousRefresh = page.waitForResponse(response => response.url().endsWith('/v1/auth/refresh'));
  await page.goto('/', { waitUntil: 'commit' });
  expect((await anonymousRefresh).status()).toBe(401);
  await expect(page.getByLabel('City')).toBeVisible();
  await expect(page.getByText('Your session ended. Sign in again.')).toHaveCount(0);
  await expect(page.getByText('The account session changed.')).toHaveCount(0);
  await page.locator('button[aria-label="Sign in"]').click();
  await expect(page.getByPlaceholder('you@example.com')).toBeVisible();
  expect(blocked).toEqual([]);
});

test('synthetic account survives reload and signs out', async ({ page, context }, info) => {
  const allowed = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
  const blocked: string[] = [];
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.protocol === 'data:' || (url.hostname === '127.0.0.1' && allowed.has(url.port))) await route.continue();
    else { blocked.push(url.origin); await route.abort('blockedbyclient'); }
  });
  await page.goto('/', { waitUntil: 'commit' });
  await expect(page.getByText('Your session ended. Sign in again.')).toHaveCount(0);
  await page.locator('button[aria-label="Sign in"]').click();
  await page.getByRole('button', { name: 'New here? Create a free account' }).click();
  const email = `browser-${info.project.name}@example.test`;
  await page.getByPlaceholder('you@example.com').fill(email);
  await page.getByPlaceholder('At least 12 characters').fill('synthetic-test-password-123');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Account', exact: true })).toBeVisible();
  let verification = '';
  await expect.poll(async () => {
    const files = await readdir(process.env.E2E_MAIL_DIR!).catch(() => []);
    for (const file of files.filter(f => f.endsWith('.eml'))) {
      const content = await readFile(join(process.env.E2E_MAIL_DIR!, file), 'utf8');
      if (content.includes(email)) verification = content.replace(/=\r?\n/g, '').replace(/=3D/gi, '=').match(/#verify_account=([^\s]+)/)?.[1] || '';
    }
    return !!verification;
  }, { timeout: 15_000 }).toBe(true);
  await page.evaluate(token => { window.location.hash = `verify_account=${token}`; }, verification);
  const verificationResponse = page.waitForResponse(response => response.url().endsWith('/v1/auth/verify-email'));
  await page.reload({ waitUntil: 'commit' });
  expect((await verificationResponse).status()).toBe(200);
  await expect(page.getByRole('button', { name: 'Account', exact: true })).toBeVisible();
  const second = await context.newPage();
  await second.goto('/', { waitUntil: 'commit' });
  await expect(second.getByRole('button', { name: 'Account', exact: true })).toBeVisible();
  let refreshRequests = 0;
  let release!: () => void;
  let reached!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const firstReached = new Promise<void>(resolve => { reached = resolve; });
  await context.route(`${process.env.E2E_AUTH_URL}/v1/auth/refresh`, async route => {
    refreshRequests++;
    if (refreshRequests === 1) { reached(); await gate; }
    await route.continue();
  });
  try {
    await page.reload({ waitUntil: 'commit' });
    await firstReached;
    await second.reload({ waitUntil: 'commit' });
    await expect.poll(() => second.evaluate(async () =>
      (await navigator.locks.query()).pending?.filter(lock => lock.name === 'realtoruch-refresh').length || 0
    )).toBeGreaterThan(0);
    expect(refreshRequests).toBe(1);
  } finally { release(); }
  await expect(page.getByRole('button', { name: 'Account', exact: true })).toBeVisible();
  await expect(second.getByRole('button', { name: 'Account', exact: true })).toBeVisible();
  await expect.poll(() => refreshRequests).toBe(2);
  await second.getByRole('button', { name: 'Account', exact: true }).click();
  await expect(second.getByText(email)).toBeVisible();
  await page.getByRole('button', { name: 'Account', exact: true }).click();
  await expect(page.getByText('Email verified', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Account', exact: true })).toHaveCount(0);
  const revokedRefresh = second.waitForResponse(response => response.url().endsWith('/v1/auth/refresh'));
  await second.reload({ waitUntil: 'commit' });
  expect((await revokedRefresh).status()).toBe(401);
  await expect(second.locator('button[aria-label="Sign in"]')).toBeVisible();
  await expect(second.getByRole('button', { name: 'Account', exact: true })).toHaveCount(0);
  await expect(second.getByText(email)).toHaveCount(0);
  expect(blocked).toEqual([]);
});

test('a stale tab cannot retry an account mutation as a different signed-in account', async ({ page, context }, info) => {
  const ports = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
  const blocked: string[] = [];
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.protocol === 'data:' || (url.hostname === '127.0.0.1' && ports.has(url.port))) await route.continue();
    else { blocked.push(url.origin); await route.abort('blockedbyclient'); }
  });
  const register = async (tab: typeof page, email: string) => {
    await tab.locator('button[aria-label="Sign in"]').click();
    await tab.getByRole('button', { name: 'New here? Create a free account' }).click();
    await tab.getByPlaceholder('you@example.com').fill(email);
    await tab.getByPlaceholder('At least 12 characters').fill('synthetic-test-password-123');
    await tab.getByRole('button', { name: 'Create account', exact: true }).click();
    await expect(tab.getByRole('button', { name: 'Account', exact: true })).toBeVisible();
  };
  await page.goto('/', { waitUntil: 'commit' });
  await register(page, `switch-a-${info.project.name}@example.test`);
  const second = await context.newPage();
  await second.goto('/', { waitUntil: 'commit' });
  await expect(second.getByRole('button', { name: 'Account', exact: true })).toBeVisible();
  await second.getByRole('button', { name: 'Account', exact: true }).click();
  await second.getByRole('button', { name: 'Sign out', exact: true }).click();
  await register(second, `switch-b-${info.project.name}@example.test`);
  let mutations = 0;
  await page.route(`${process.env.E2E_API_URL}/v1/me/searches`, async route => {
    if (route.request().method() !== 'POST') return route.fallback();
    mutations++;
    if (mutations === 1) return route.fulfill({ status: 401, contentType: 'application/json', body: '{"detail":"expired"}' });
    return route.continue();
  });
  await page.getByRole('button', { name: 'Save search', exact: true }).click();
  await page.getByLabel('SEARCH NAME').fill('Must not transfer to account B');
  await page.getByRole('button', { name: 'Save search', exact: true }).last().click();
  await expect(page.getByText('Your session ended. Sign in again.')).toBeVisible();
  expect(mutations).toBe(1);
  await expect(page.getByRole('button', { name: 'Account', exact: true })).toHaveCount(0);
  await second.getByRole('button', { name: 'Saved searches', exact: true }).first().click();
  await expect(second.getByText('Must not transfer to account B')).toHaveCount(0);
  expect(blocked).toEqual([]);
});
