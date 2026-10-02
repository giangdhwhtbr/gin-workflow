---
id: react
tier: framework
requires: [typescript]
applies_to: ["**/*.tsx", "**/*.jsx"]
detect: {package_json_deps: [react]}
conflict_keywords:
  - {pack_says: "named export", project_conflict: "default export"}
tool_checks:
  - id: react-hooks-lint
    check: {eslint_rule: "react-hooks/rules-of-hooks"}
    suggest: |
      // eslint.config.js
      import reactHooks from "eslint-plugin-react-hooks";
      export default [reactHooks.configs["recommended-latest"]];
---
- [critical] `state-location`: Keep server state in the data-fetching layer (query cache or loader), not in component state.
- [high] `derive-not-sync`: Derive values during render instead of copying them into state with an effect.
- [high] `effects-external-only`: Use effects only to sync with external systems; handle user actions in event handlers.
- [high] `stable-keys`: Key list items by stable domain ids, never by array index in lists that reorder.
- `one-component-per-file`: Export one component per file; split a component that renders unrelated concerns.
- `named-exports`: Use named exports for components.
- `semantic-first`: Use semantic elements (`button`, `label`, headings) before ARIA attributes.

## Why
- `state-location`: Server state copied into components goes stale and duplicates caching logic.
- `derive-not-sync`: Synced state renders twice and drifts from its source.
