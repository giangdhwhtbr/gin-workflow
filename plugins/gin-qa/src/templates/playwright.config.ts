// Playwright config written by `gin-qa e2e init`. It belongs to this repository: edit it freely.
// E2E_BASE_URL overrides baseURL. Under `gin-qa e2e run` (GIN_QA_RUN_DIR set) the JUnit report goes
// to the run folder, next to the evidence.
import { defineConfig, devices } from '@playwright/test';
import * as path from 'node:path';

const runDir = process.env.GIN_QA_RUN_DIR;

export default defineConfig({
  testDir: '__E2E_DIR__',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [
    ['list'],
    ['junit', { outputFile: runDir ? path.join(runDir, 'junit.xml') : 'test-results/junit.xml' }],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? '__BASE_URL__',
    trace: 'on-first-retry',
    testIdAttribute: 'data-testid',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  // Uncomment to let Playwright start the application before the tests and stop it after them.
  // webServer: {
  //   command: 'npm run start',
  //   url: '__BASE_URL__',
  //   reuseExistingServer: !process.env.CI,
  // },
});
