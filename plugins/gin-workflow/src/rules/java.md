---
id: java
tier: language
applies_to: ["**/*.java"]
detect: {files_exist: [pom.xml, build.gradle, build.gradle.kts]}
---
- [critical] `parameterized-sql`: Bind parameters with PreparedStatement or query framework methods; never concatenate input into SQL, JPQL, or HQL strings.
- [high] `close-resources`: Manage every AutoCloseable resource with a try-with-resources statement; never rely on finalizers or unclosed streams.
- [high] `equals-hashcode`: Override hashCode whenever overriding equals, using the same fields for equality and hashing.
- [high] `money-bigdecimal`: Represent monetary amounts and financial calculations with BigDecimal using an explicit scale and RoundingMode; never use float or double.
- `empty-not-null`: Return empty collections or arrays from methods returning collections, never null.

## Why
- `parameterized-sql`: String concatenation in queries allows SQL injection and prevents query plan caching.
