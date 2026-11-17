import { expect, test, type BrowserContext } from '@playwright/test';
import type { Listing } from '../src/types';
const web = process.env.E2E_WEB_URL!, api = process.env.E2E_API_URL!, auth = process.env.E2E_AUTH_URL!;
const stamp = '2026-11-17T10:00:00Z';
const photo = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jR1sAAAAASUVORK5CYII=', 'base64');
const homes: Listing[] = Array.from({ length: 4 }, (_, index) => ({
  id: `quality-home-${index}`, title: ['Sunny two-room apartment', 'Quiet home by the park', 'Bright studio near the tram', 'Spacious family apartment'][index],
  city: 'Kraków', address: `Example Street ${index + 1}`, district: 'Krowodrza', region: 'małopolskie',
  description: 'A synthetic home used to check layout, readable costs and clear rental decisions.',
  lat: 50.06 + index / 1000, lon: 19.94 + index / 1000, area_m2: 55, rooms: 2, floor: 2,
  rent_pln: 3500 + index * 200, fees_pln: index ? 500 : null, deposit_pln: 3500, commission_pln: 0,
  total_monthly_pln: index ? 4000 + index * 200 : 3500, advertiser_type: 'private', property_type: 'apartment',
  status: 'active', images: [`${web}/quality-photo.png`], amenities: ['balcony'], is_demo: false,
  first_seen: stamp, last_seen: stamp, risk_score: 0, risk_flags: [], sources: [],
}));
async function fixture(context: BrowserContext) {
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (![web, api, auth].includes(url.origin) && url.protocol !== 'data:') return route.abort();
    if (url.origin === web && url.pathname === '/quality-photo.png') return route.fulfill({ contentType: 'image/png', body: photo });
    if (url.origin !== api || route.request().method() === 'OPTIONS') return route.continue();
    const json = (value: object) => route.fulfill({ json: value, headers: { 'Access-Control-Allow-Origin': web, 'Access-Control-Allow-Credentials': 'true' } });
    const path = url.pathname;
    if (path === '/v1/market/summary') return json({ homes: 4, source_listings: 4, duplicates_removed: 0, demo: false });
    if (path === '/v1/listings') return json({ items: homes, total: homes.length, page: 1, page_size: 24, engine: 'sql' });
    const home = homes.find(item => path === `/v1/listings/${item.id}`); if (home) return json(home);
    if (path === '/v1/me/favorites') return json({ items: [homes[1], { ...homes[2], status: 'inactive' }] });
    if (path === '/v1/me/listing-state') return json({ seen_ids: [] });
    if (path.startsWith('/v1/me/seen/')) return json({ seen: true });
    if (path === '/v1/me/advertiser') return json({ profile: { id: 'synthetic-owner', name: 'Synthetic owner', kind: 'private', description: 'Local visual fixture.' } });
    if (path === '/v1/me/adverts') return json({ items: [] });
    if (path === '/v1/me/conversations') return json({ items: [{ id: 'quality-thread', title: homes[0].title, listing_id: null, updated_at: stamp, unread_count: 0, blocked: false, can_unblock: false }], next_cursor: null });
    if (path === '/v1/me/conversations/quality-thread') return json({ id: 'quality-thread', items: [
      { id: 'first', body: 'Hello, is this apartment still available?', mine: false, created_at: stamp },
      { id: 'second', body: 'Yes. We can arrange a viewing this week.', mine: true, created_at: stamp },
    ], next_cursor: null, blocked: false, can_unblock: false });
    if (path.endsWith('/read')) return json({ read: true });
    return route.continue();
  });
}

test.describe('reviewed visual fixture', () => {
  test.use({ locale: 'en-GB', timezoneId: 'Europe/Warsaw' });
  test('Q39 discovery detail saved owner and messages @visual', async ({ page, context }, info) => {
    await fixture(context); await page.clock.setFixedTime(new Date(stamp));
    await page.setViewportSize({ width: info.project.name === 'mobile' ? 390 : 1440, height: 844 });
    await page.goto('/'); await expect(page.getByRole('button', { name: 'View Sunny two-room apartment', exact: true })).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    const shot = async (name: string) => {
      if (process.env.QUALITY_OVERLAP_FAULT === '1') await page.addStyleTag({ content: '[role="heading"] { position: fixed !important; top: 0 !important; background: red !important; z-index: 999999 !important; }' });
      if (process.env.QUALITY_CAPTURE === '1') await page.screenshot({ path: info.outputPath(`${name}.png`), animations: 'disabled', caret: 'hide' });
      else await expect(page).toHaveScreenshot(`${name}.png`, { animations: 'disabled', caret: 'hide', maxDiffPixelRatio: 0.002 });
    };
    await shot('discovery');
    await page.getByRole('button', { name: 'View Sunny two-room apartment', exact: true }).click();
    await expect(page.getByText('A synthetic home used to check layout, readable costs and clear rental decisions.')).toBeVisible();
    await shot('detail'); await page.getByRole('button', { name: 'Close dialog', exact: true }).click();
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await page.getByRole('button', { name: 'New here? Create a free account', exact: true }).click();
    await page.getByLabel('EMAIL', { exact: true }).fill(`quality-${info.project.name}@example.test`);
    await page.getByLabel('PASSWORD', { exact: true }).fill('synthetic-quality-password-123');
    await page.getByRole('button', { name: 'Create account', exact: true }).click();
    await page.getByRole('button', { name: 'Saved homes', exact: true }).click();
    await expect(page.getByRole('button', { name: 'View Quiet home by the park', exact: true })).toBeVisible();
    await shot('saved');
    await page.getByRole('button', { name: 'Account', exact: true }).click(); await page.getByRole('button', { name: 'My rental adverts', exact: true }).click();
    await page.getByRole('button', { name: 'Create rental advert', exact: true }).click();
    await expect(page.getByLabel('TITLE', { exact: true })).toBeVisible();
    const geometry = await page.getByLabel('DESCRIPTION', { exact: true }).boundingBox();
    const next = await page.getByRole('button', { name: 'apartment', exact: true }).boundingBox();
    expect(next!.y).toBeGreaterThan(geometry!.y + geometry!.height);
    await shot('owner'); await page.getByRole('button', { name: 'Back to adverts', exact: true }).click();
    await page.getByRole('button', { name: 'Messages', exact: true }).click();
    await page.getByRole('button', { name: 'Open conversation: Sunny two-room apartment', exact: true }).click();
    await expect(page.getByText('Yes. We can arrange a viewing this week.', { exact: true })).toBeVisible();
    await shot('messages');
  });
});
