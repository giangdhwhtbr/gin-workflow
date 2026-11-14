---
id: spring
tier: framework
requires: [java]
applies_to: ["**/*.java"]
detect: {build_file_mentions: [org.springframework, spring-boot]}
---
- [critical] `no-secrets-in-properties`: Read credentials, tokens, and secrets from environment variables or a secret store; never commit secrets in application.properties or application.yml.
- [high] `constructor-injection`: Inject dependencies through constructor parameters; avoid field injection with @Autowired.
- [high] `transactional-service`: Place @Transactional on service layer boundary methods; avoid @Transactional on controller methods or internal helper calls.
- [high] `validate-boundary`: Annotate incoming request payload parameters with @Valid or @Validated and apply constraint annotations to boundary models.
- `dto-not-entity`: Accept and return dedicated Data Transfer Objects in controller endpoints; never expose persistent entity models across API boundaries.

## Why
- `no-secrets-in-properties`: Secrets committed to version control leak across environments and build artifacts.
