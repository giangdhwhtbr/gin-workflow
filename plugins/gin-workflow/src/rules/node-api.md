---
id: node-api
tier: framework
applies_to: ["**/*.ts", "**/*.js", "**/*.mts", "**/*.mjs", "**/*.cts", "**/*.cjs"]
detect: {package_json_deps: [express, fastify, koa, hono, "@nestjs/core"]}
---
- [critical] `validate-input`: Validate every request body, query, and params with a schema before use.
- [critical] `async-errors`: Route every async error to the framework error handler; leave no promise unhandled.
- [high] `thin-handlers`: Handlers parse, call a service, and map the result; services never see `req` or `res`.
- [high] `config-once`: Read and validate environment config once at startup into a typed object.
- `error-shape`: Return one error body shape with a stable code.
- `graceful-shutdown`: Close servers, pools, and queues on SIGTERM.

## Why
- `validate-input`: Unvalidated input is the main source of injection and crash bugs.
- `async-errors`: An unhandled rejection can crash the process or hang the request.
