import { expect, test, type Page } from '@playwright/test';
import { readFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';

async function verifiedOwner(page: Page, email: string) {
  await page.goto('/', { waitUntil: 'commit' });
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByRole('button', { name: 'New here? Create a free account' }).click();
  await page.getByPlaceholder('you@example.com').fill(email);
  await page.getByPlaceholder('At least 12 characters').fill('synthetic-q34-password-123');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  let token = '';
  await expect.poll(async () => {
    for (const name of (await readdir(process.env.E2E_MAIL_DIR!).catch(() => [])).filter(file => file.endsWith('.eml'))) {
      const text = (await readFile(join(process.env.E2E_MAIL_DIR!, name), 'utf8')).replace(/=\r?\n/g, '').replace(/=3D/gi, '=');
      if (text.includes(email)) token = text.match(/#verify_account=([^\s]+)/)?.[1] ?? '';
    }
    return !!token;
  }, { timeout: 20_000 }).toBe(true);
  await page.evaluate(value => { window.location.hash = `verify_account=${value}`; }, token);
  const verification = page.waitForResponse(r => r.url().endsWith('/v1/auth/verify-email'));
  await page.reload({ waitUntil: 'commit' }); expect((await verification).status()).toBe(200);
  await page.getByRole('button', { name: 'Account', exact: true }).click();
  await page.getByRole('button', { name: 'My rental adverts' }).click();
  await page.getByLabel('PUBLIC NAME').fill('Photo owner');
  await page.getByRole('button', { name: 'Save profile' }).click();
}
async function png(page: Page, name: string, color: string) {
  const encoded = await page.evaluate(fill => { const canvas = document.createElement('canvas'); canvas.width = 24; canvas.height = 16; const ctx = canvas.getContext('2d')!; ctx.fillStyle = fill; ctx.fillRect(0, 0, 24, 16); return canvas.toDataURL('image/png').split(',')[1]; }, color);
  return { name, mimeType: 'image/png', buffer: Buffer.from(encoded, 'base64') };
}
test('owned photos upload, reorder, save and publish in selected order', async ({ page, context }, info) => {
  test.setTimeout(90_000);
  if (info.project.name === 'mobile') await page.setViewportSize({ width: 320, height: 800 });
  const ports = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
  await context.route('**/*', route => { const url = new URL(route.request().url()); return ['data:', 'blob:'].includes(url.protocol) || (url.hostname === '127.0.0.1' && ports.has(url.port)) ? route.continue() : route.abort(); });
  await page.addInitScript(() => { const create = URL.createObjectURL.bind(URL), revoke = URL.revokeObjectURL.bind(URL), active = new Set<string>(); Object.assign(window, { __photoUrls: active }); URL.createObjectURL = blob => { const url = create(blob); active.add(url); return url; }; URL.revokeObjectURL = url => { active.delete(url); revoke(url); }; });
  await verifiedOwner(page, `q34-${info.project.name}@example.test`);
  await page.getByRole('button', { name: 'Create rental advert' }).click();
  await page.getByLabel('TITLE', { exact: true }).fill('Photo order rental');
  await page.getByLabel('DESCRIPTION', { exact: true }).fill('A synthetic rental for checking owned photo uploads.');
  await page.getByLabel('STREET AND BUILDING').fill('Testowa 34');
  await page.getByLabel('Location latitude').fill('50.06');
  await page.getByLabel('Location longitude').fill('19.94');
  const files = [await png(page, 'red.png', '#ef3333'), await png(page, 'blue.png', '#3333ef')];
  const uploads: Promise<{ body: Buffer | null; id: string }>[] = [];
  let release!: () => void; const hold = new Promise<void>(resolve => { release = resolve; });
  let first = true, failNext = false; const failedKeys: string[] = [];
  await page.route(`${process.env.E2E_API_URL}/v1/me/media`, async route => {
    if (route.request().method() !== 'POST') return route.continue();
    if (first) { first = false; await hold; }
    if (failNext) { failNext = false; failedKeys.push(route.request().headers()['idempotency-key']); return route.fulfill({ status: 503, json: { detail: 'offline' } }); }
    if (failedKeys.length === 1) failedKeys.push(route.request().headers()['idempotency-key']);
    return route.continue();
  });
  page.on('response', response => { if (response.status() === 201 && response.url().endsWith('/v1/me/media') && response.request().method() === 'POST') uploads.push(response.json().then(body => ({ body: response.request().postDataBuffer(), id: body.id }))); });
  const chooser = page.waitForEvent('filechooser');
  const choose = page.getByRole('button', { name: 'Choose photos', exact: true }); await choose.focus(); await page.keyboard.press('Enter');
  await (await chooser).setFiles(files);
  await expect(page.getByRole('button', { name: 'Save draft', exact: true })).toBeDisabled();
  await expect(page.getByText('Finish or remove unfinished uploads before saving or publishing.')).toBeVisible();
  release();
  await expect(page.getByRole('button', { name: 'Move photo 2, blue.png earlier' })).toBeEnabled();
  await expect(page.getByText(/Ready/)).toHaveCount(2);
  await page.getByLabel('Description for photo 2, blue.png').fill('Blue room');
  const move = page.getByRole('button', { name: 'Move photo 2, blue.png earlier' }); await move.focus(); await page.keyboard.press('Enter');
  await expect(page.getByText('Ready · Cover photo')).toBeVisible();
  const results = await Promise.all(uploads);
  const blue = results.find(item => item.body?.equals(files[1].buffer))?.id;
  const red = results.find(item => item.body?.equals(files[0].buffer))?.id;
  expect(blue).toBeTruthy(); expect(red).toBeTruthy();
  const saved = page.waitForResponse(r => r.url().endsWith('/v1/me/adverts') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  expect((await (await saved).json()).advert.media_ids).toEqual([blue, red]);
  await expect(page.getByText('Photo order rental', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Review and publish' }).click();
  await expect(page.getByText('Uploaded photo 1 · Cover')).toBeVisible();
  await expect(page.getByRole('img', { name: 'Blue room' })).toBeVisible();
  await page.screenshot({ path: info.outputPath('synthetic-photo-preview.png'), fullPage: true });
  await page.getByRole('button', { name: 'Publish advert' }).click();
  await expect(page.getByText(/^PUBLISHED ·/)).toBeVisible();
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Move photo 1 earlier' })).toBeDisabled();
  await expect(page.getByText(/Ready/)).toHaveCount(2);
  await page.getByLabel('TITLE', { exact: true }).fill('Updated photo rental');
  failNext = true;
  const green = await png(page, 'green.png', '#22aa33');
  const nextChooser = page.waitForEvent('filechooser'); await page.getByRole('button', { name: 'Choose photos' }).click(); await (await nextChooser).setFiles([green]);
  await expect(page.getByText('Upload could not finish. Try again.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Review published changes' })).toBeDisabled();
  await expect(page.getByLabel('TITLE', { exact: true })).toHaveValue('Updated photo rental');
  await page.getByRole('button', { name: 'Retry photo 3, green.png' }).click();
  await expect(page.getByText(/Ready/)).toHaveCount(3);
  expect(failedKeys).toHaveLength(2); expect(failedKeys[0]).toBe(failedKeys[1]);
  let updates = 0, cancels = 0;
  await page.route(`${process.env.E2E_API_URL}/v1/me/media/by-key/*`, route => { if (route.request().method() === 'DELETE') cancels++; return route.continue(); });
  await page.route(`${process.env.E2E_API_URL}/v1/me/adverts/*`, route => {
    if (route.request().method() === 'PUT' && ++updates === 1) return route.fulfill({ status: 409, json: { detail: 'This advert changed on another device. Reload before editing.' } });
    return route.continue();
  });
  await page.getByRole('button', { name: 'Review published changes' }).click();
  await page.getByRole('button', { name: 'Apply published changes' }).click();
  await page.getByRole('button', { name: 'Use mine for title' }).click();
  await expect(page.getByText('Your uploaded photos, in order')).toBeVisible();
  await expect(page.getByText('Latest uploaded photos, in order')).toBeVisible();
  await page.getByRole('button', { name: 'Use mine for media_ids' }).click();
  expect(cancels).toBe(0);
  await page.getByRole('button', { name: 'Save selected values' }).click();
  await expect(page.getByText('Uploaded photo 3')).toBeVisible();
  const update = page.waitForResponse(r => r.url().includes('/v1/me/adverts/') && r.request().method() === 'PUT' && r.status() === 200);
  await page.getByRole('button', { name: 'Apply published changes' }).click();
  const updated = await (await update).json();
  const greenId = (await Promise.all(uploads)).find(item => item.body?.equals(green.buffer))?.id;
  expect(updated.advert.media_ids).toEqual([blue, red, greenId]);
  await expect(page.getByText('Updated photo rental', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(page.getByText(/Ready/)).toHaveCount(3);
  await page.getByRole('button', { name: 'Back to adverts' }).click();
  await expect.poll(() => page.evaluate(() => (window as unknown as { __photoUrls: Set<string> }).__photoUrls.size)).toBe(0);
});
