import { expect, test } from '@playwright/test';
const auth = process.env.E2E_AUTH_URL!;

test('Q25 account sections recover independently and device and sign-out failures stay retryable', async ({ page, context }, info) => {
  const ports = new Set((process.env.E2E_ALLOWED_PORTS || '').split(','));
  await context.route('**/*', route => { const url = new URL(route.request().url()); return url.protocol === 'data:' || (url.hostname === '127.0.0.1' && ports.has(url.port)) ? route.continue() : route.abort(); });
  await page.setViewportSize({ width: 320, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByRole('button', { name: 'New here? Create a free account', exact: true }).click();
  const email = `q25-${info.project.name}@example.test`;
  await page.getByLabel('EMAIL', { exact: true }).fill(email);
  await page.getByLabel('PASSWORD', { exact: true }).fill('synthetic-q25-password-123');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Account', exact: true })).toBeVisible();
  let devicesFail = true, identityFail = false, verified = false, revokeFail = true;
  const json = { 'Access-Control-Allow-Origin': process.env.E2E_WEB_URL!, 'Access-Control-Allow-Credentials': 'true' };
  await page.route(`${auth}/v1/auth/me`, route => route.fulfill({ status: identityFail ? 503 : 200, json: identityFail ? {} : { id: 'synthetic', email, email_verified: verified }, headers: json }));
  await page.route(`${auth}/v1/auth/sessions`, route => route.fulfill({ status: devicesFail ? 503 : 200, json: devicesFail ? {} : { items: [
    { id: 'current', current: true, label: 'Current browser', last_used_at: '2026-01-01T00:00:00Z' },
    { id: 'device-one', current: false, label: 'Other browser one', last_used_at: '2026-01-01T00:00:00Z' },
    { id: 'device-two', current: false, label: 'Other browser two', last_used_at: '2026-01-01T00:00:00Z' },
  ] }, headers: json }));
  await page.getByRole('button', { name: 'Account', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Your account.' });
  await expect(dialog.getByText(email, { exact: true })).toBeVisible();
  await expect(dialog.getByText('Could not load signed-in devices.', { exact: true })).toBeVisible();
  devicesFail = false;
  await dialog.getByRole('button', { name: 'Retry signed-in devices' }).click();
  await expect(dialog.getByText('Current browser · This device', { exact: true })).toBeVisible();
  verified = true;
  await dialog.getByRole('button', { name: 'Refresh verification status' }).click();
  await expect(dialog.getByText('Email verified', { exact: true })).toBeVisible();
  await page.route(`${auth}/v1/auth/sessions/device-one`, route => route.fulfill({ status: revokeFail ? 503 : 200, json: {}, headers: json }));
  await dialog.getByRole('button', { name: 'Sign out this device', exact: true }).first().click();
  await expect(dialog.getByText('Cannot reach the service. Try again.', { exact: true })).toBeVisible();
  await expect(dialog.getByText('Other browser one', { exact: true })).toBeVisible();
  revokeFail = false;
  let release!: () => void; const held = new Promise<void>(resolve => { release = resolve; });
  await page.route(`${auth}/v1/auth/sessions/device-one`, async route => { await held; await route.fallback(); });
  await dialog.getByRole('button', { name: 'Sign out this device', exact: true }).first().click();
  await expect(dialog.getByRole('button', { name: 'Signing out device…', exact: true })).toBeDisabled();
  await expect(dialog.getByRole('button', { name: 'Sign out this device', exact: true })).toBeEnabled();
  release(); await expect(dialog.getByText('Other browser one', { exact: true })).toHaveCount(0);
  await dialog.getByRole('button', { name: 'Close dialog' }).click();
  identityFail = true; await page.getByRole('button', { name: 'Account', exact: true }).click();
  await expect(dialog.getByText('Could not load account details.', { exact: true })).toBeVisible();
  await expect(dialog.getByText('Email verified', { exact: true })).toHaveCount(0);
  await expect(dialog.getByText('Current browser · This device', { exact: true })).toBeVisible();
  identityFail = false; await dialog.getByRole('button', { name: 'Retry account details' }).click();
  await expect(dialog.getByText(email, { exact: true })).toBeVisible();
  let logoutFail = true;
  await page.route(`${auth}/v1/auth/logout`, route => logoutFail ? route.fulfill({ status: 503, json: {}, headers: json }) : route.fallback());
  await dialog.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(dialog.getByRole('button', { name: 'Retry sign out', exact: true })).toBeVisible();
  logoutFail = false; await dialog.getByRole('button', { name: 'Retry sign out', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
});
