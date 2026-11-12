# Capability epics: tracks, areas, contract, integration

Read on `/roadmap` when presenting epics (step 4).

## One epic per capability
An epic delivers one capability. In a workspace it holds at least one track in each repository the capability changes, with QA work as tracks in the `qa` repository of the same epic. With team areas and no workspace, it holds at least one track per area. A track never spans two repositories or two areas.

## Tracks line
Add `Tracks:` to the epic entry when the project has a workspace or team areas, one item per track: `Tracks: services/catalog-api: browse endpoints (Area: backend); apps/web-shop: catalog pages (Area: frontend)`. Each track names the repository or area and what it builds, then the `Area:` it carries. Omit the line without a workspace and without areas. `/plan` starts its tracks from this line and may split a track further.

## Contract
The confirmed spec of the epic is the API contract of the capability. `requirement_confirmed` freezes the business part. When discuss left contract details as technical questions (team mode, a discuss runner without a technical role), `plan_approved` freezes them. The service and app tracks of the epic build against that spec, and the app track generates its mocks from it. No separate contract epic is created.

## Integration epic
With `--milestone`, propose one epic titled `<capability> integration` for each capability listed in `Integrates:` of the milestone block. It depends on the capability's build epics, its scope is "turn the flag on and run the E2E suite against the real API", and it belongs to the milestone of that integration point. It carries `Tracks:` only when the flag flip or the E2E run belongs to a specific repository.

## Kind
Each entry has `Kind: capability|technical|parity`. Propose the kind per epic, and the PM confirms it. Integration epics are `technical`.

Create epics with `--labels roadmap,kind:<kind>`.

When the kind of an existing epic changes, run `gin task update <id> --remove-label kind:<old> --add-label kind:<new>`. Skip this for an `in_progress` or adopted epic, and apply the `[gin roadmap]` comment rule of the sync instead.
