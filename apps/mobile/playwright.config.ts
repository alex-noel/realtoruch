import { defineConfig, devices } from '@playwright/test';

const profile = process.env.E2E_QUALITY_PROFILE || 'functional';
if (!['functional', 'visual', 'cross-browser'].includes(profile)) throw new Error('Unknown E2E_QUALITY_PROFILE');
if (profile === 'visual' && process.platform !== 'darwin') throw new Error('Reviewed visual baselines currently require macOS. Capture and review a separate platform baseline before enabling this profile elsewhere.');

export default defineConfig({
  grep: profile === 'visual' ? /@visual/ : profile === 'cross-browser' ? /@cross-browser/ : undefined,
  grepInvert: profile === 'functional' ? /@visual/ : undefined,
  testDir: './e2e',
  testMatch: '**/*.spec.ts',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  workers: 1,
  retries: 0,
  forbidOnly: true,
  outputDir: process.env.E2E_OUTPUT_DIR,
  reporter: [['list'], ['./e2e/reporter.ts']],
  use: { actionTimeout: 8_000, baseURL: process.env.E2E_WEB_URL, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: profile === 'cross-browser' ? [
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
  ] : [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 } } },
  ],
});
