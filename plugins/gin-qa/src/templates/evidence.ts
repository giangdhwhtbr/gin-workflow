// Evidence fixture for gin-qa e2e specs. This file belongs to the repository: change it freely,
// but keep result.json's shape, which `gin-qa e2e check --run` and `gin-qa e2e export` read.
//
// A spec starts with `// TC: <TC-ID>@<hash8>` (written by `gin-qa e2e pin`) and wraps each test
// case step in `ev.step`. Under `gin-qa e2e run` (GIN_QA_RUN_DIR set) every step leaves a
// screenshot, and the test leaves <run>/<tc-id>/result.json. Without it the fixture records nothing.
import { test as base, expect } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';

type StepResult = {
  n: number;
  title: string;
  status: 'passed' | 'failed';
  screenshot: string | null;
  error: string | null;
};

export type Evidence = {
  step: (title: string, body: () => Promise<void>) => Promise<void>;
};

const HEADER = /^\/\/ TC: (TC-[A-Z][A-Z0-9-]*-\d{3,})@([0-9a-f]{8})$/;

function firstLine(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error);
  return text.split('\n')[0].slice(0, 300);
}

export const test = base.extend<{ ev: Evidence }>({
  ev: async ({ page }, use, testInfo) => {
    const header = HEADER.exec(fs.readFileSync(testInfo.file, 'utf8').split('\n')[0]);
    const runDir = process.env.GIN_QA_RUN_DIR;
    const tcDir = runDir && header ? path.join(runDir, header[1].toLowerCase()) : null;
    if (tcDir) fs.mkdirSync(tcDir, { recursive: true });
    const steps: StepResult[] = [];
    const started = new Date().toISOString();

    await use({
      step: (title, body) =>
        base.step(title, async () => {
          const n = steps.length + 1;
          let failure: unknown = null;
          try {
            await body();
          } catch (error) {
            failure = error;
          }
          let screenshot: string | null = null;
          if (tcDir) {
            const name = `${String(n).padStart(2, '0')}.png`;
            try {
              await page.screenshot({ path: path.join(tcDir, name), fullPage: true });
              screenshot = name;
            } catch {
              screenshot = null;
            }
          }
          steps.push({
            n,
            title,
            status: failure ? 'failed' : 'passed',
            screenshot,
            error: failure ? firstLine(failure) : null,
          });
          if (failure) throw failure;
        }),
    });

    if (!tcDir || !header) return;
    const stepFailed = steps.some((step) => step.status === 'failed');
    const failed = stepFailed || testInfo.status !== testInfo.expectedStatus;
    const outside = failed && !stepFailed ? firstLine(testInfo.error?.message ?? testInfo.status) : null;
    const result = {
      tc: header[1],
      tc_hash8: header[2],
      status: failed ? 'failed' : 'passed',
      started,
      finished: new Date().toISOString(),
      error: outside,
      steps,
    };
    fs.writeFileSync(path.join(tcDir, 'result.json'), JSON.stringify(result, null, 2) + '\n');
  },
});

export { expect };
