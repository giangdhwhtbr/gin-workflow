---
id: typescript
tier: language
applies_to: ["**/*.ts", "**/*.tsx", "**/*.mts", "**/*.cts"]
detect: {package_json_deps: [typescript], files_exist: [tsconfig.json]}
tool_checks:
  - id: tsconfig-strict
    check: {tsconfig_option: {strict: true}}
    suggest: |
      // tsconfig.json
      { "compilerOptions": { "strict": true } }
  - id: typescript-eslint
    check: {eslint_rule: "@typescript-eslint/no-floating-promises"}
    suggest: |
      // eslint.config.js
      import tseslint from "typescript-eslint";
      export default tseslint.config(...tseslint.configs.recommendedTypeChecked);
---
- [critical] `no-type-escape`: Do not silence the type checker with `any`, `as` casts, or `!`; narrow with guards or fix the type.
- [high] `model-states`: Model variants as discriminated unions so invalid states cannot be represented.
- [high] `parse-at-boundary`: Parse untrusted data (JSON, env, API responses) with a schema before giving it a type.
- `readonly-inputs`: Mark data a function does not mutate as `readonly`.
- `types-with-owner`: Export a type from the module that owns it; avoid catch-all `types.ts` files.

## Why
- `no-type-escape`: Escapes hide exactly the bugs the type checker exists to catch.
- `parse-at-boundary`: A type annotation on unvalidated data is a false guarantee.
