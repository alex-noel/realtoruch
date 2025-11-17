import { test, expect } from '@playwright/test';

test('notification retry and read failures preserve the inbox', async ({ page, context }, info) => {
  const allowed = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.protocol === 'data:' || (url.hostname === '127.0.0.1' && allowed.has(url.port))) await route.continue();
    else await route.abort('blockedbyclient');
  });
  const item = (id: string) => ({ id, listing_id: id, search_id: null, kind: 'new_match', title: `Synthetic ${id}`, rent_pln: 1000, previous_rent_pln: null, created_at: '2026-01-01T00:00:00', read_at: null, listing_status: 'active' });
  let moreAttempts = 0;
  let burst = false;
  await page.route(`${process.env.E2E_API_URL}/v1/me/notifications*`, async route => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/read')) return route.fulfill({ status: 503, json: { detail: 'offline' } });
    if (url.searchParams.get('cursor') === 'gap') return route.fulfill({ json: { items: Array.from({ length: 10 }, (_, i) => ({ ...item(`burst-${String(i + 30).padStart(2, '0')}`), created_at: '2026-02-01T00:00:00' })), unread_count: 42, page: 1, page_size: 30, has_more: false, next_cursor: null } });
    if (url.searchParams.has('cursor')) {
      if (++moreAttempts === 1) return route.fulfill({ status: 503, json: { detail: 'offline' } });
      return route.fulfill({ json: { items: [item('older')], unread_count: 2, page: 1, page_size: 30, has_more: false, next_cursor: null } });
    }
    if (burst) return route.fulfill({ json: { items: Array.from({ length: 30 }, (_, i) => ({ ...item(`burst-${String(i).padStart(2, '0')}`), created_at: '2026-02-01T00:00:00' })), unread_count: 42, page: 1, page_size: 30, has_more: true, next_cursor: 'gap' } });
    return route.fulfill({ json: { items: [item('head')], unread_count: 2, page: 1, page_size: 30, has_more: true, next_cursor: 'next' } });
  });
  await page.goto('/', { waitUntil: 'commit' });
  await page.locator('button[aria-label="Sign in"]').click();
  await page.getByRole('button', { name: 'New here? Create a free account' }).click();
  await page.getByPlaceholder('you@example.com').fill(`q21-${info.project.name}@example.test`);
  await page.getByPlaceholder('At least 12 characters').fill('synthetic-test-password-123');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Account', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Notifications', exact: true }).first().click();
  await expect(page.getByText('Synthetic head')).toBeVisible();
  await page.getByRole('button', { name: 'Mark as read' }).click();
  await expect(page.getByText('Could not mark this notification as read. Please try again.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Mark as read' })).toBeVisible();
  await page.getByRole('button', { name: 'Older notifications', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Retry older notifications' })).toBeVisible();
  await expect(page.getByText('Synthetic head')).toBeVisible();
  await page.getByRole('button', { name: 'Retry older notifications' }).click();
  await expect(page.getByText('Synthetic older')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Older notifications', exact: true })).toHaveCount(0);
  expect(moreAttempts).toBe(2);
  burst = true;
  await expect(page.getByText('Synthetic burst-00')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText('Synthetic older')).toBeVisible();
  await page.getByRole('button', { name: 'Older notifications', exact: true }).click();
  await expect(page.getByText('Synthetic burst-39')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Older notifications', exact: true })).toHaveCount(0);
  const titles = await page.getByText(/^Synthetic /).allTextContents();
  expect(titles).toEqual([...Array.from({ length: 40 }, (_, i) => `Synthetic burst-${String(i).padStart(2, '0')}`), 'Synthetic head', 'Synthetic older']);
  await page.screenshot({ path: info.outputPath('synthetic-inbox.png'), fullPage: true });
});
