import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import type { Listing, SearchResult } from '../src/types';

test('search controls preserve rent, area, advertiser, polygon and commission boundaries', async ({ page, context }, info) => {
  const allowed = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
  const blocked: string[] = [];
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.protocol === 'data:' || (url.hostname === '127.0.0.1' && allowed.has(url.port))) await route.continue();
    else { blocked.push(url.origin); await route.abort('blockedbyclient'); }
  });
  execFileSync(process.env.E2E_PYTHON!, [join(__dirname, 'fixture.py'), 'boundaries', info.project.name]);
  await page.goto('/', { waitUntil: 'commit' });
  await page.getByRole('button', { name: 'Direct offers', exact: true }).click();
  await page.getByRole('button', { name: 'More filters' }).click();
  await page.getByLabel('RENT BELOW · PLN').fill('5000');
  await page.getByLabel('MIN AREA · M²').fill('50');
  await page.getByRole('button', { name: 'Show matching homes' }).click();
  if (info.project.name === 'mobile') await page.getByRole('button', { name: 'Map view' }).click();
  await page.getByRole('button', { name: 'Draw area' }).click();
  const map = page.getByRole('region', { name: 'Map of rental homes' });
  const box = await map.boundingBox();
  expect(box).not.toBeNull();
  for (const [x, y] of [[.2,.2], [.8,.2], [.8,.8], [.2,.8]])
    await map.click({ position: { x: box!.width * x, y: box!.height * y } });
  const results = page.waitForResponse(response => response.url().includes('/v1/listings?') && response.status() === 200);
  await page.getByRole('button', { name: 'Use this area' }).click();
  await results;
  if (info.project.name === 'mobile') await page.getByRole('button', { name: 'List view' }).click();
  const title = (name: string) => `T18 boundary ${info.project.name} ${name}`;
  await expect(page.getByText(title('good'), { exact: true })).toBeVisible();
  await expect(page.getByText(title('unknown'), { exact: true })).toBeVisible();
  for (const name of ['price', 'area', 'agency', 'outside'])
    await expect(page.getByText(title(name), { exact: true })).toHaveCount(0);
  const filtered = page.waitForResponse(response => response.url().includes('/v1/listings?') && response.status() === 200);
  await page.getByRole('button', { name: 'No commission', exact: true }).click();
  await filtered;
  await expect(page.getByText(title('good'), { exact: true })).toBeVisible();
  await expect(page.getByText(title('unknown'), { exact: true })).toHaveCount(0);
  expect(blocked).toEqual([]);
});

test('filter validation parses decimal commas and enforces rent-exclusive and area-inclusive bounds', async ({ page, context }, info) => {
  const allowed = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
  const blocked: string[] = [];
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.protocol === 'data:' || (url.hostname === '127.0.0.1' && allowed.has(url.port))) return route.continue();
    blocked.push(url.origin);
    return route.abort('blockedbyclient');
  });
  execFileSync(process.env.E2E_PYTHON!, [join(__dirname, 'fixture.py'), 'boundaries', info.project.name]);
  await page.goto('/', { waitUntil: 'commit' });
  await page.getByRole('button', { name: 'More filters' }).click();

  const minRent = page.getByLabel('MIN RENT · PLN');
  const maxRent = page.getByLabel('RENT BELOW · PLN');
  const minArea = page.getByLabel('MIN AREA · M²');
  const maxArea = page.getByLabel('MAX AREA · M²');
  await minRent.fill('2000');
  await maxRent.fill('2000');
  await minArea.fill('50,5');
  await maxArea.fill('50.5');
  await page.getByRole('button', { name: 'Show matching homes' }).click();

  await expect(minRent).toHaveAttribute('aria-invalid', 'true');
  await expect(maxRent).toHaveAttribute('aria-invalid', 'true');
  await expect(minArea).not.toHaveAttribute('aria-invalid', 'true');
  await expect(maxArea).not.toHaveAttribute('aria-invalid', 'true');
  await expect(page.getByText('Minimum rent must be below the exclusive rent maximum.')).toBeVisible();
  await expect(page.getByText('Rent maximum must be above minimum rent.')).toBeVisible();
  await expect(minArea).toHaveValue('50,5');
  await expect(maxArea).toHaveValue('50.5');

  await maxRent.fill('2001');
  await expect(minRent).not.toHaveAttribute('aria-invalid', 'true');
  await expect(maxRent).not.toHaveAttribute('aria-invalid', 'true');
  const matchingRequest = page.waitForRequest(request => {
    const url = new URL(request.url());
    return url.pathname === '/v1/listings' &&
      url.searchParams.get('min_area') === '50.5' &&
      url.searchParams.get('max_area') === '50.5';
  });
  await page.getByRole('button', { name: 'Show matching homes' }).click();
  const request = await matchingRequest;
  const applied = new URL(request.url()).searchParams;
  expect(applied.get('min_price')).toBe('2000');
  expect(applied.get('max_price')).toBe('2001');
  expect(applied.get('max_price_exclusive')).toBe('true');
  expect(applied.get('min_area')).toBe('50.5');
  expect(applied.get('max_area')).toBe('50.5');
  expect(blocked).toEqual([]);
});

function pagedHomes(): Listing[] {
  const image = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
  return Array.from({ length: 49 }, (_, index) => ({
    id: `q09-home-${index + 1}`,
    title: `Q09 home ${index + 1}`,
    description: 'Fictional apartment for the pagination check',
    city: 'Kraków', district: 'Krowodrza', region: 'małopolskie', address: 'Fixture street',
    lat: 50.0647 + (index % 24 === 0 ? 0 : (index % 2 ? .018 : -.018)),
    lon: 19.945 + (index % 24 === 0 ? 0 : ((index % 6) - 2.5) * .01),
    area_m2: 55, rooms: 2, floor: 2, rent_pln: 4000, fees_pln: 500, deposit_pln: 4000,
    commission_pln: 0, total_monthly_pln: 4500, advertiser_type: 'private',
    property_type: 'apartment', status: 'active', images: [image], amenities: [], is_demo: true,
    first_seen: '2026-01-01T12:00:00Z', last_seen: '2026-01-01T12:00:00Z',
    risk_score: 0, risk_flags: [], sources: [],
  }));
}

test('results pager keeps cards and pins on the same page and preserves browsing position', async ({ page, context }, info) => {
  const allowed = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
  const blocked: string[] = [];
  const homes = pagedHomes();
  const requests: URLSearchParams[] = [];
  let releasePageTwo!: () => void;
  const pageTwoPending = new Promise<void>(resolve => { releasePageTwo = resolve; });
  let holdPageTwo = true;
  let releaseFilter!: () => void;
  const filterPending = new Promise<void>(resolve => { releaseFilter = resolve; });
  let failFilter = true;
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.protocol === 'data:') return route.continue();
    if (url.hostname !== '127.0.0.1' || !allowed.has(url.port)) {
      blocked.push(url.origin);
      return route.abort('blockedbyclient');
    }
    if (url.origin === process.env.E2E_API_URL && url.pathname === '/v1/listings') {
      requests.push(url.searchParams);
      const number = Number(url.searchParams.get('page'));
      const size = Number(url.searchParams.get('page_size'));
      if (number === 2 && holdPageTwo) {
        holdPageTwo = false;
        await pageTwoPending;
      }
      if (url.searchParams.get('no_commission') === 'true' && failFilter) {
        failFilter = false;
        await filterPending;
        return route.fulfill({ status: 503, json: { detail: 'Synthetic search failure' } });
      }
      const result: SearchResult = {
        items: homes.slice((number - 1) * size, number * size),
        total: homes.length, page: number, page_size: size, engine: 'fixture',
      };
      return route.fulfill({ json: result });
    }
    const home = homes.find(item => url.pathname === `/v1/listings/${item.id}`);
    if (url.origin === process.env.E2E_API_URL && home) return route.fulfill({ json: home });
    return route.continue();
  });

  await page.goto('/', { waitUntil: 'commit' });
  const direct = page.getByRole('button', { name: 'Direct offers', exact: true });
  await direct.click();
  const mapView = page.getByRole('button', { name: 'Map view' });
  const listView = page.getByRole('button', { name: 'List view' });
  await mapView.click();
  const split = info.project.name === 'desktop';
  const map = page.getByRole('region', { name: 'Map of rental homes' });
  const pins = map.getByRole('button', { name: /^Q09 home \d+, 4000 zł$/ });
  const cards = page.getByRole('button', { name: /^View Q09 home \d+$/ });
  const previous = page.getByRole('button', { name: 'Previous', exact: true });
  const next = page.getByRole('button', { name: 'Next', exact: true });
  const heading = page.getByRole('heading', { name: '49 homes in Kraków' });
  const pageLabel = (number: number) => page.getByText(`Page ${number} of 3`, { exact: true });

  async function checkPage(number: number, mode: 'map' | 'list' | 'split') {
    await expect(pageLabel(number)).toBeVisible();
    const expected = homes.slice((number - 1) * 24, number * 24);
    if (mode === 'list') {
      await expect(map).toHaveCount(0);
    } else {
      await expect(pins).toHaveCount(expected.length);
      await expect.poll(() => pins.evaluateAll(nodes => nodes.map(node => node.getAttribute('data-listing-id'))))
        .toEqual(expected.map(home => home.id));
    }
    if (mode === 'map') {
      await expect(cards).toHaveCount(0);
    } else {
      await expect.poll(() => cards.evaluateAll(nodes => nodes.map(node => node.getAttribute('aria-label'))))
        .toEqual(expected.map(home => `View ${home.title}`));
    }
  }

  async function closeDetailsAndCheckPosition(opener: ReturnType<typeof page.getByRole>) {
    await opener.scrollIntoViewIfNeeded();
    const scrollTop = () => heading.evaluate(node => {
      let ancestor = node.parentElement;
      while (ancestor && !['auto', 'scroll'].includes(getComputedStyle(ancestor).overflowY)) {
        ancestor = ancestor.parentElement;
      }
      return ancestor?.scrollTop ?? window.scrollY;
    });
    const before = await scrollTop();
    expect(before).toBeGreaterThan(0);
    await opener.click();
    const detail = page.getByRole('dialog', { name: 'A closer look' });
    await expect(detail.getByText('Q09 home 25', { exact: true })).toBeVisible();
    await detail.getByRole('button', { name: 'Close dialog' }).click();
    await expect(detail).toHaveCount(0);
    await expect(opener).toBeFocused();
    await expect.poll(scrollTop).toBeCloseTo(before, 0);
    await expect(pageLabel(2)).toBeVisible();
  }

  const mapMode = split ? 'split' : 'map';
  await checkPage(1, mapMode);
  await expect(previous).toBeDisabled();
  await next.click();
  try {
    await expect.poll(() => requests.at(-1)?.get('page')).toBe('2');
    await expect(previous).toBeDisabled();
    await expect(next).toBeDisabled();
    await expect(pageLabel(1)).toBeVisible();
    await expect(heading).toBeFocused();
    await expect(heading).toBeInViewport();
  } finally {
    releasePageTwo();
  }
  await checkPage(2, mapMode);
  if (!split) {
    await page.screenshot({ path: info.outputPath('q09-map-page-two.png') });
    await closeDetailsAndCheckPosition(map.getByRole('button', { name: 'Q09 home 25, 4000 zł', exact: true }));
  }
  await next.click();
  await checkPage(3, mapMode);
  await expect(next).toBeDisabled();
  await previous.click();
  await checkPage(2, mapMode);

  const requestCount = requests.length;
  await listView.click();
  await checkPage(2, 'list');
  await expect(direct).toHaveAttribute('aria-pressed', 'true');
  expect(requests).toHaveLength(requestCount);
  await closeDetailsAndCheckPosition(page.getByRole('button', { name: 'View Q09 home 25', exact: true }));
  await previous.click();
  await checkPage(1, 'list');
  await expect(previous).toBeDisabled();
  await next.click();
  await checkPage(2, 'list');
  await next.click();
  await checkPage(3, 'list');
  await expect(next).toBeDisabled();
  await mapView.click();
  await checkPage(3, mapMode);
  await previous.click();
  await checkPage(2, mapMode);
  expect(requests.at(-1)?.get('advertiser')).toBe('private');
  expect(requests.at(-1)?.get('city')).toBe('Kraków');

  await page.getByRole('button', { name: 'No commission', exact: true }).click();
  try {
    await expect.poll(() => requests.at(-1)?.get('no_commission')).toBe('true');
    expect(requests.at(-1)?.get('page')).toBe('1');
    await expect(pageLabel(2)).toBeVisible();
    await expect(previous).toBeDisabled();
    await expect(next).toBeDisabled();
  } finally {
    releaseFilter();
  }
  await expect(page.getByRole('alert')).toHaveText(/Could not update homes/);
  await expect(previous).toBeDisabled();
  await expect(next).toBeDisabled();
  await page.getByRole('button', { name: 'Retry search' }).click();
  await checkPage(1, mapMode);
  await expect(previous).toBeDisabled();
  await expect(next).toBeEnabled();
  expect(blocked).toEqual([]);
});

test.describe('explicit sort', () => {
  test.use({ hasTouch: true });

  test('sort choices work by keyboard and touch and keep the latest result', async ({ page, context }, info) => {
    if (info.project.name === 'mobile') await page.setViewportSize({ width: 320, height: 800 });
    const allowed = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
    const blocked: string[] = [];
    const homes = pagedHomes();
    const requests: URLSearchParams[] = [];
    let releaseOlderSort!: () => void;
    const olderSortPending = new Promise<void>(resolve => { releaseOlderSort = resolve; });

    // Simulate an older transport response that arrives even after cancellation.
    await page.addInitScript(() => {
      const fetch = window.fetch.bind(window);
      window.fetch = (input, init) => {
        if (typeof input === 'string') {
          const url = new URL(input, location.href);
          if (url.pathname === '/v1/listings' && url.searchParams.get('sort') === 'price_asc')
            return fetch(input, { ...init, signal: undefined });
        }
        return fetch(input, init);
      };
    });
    await context.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.protocol === 'data:') return route.continue();
      if (url.hostname !== '127.0.0.1' || !allowed.has(url.port)) {
        blocked.push(url.origin);
        return route.abort('blockedbyclient');
      }
      if (url.origin !== process.env.E2E_API_URL || url.pathname !== '/v1/listings')
        return route.continue();

      requests.push(url.searchParams);
      const sort = url.searchParams.get('sort');
      const number = Number(url.searchParams.get('page'));
      const size = Number(url.searchParams.get('page_size'));
      if (sort === 'price_asc') await olderSortPending;
      const result: SearchResult = {
        items: homes.slice((number - 1) * size, number * size).map((home, index) => ({
          ...home, title: `Q08 ${sort} page ${number} home ${index + 1}`,
        })),
        total: homes.length, page: number, page_size: size, engine: 'fixture',
      };
      return route.fulfill({ json: result });
    });

    await page.goto('/', { waitUntil: 'commit' });
    const button = (name: string) => page.getByRole('button', { name, exact: true });
    const dialog = page.getByRole('dialog', { name: 'Sort homes' });
    const choice = (name: string) => dialog.getByRole('button', { name, exact: true });
    const trigger = (label: string) => button(`Change sort order, ${label} selected`);
    const result = (sort: string, number = 1) => button(`Q08 ${sort} page ${number} home 1`);
    const direct = button('Direct offers');
    await direct.click();
    await expect.poll(() => requests.at(-1)?.get('advertiser')).toBe('private');
    await button('No commission').click();
    await expect.poll(() => requests.at(-1)?.get('no_commission')).toBe('true');
    await button('Next').click();
    await expect(result('newest', 2)).toBeVisible();
    const beforeSort = requests.length;
    const nextQuery = new URLSearchParams(requests.at(-1));
    nextQuery.set('page', '1');
    nextQuery.set('sort', 'price_desc');

    await page.getByRole('button', { name: /^Change sort order/ }).focus();
    await page.keyboard.press('Enter');
    await expect(dialog).toBeVisible();
    await expect(choice('Close dialog')).toBeFocused();
    for (const label of ['Newest first', 'Lowest rent', 'Highest rent', 'Largest first']) {
      await expect(choice(label)).toBeInViewport({ ratio: 1 });
      await expect(choice(label)).toHaveAttribute('aria-pressed', String(label === 'Newest first'));
    }
    if (info.project.name === 'mobile')
      await page.screenshot({ path: info.outputPath('q08-sort-320px.png') });
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(trigger('Newest first')).toBeFocused();
    await trigger('Newest first').tap();
    await choice('Cancel').tap();
    await expect(dialog).toHaveCount(0);
    await expect(result('newest', 2)).toBeVisible();
    expect(requests).toHaveLength(beforeSort);

    await trigger('Newest first').tap();
    await choice('Newest first').tap();
    await expect(dialog).toHaveCount(0);
    await expect(result('newest', 2)).toBeVisible();
    expect(requests).toHaveLength(beforeSort);

    await trigger('Newest first').press('Enter');
    for (const label of ['Newest first', 'Lowest rent', 'Highest rent']) {
      await page.keyboard.press('Tab');
      await expect(choice(label)).toBeFocused();
    }
    await page.keyboard.press('Enter');
    await expect(result('price_desc')).toBeVisible();
    await expect(trigger('Highest rent')).toBeFocused();
    expect(requests).toHaveLength(beforeSort + 1);
    expect(Object.fromEntries(requests.at(-1)!)).toEqual(Object.fromEntries(nextQuery));

    await trigger('Highest rent').tap();
    await expect(choice('Highest rent')).toHaveAttribute('aria-pressed', 'true');
    await choice('Lowest rent').tap();
    try {
      await expect.poll(() => requests.at(-1)?.get('sort')).toBe('price_asc');
      await trigger('Lowest rent').tap();
      await choice('Largest first').tap();
      await expect(result('area_desc')).toBeVisible();
      const olderResponse = page.waitForResponse(response => new URL(response.url()).searchParams.get('sort') === 'price_asc');
      releaseOlderSort();
      expect(await (await olderResponse).finished()).toBeNull();
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await expect(result('area_desc')).toBeVisible();
      await expect(result('price_asc')).toHaveCount(0);
    } finally {
      releaseOlderSort();
    }
    await trigger('Largest first').tap();
    await expect(choice('Largest first')).toHaveAttribute('aria-pressed', 'true');
    await choice('Newest first').tap();
    await expect(result('newest')).toBeVisible();
    expect(blocked).toEqual([]);
  });
});

test('Q10 detail failures retry locally and late responses cannot replace a different home', async ({ page, context }) => {
  const api = process.env.E2E_API_URL!;
  const allowed = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
  const homes = pagedHomes().slice(0, 2);
  const contact = { id: 'synthetic-advert', name: 'Synthetic owner', advertiser_type: 'private' };
  let mode: 'fail' | 'loaded' | 'missing' | 'hold' = 'fail';
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.protocol === 'data:') return route.continue();
    if (url.hostname !== '127.0.0.1' || !allowed.has(url.port)) return route.abort();
    const headers = { 'Access-Control-Allow-Origin': process.env.E2E_WEB_URL! };
    if (url.origin === api && url.pathname === '/v1/listings') return route.fulfill({ json: { items: homes, total: 2, page: 1, page_size: 24, engine: 'sql' }, headers });
    const home = homes.find(item => url.origin === api && url.pathname === `/v1/listings/${item.id}`);
    if (home) {
      if (home.id === homes[0].id) {
        if (mode === 'fail') return route.fulfill({ status: 503, json: { detail: 'hidden upstream cause' }, headers });
        if (mode === 'missing') return route.fulfill({ status: 404, json: { detail: 'missing' }, headers });
        if (mode === 'hold') await held;
      }
      return route.fulfill({ json: { ...home, description: `${home.title} hydrated`, contact_adverts: [contact], history: [{ at: '2026-01-01T12:00:00Z', rent_pln: 4000, status: 'active' }] }, headers });
    }
    return route.continue();
  });
  await page.goto('/');
  const open = (index: number) => page.getByRole('button', { name: `View ${homes[index].title}`, exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'A closer look' });
  await open(0);
  await expect(dialog.getByRole('alert')).toContainText('Could not load current details');
  await expect(dialog.getByText(homes[0].title, { exact: true })).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Message Synthetic owner' })).toHaveCount(0);
  await expect(dialog.getByText('Observed rent history')).toHaveCount(0);
  mode = 'loaded';
  await dialog.getByRole('button', { name: 'Retry details' }).click();
  await expect(dialog.getByRole('button', { name: 'Message Synthetic owner' })).toBeVisible();
  await dialog.getByRole('button', { name: 'Close dialog' }).click();
  mode = 'missing'; await open(0);
  await expect(dialog.getByRole('alert')).toContainText('no longer available');
  await expect(dialog.getByRole('button', { name: 'Message Synthetic owner' })).toHaveCount(0);
  await dialog.getByRole('button', { name: 'Close dialog' }).click();
  mode = 'hold'; await open(0);
  await expect(dialog.getByRole('status')).toContainText('Loading current details');
  await dialog.getByRole('button', { name: 'Close dialog' }).click();
  await open(1);
  await expect(dialog.getByText(`${homes[1].title} hydrated`, { exact: true })).toBeVisible();
  const oldResponse = page.waitForResponse(response => response.url() === `${api}/v1/listings/${homes[0].id}`);
  release(); await oldResponse;
  await expect(dialog.getByText(homes[1].title, { exact: true })).toBeVisible();
  await expect(dialog.getByText(homes[0].title, { exact: true })).toHaveCount(0);
});
