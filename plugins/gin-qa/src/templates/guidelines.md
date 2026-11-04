# Test case guidelines

Rules for writing test cases in this repository. `/gin-qa:cases` reads this file first; its rules override the skill's defaults. Edit freely.

- Language: not set yet (the language test cases are written in).
- One user action per step.
- Type is the file suffix: `.e2e.md` for cases a browser test can run, `.manual.md` otherwise; add the types this team uses.
- `Priority: high | medium | low`.
- Extra fields this team uses (kept and exported as-is): none yet.

## E2E specs (`/gin-qa:e2e`)

- Playwright: `@playwright/test` 1.49 or later (the evidence fixture records ARIA snapshots).
- Locators: prefer `getByRole` with the accessible name; use `getByTestId` only when no stable name exists.
- Sign-in: none yet (describe how specs sign in, e.g. a `storageState` file or a sign-in step).
- Test data: none yet (shared users and records specs may rely on; data one case needs goes in its `Test data` section).
