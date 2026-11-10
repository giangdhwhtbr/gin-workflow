# Capability epics: tracks, areas, contract, integration

Read on `/roadmap` when presenting epics (step 4).

## One epic per capability
An epic delivers one capability. In a workspace it holds one track per repository; with team areas and no workspace, one track per area. A track never spans two repositories or two areas.

## Tracks line
Add `Tracks:` to the epic entry when the project has a workspace or team areas, one item per track: `Tracks: services/catalog-api: browse endpoints (Area: backend); apps/web-shop: catalog pages (Area: frontend)`. Each track names the repository or area and what it builds, then the `Area:` it carries. Omit the line without a workspace and without areas. `/plan` starts its tracks from this line and may split a track further.

## Contract
The confirmed spec of the epic is the API contract of the capability. `requirement_confirmed` freezes it. The service and app tracks of the epic build against that spec, and the app track generates its mocks from it. No separate contract epic is created.

## Integration epic
With `--milestone`, propose one epic titled `<capability> integration` for each capability listed in `Integrates:` of the milestone block. It depends on the capability's build epics, its scope is "turn the flag on and run the E2E suite against the real API", and it belongs to the milestone of that integration point. It carries `Tracks:` only when the flag flip or the E2E run belongs to a specific repository.
