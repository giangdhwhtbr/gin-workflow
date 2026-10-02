---
id: fastapi
tier: framework
requires: [python]
applies_to: ["**/*.py"]
detect: {pyproject_deps: [fastapi]}
---
- [critical] `models-at-edge`: Declare request and response models; never return ORM objects or raw dicts from routes.
- [high] `depends-for-resources`: Get sessions, settings, and the current user through `Depends`, not module globals.
- [high] `thin-routes`: Keep route functions thin; business logic lives in services that do not import FastAPI.
- [high] `no-blocking-async`: Never block inside `async def`; use `def` routes or async clients.
- `stable-errors`: Raise `HTTPException` or a mapped domain error with a stable code; never leak stack traces.
- `router-per-domain`: Use one `APIRouter` per domain module, included by the app factory.

## Why
- `models-at-edge`: Response models are the API contract and stop accidental field leaks.
