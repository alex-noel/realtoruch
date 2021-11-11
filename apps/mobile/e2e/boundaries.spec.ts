import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';

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
