---
id: nextjs
tier: framework
requires: [react]
applies_to: ["app/**", "src/app/**", "pages/**", "src/pages/**", "middleware.ts", "src/middleware.ts"]
detect: {package_json_deps: [next]}
tool_checks:
  - id: next-lint
    check: {eslint_rule: "@next/next/no-html-link-for-pages"}
    suggest: |
      // eslint.config.js
      import next from "@next/eslint-plugin-next";
      export default [{ plugins: { "@next/next": next }, rules: next.configs.recommended.rules }];
---
- [critical] `server-secrets`: Read secrets only in server code; never import server-only modules or private env into Client Components.
- [high] `server-default`: Keep components on the server; add `"use client"` only at the smallest interactive leaf.
- [high] `fetch-on-server`: Fetch data in Server Components or route handlers, not in client effects.
- [high] `cache-explicit`: State the caching and revalidation intent of every fetch and route.
- `mutations-revalidate`: Mutate through Server Actions or route handlers that revalidate the affected paths.
- `route-colocation`: Keep route-only components inside the route segment; move them to `components/` when reused.

## Why
- `server-secrets`: Anything a Client Component imports ships to the browser.
- `cache-explicit`: Implicit caching defaults change between Next.js versions.
