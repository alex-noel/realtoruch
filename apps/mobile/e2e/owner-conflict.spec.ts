import { test, expect, BrowserContext, Page } from '@playwright/test';
async function blockOutside(context: BrowserContext) {
  const ports = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.protocol === 'data:' || (url.hostname === '127.0.0.1' && ports.has(url.port))) await route.continue();
    else await route.abort('blockedbyclient');
  });
}
async function openDesk(page: Page) {
  await page.getByRole('button', { name: 'Account', exact: true }).click();
  await page.getByRole('button', { name: 'My rental adverts' }).click();
}
test('two sessions reconcile explicitly and handle a second conflict', async ({ page, context, browser }, info) => {
  await blockOutside(context);
  const email = `q30-${info.project.name}@example.test`, password = 'synthetic-test-password-123';
  await page.goto('/', { waitUntil: 'commit' });
  await page.locator('button[aria-label="Sign in"]').click();
  await page.getByRole('button', { name: 'New here? Create a free account' }).click();
  await page.getByPlaceholder('you@example.com').fill(email);
  await page.getByPlaceholder('At least 12 characters').fill(password);
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await openDesk(page);
  await page.getByLabel('PUBLIC NAME').fill('Conflict owner');
  await page.getByRole('button', { name: 'Save profile' }).click();
  await page.getByRole('button', { name: 'Create rental advert' }).click();
  await page.getByLabel('TITLE', { exact: true }).fill('Original rental');
  await page.getByLabel('DESCRIPTION', { exact: true }).fill('Original synthetic description for this rental.');
  await page.getByLabel('STREET AND BUILDING').fill('Testowa 30');
  await page.getByLabel('Location latitude').fill('50.06');
  await page.getByLabel('Location longitude').fill('19.94');
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await page.getByLabel('TITLE', { exact: true }).fill('My local title');
  const secondContext = await browser.newContext({ viewport: info.project.use.viewport });
  await blockOutside(secondContext);
  const other = await secondContext.newPage();
  try {
    await other.goto('/', { waitUntil: 'commit' });
    await other.locator('button[aria-label="Sign in"]').click();
    await other.getByPlaceholder('you@example.com').fill(email);
    await other.getByPlaceholder('At least 12 characters').fill(password);
    await other.getByRole('button', { name: 'Sign in', exact: true }).last().click();
    await openDesk(other);
    await other.getByRole('button', { name: 'Edit', exact: true }).click();
    await other.getByLabel('DESCRIPTION', { exact: true }).fill('A newer synthetic description from the second session.');
    await other.getByLabel('PHOTO LINKS (HTTPS; ONE PER LINE)').fill('https://example.test/photo.jpg');
    await other.getByRole('button', { name: 'Save draft', exact: true }).click();
    await expect(other.getByRole('button', { name: 'Edit', exact: true })).toBeVisible();
    let failLatest = true, injectHidden = true;
    await page.route(`${process.env.E2E_API_URL}/v1/me/adverts`, async route => {
      if (route.request().method() === 'GET' && failLatest) { failLatest = false; return route.fulfill({ status: 503, json: { detail: 'offline' } }); }
      if (route.request().method() === 'GET' && injectHidden) {
        injectHidden = false; const response = await route.fetch(); const data = await response.json();
        data.items[0].hidden = true; data.items[0].state = 'withdrawn';
        return route.fulfill({ response, json: data });
      }
      return route.continue();
    });
    await page.getByRole('button', { name: 'Save draft', exact: true }).click();
    await expect(page.getByText(/latest advert is unavailable/i)).toBeVisible();
    await expect(page.getByText(/This advert changed on another device/).first()).toBeVisible();
    await page.getByRole('button', { name: 'Retry latest version' }).click();
    await expect(page.getByText(/Latest status: withdrawn · hidden after review/)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Save selected values' })).toBeDisabled();
    await page.getByRole('button', { name: 'Use mine for title' }).click();
    await page.getByRole('button', { name: 'Use latest for description' }).click();
    await page.getByRole('button', { name: 'Use latest for images' }).click();
    await other.getByRole('button', { name: 'Edit', exact: true }).click();
    await expect(other.getByLabel('TITLE', { exact: true })).toHaveValue('Original rental');
    await other.getByLabel('CITY', { exact: true }).fill('Warszawa');
    await other.getByRole('button', { name: 'Save draft', exact: true }).click();
    await expect(other.getByRole('button', { name: 'Edit', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Save selected values' }).click();
    await expect(page.getByRole('button', { name: 'Save selected values' })).toBeDisabled();
    await page.getByRole('button', { name: 'Use mine for title' }).click();
    await page.getByRole('button', { name: 'Use latest for city' }).click();
    const response = page.waitForResponse(r => r.url().includes('/v1/me/adverts/') && r.request().method() === 'PUT');
    await page.getByRole('button', { name: 'Save selected values' }).click();
    const saved = await response; expect(saved.status()).toBe(200);
    expect((await saved.json()).advert).toMatchObject({ title: 'My local title', city: 'Warszawa', description: 'A newer synthetic description from the second session.', images: ['https://example.test/photo.jpg'] });
    await expect(page.getByText('My local title', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit', exact: true }).click();
    await page.getByLabel('TITLE', { exact: true }).fill('Local changes to discard');
    await other.getByRole('button', { name: 'Close dialog' }).click();
    await openDesk(other);
    await other.getByRole('button', { name: 'Edit', exact: true }).click();
    await other.getByLabel('DESCRIPTION', { exact: true }).fill('The latest saved description for reload verification.');
    await other.getByRole('button', { name: 'Save draft', exact: true }).click();
    await expect(other.getByRole('button', { name: 'Edit', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Save draft', exact: true }).click();
    await expect(page.getByText(/Latest status: draft/)).toBeVisible();
    await page.getByRole('button', { name: 'Reload latest version' }).click();
    await page.getByRole('button', { name: 'Keep my edits' }).click();
    await page.getByRole('button', { name: 'Reload latest version' }).click();
    await page.getByRole('button', { name: 'Discard edits and reload' }).click();
    await expect(page.getByLabel('TITLE', { exact: true })).toHaveValue('My local title');
    await expect(page.getByLabel('DESCRIPTION', { exact: true })).toHaveValue('The latest saved description for reload verification.');
    await page.getByRole('button', { name: 'Back to adverts' }).click();
    await expect(page.getByText('Discard unsaved changes?')).toHaveCount(0);
  } finally { await secondContext.close(); }
});
