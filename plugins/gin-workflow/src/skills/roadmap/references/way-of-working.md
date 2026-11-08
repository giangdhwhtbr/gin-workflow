# Way of working: default pattern for a multi-role team

Read on `/roadmap`. Tailor each block to the team roles and the tech-doc set, present it with trade-offs, and write the confirmed text under `## Way of working` in the roadmap file. Keep a confirmed section on re-runs unless the PM asks for a change.

## Foundation
First milestone, 2 weeks by default, shorter when the tech-doc set shows the pieces exist: CI/CD, environments, auth, feature flags, app shell, contract convention (OpenAPI first), and onboarding. In onboarding each member sets up the environment and learns the tools and the gin skills the team installed on one small capability. Feature epics depend on the foundation epics they need.

## Spec cadence
The BA confirms the specs of milestone N+1 during milestone N. `Spec ready by:` of a milestone is its kickoff date, else its start date. At kickoff, `gin milestone show <id>` warns `spec_not_ready` for an open epic without a confirmed spec. Name those epics and the BA work due before kickoff.

## Build
Contract first: the OpenAPI contract of a capability is agreed before BE and FE start, then both build in parallel. FE runs against mocks generated from the contract (MSW handlers from orval, for example). For a migration the first FE target is a 1-1 copy of the legacy UI. Sequence capabilities by spec readiness and by real API or data needs only. Keep `Depends on:` minimal.

## Integration
One feature flag per capability, controlled by the backend. `GET /api/feature-flags` lists them, and the backend also guards the endpoints of an off feature. A gate handler per capability passes requests to the real API when its flag is on and falls through to the mock when off. The FE renders a `MOCK` watermark on a capability served by mocks (from the flags state, or an `X-Mock` header the mock handlers add) and removes it once the capability calls the real backend. Capabilities that share data (a cart referencing catalog ids) share a flag or integrate together. CI runs a contract-diff check, and production builds carry no mocks. The integration point of a milestone is working day floor(0.75 * N), where N counts the working days (Monday to Friday) from `start` to `end` inclusive and `start` is working day 1; when that number is 0, use `start`. The flags listed under `Flags on:` are turned on that day.

## Quality
QA writes the E2E suite against the mocked UI during the build and reruns the same suite against the real API after the flip. QA closes each epic inside its own milestone, and the days after the integration point are hardening days. `Exit criteria:` of a milestone: E2E green against the real API for every flag turned on, watermark gone, no open bug bead on the integrated epics.

## Load
Team mode: group the roles of `team.members` (`.agent-workflow/config.yaml`) by the first token before `_` (`be_dev` and `be_lead` are BE; `fe_*` is FE; `qa` and `qe` are QA; `ba`, `sa`, `devops`, `pm` stand alone). Print the grouping for the PM to correct. Bound each milestone by the member count of the scarcest group that the adopted epics need (an epic needs the groups its `Scope:` names), times the working days. Without team mode, the bound is the lane count (`AI capacity:` or `--lanes`) times the working days. Never ask the team composition.

## Milestone block
```
Spec ready by: <kickoff, else start>
Integration point: <date>
- Integrates: <adopted epic ids>
- Flags on: <one flag per capability, or one shared flag for capabilities that share data>
- E2E scope: <the user flows those flags expose>
- Exit criteria: <see Quality>
```
