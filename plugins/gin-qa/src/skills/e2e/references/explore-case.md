# Explore one case

Build the Playwright spec for one `Type: e2e` test case from what the running application shows. Input: the case's `plan` row (TC-ID, title, steps, expected, `spec` path) and the guidelines file. Write only the case's spec file. Never commit, and never edit the fixture, the guidelines, the test cases, or another spec. Commands are `gin-qa e2e <command>`.

## Spec shape

- First line `// TC: <TC-ID>@00000000`, then `import { test, expect } from '../evidence';` and one `test('<TC-ID>: <title>', async ({ page, ev }) => { … })`.
- One `await ev.step('<n>. <step text>', async () => { … })` per case step, in order. `Preconditions` go before the first step; `Expected` items are assertions in the step that produces them.
- Locators, in order of preference: `getByRole` with the accessible name, `getByLabel`/`getByPlaceholder`, `getByText`, `getByTestId`. The guidelines win over this list.
- Assert with auto-waiting `expect(...)`; never `waitForTimeout` to wait for a state.

## Loop

1. Write the spec with step 1 only. `run <TC-ID> --format json` prints the run folder (`run`); the case's evidence is in `<run>/<tc-id>/`. Until step 4 the run also reports the unpinned header as a finding; ignore that one.
2. Read `result.json` there. For the last step (or the failing one) read its `NN.aria.yml` (the page's ARIA tree after the step) and `url`. If step 1 cannot reach the page, stop with `blocked`: name the `baseURL` and ask how to start the application.
3. Add the next step. Take its locator from the snapshot (role and accessible name as shown there) and confirm it in the UI source. Add the assertions for the `Expected` items it produces. Run again and go back to 2 until every case step is in the spec.
4. `pin <TC-ID>` writes the real hash; never type a hash by hand. Run once more.
5. Review the evidence: read every `NN.png` and confirm it shows what its step title says. A passing test that shows the wrong screen or skips the step's action is a spec defect.
6. Spec defects (locator, timing, navigation, wrong screen): fix and rerun, at most 3 rounds after the spec is complete.

## Outcome

Return one line: `<TC-ID> done|app_defect|blocked <run folder> <reason>`.

- `done`: the last run passed and the evidence review found nothing.
- `app_defect`: the application does not do what `Expected` says. Do not bend the spec to pass; name the step, its error, and its screenshot and snapshot.
- `blocked`: anything else that stops the case (no access, 3 rounds used up, a step the UI cannot perform), with the reason.

## Fixture without snapshots

A repository whose `evidence.ts` has no `ariaSnapshot` predates step snapshots. Its owner merges this into `ev.step`, after the screenshot, and adds `snapshot: string | null; url: string;` to `StepResult` and `snapshot, url: page.url(),` to the pushed step:

```ts
let snapshot: string | null = null;
if (tcDir) {
  try {
    const aria = await page.locator('body').ariaSnapshot({ timeout: 5000 });
    fs.writeFileSync(path.join(tcDir, `${String(n).padStart(2, '0')}.aria.yml`), aria + '\n');
    snapshot = `${String(n).padStart(2, '0')}.aria.yml`;
  } catch {
    snapshot = null;
  }
}
```

`ariaSnapshot` needs `@playwright/test` 1.49 or later. If every step's `snapshot` is null, ask the user to upgrade it.
