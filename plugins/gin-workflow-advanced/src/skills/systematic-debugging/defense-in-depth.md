# Defense in depth — validating at every layer

A single validation check is easy to bypass: a different code path skips it, a refactor moves it, a test mock removes the side effect that it was guarding. Validating at every layer the data passes through makes the bug structurally impossible — no individual mistake removes all the safety nets.

## Why one check isn't enough

| Single check | All layers |
|--------------|------------|
| "We fixed the bug" | "We made the bug impossible" |
| Future code paths can bypass it | Bypassing one layer hits the next |
| Refactor can accidentally remove it | Refactor would have to remove all of them |
| Mocks can replace the layer that holds it | Mocks below replacement still catch it |

Each layer catches a different failure mode:

- **Entry validation** rejects obviously bad input.
- **Business logic validation** catches data that's structurally fine but semantically wrong for this operation.
- **Environment guards** prevent dangerous operations in contexts where they don't belong (test fixtures, dev environments).
- **Debug instrumentation** records context for the next time something slips through.

## The four layers

### Layer 1 — Entry-point validation

Reject the obviously invalid at the API boundary, with a clear error message.

```typescript
function createProject(name: string, workingDirectory: string) {
  if (!workingDirectory || workingDirectory.trim() === '') {
    throw new Error('workingDirectory cannot be empty');
  }
  if (!existsSync(workingDirectory)) {
    throw new Error(`workingDirectory does not exist: ${workingDirectory}`);
  }
  if (!statSync(workingDirectory).isDirectory()) {
    throw new Error(`workingDirectory is not a directory: ${workingDirectory}`);
  }
  // ...
}
```

The point is to fail loudly with a message a human can act on. Vague entry-point checks (`if (!input) throw 'invalid'`) defeat the purpose.

### Layer 2 — Business-logic validation

The data passed structural checks. Now does it make sense for *this* operation?

```typescript
function initializeWorkspace(projectDir: string, sessionId: string) {
  if (!projectDir) {
    throw new Error('projectDir required for workspace initialization');
  }
  if (!sessionId) {
    throw new Error('sessionId required for workspace initialization');
  }
  // ...
}
```

Layer 1 checked the value's shape; Layer 2 checks its meaning.

### Layer 3 — Environment guards

Some operations are dangerous in particular contexts. Guard them where they happen.

```typescript
async function gitInit(directory: string) {
  if (process.env.NODE_ENV === 'test') {
    const normalized = normalize(resolve(directory));
    const tmpDir = normalize(resolve(tmpdir()));

    if (!normalized.startsWith(tmpDir)) {
      throw new Error(
        `refusing to git init outside temp dir during tests: ${directory}`
      );
    }
  }
  // ...
}
```

A test that accidentally points `gitInit` at the source tree gets blocked at the operation itself, even if Layers 1 and 2 were skipped or mocked.

### Layer 4 — Debug instrumentation

When all other layers fail (and they will, eventually), the next debugger needs a trail to follow.

```typescript
async function gitInit(directory: string) {
  const stack = new Error().stack;
  logger.debug('about to git init', {
    directory,
    cwd: process.cwd(),
    stack,
  });
  // ...
}
```

Don't keep the high-volume debug logging in production after the bug is closed. But the *call site* of dangerous operations should always have enough context that "what happened here?" is a one-grep question.

## How to apply the pattern

When you've identified a root cause:

1. **Trace the data flow.** Where did the bad value originate? Where did it pass through? Where did it produce the visible failure?
2. **Map the layers.** List every checkpoint the data crossed. Some will be obvious (function entry); some will be implicit (dependency injection, environment access).
3. **Add a check at each layer.** Layer 1 at the public API, Layer 2 at the business operation, Layer 3 at the dangerous primitive, Layer 4 as instrumentation.
4. **Try to bypass each layer.** Write a test that passes invalid data and confirm Layer 1 catches it. Write another that bypasses Layer 1 (e.g., by reaching Layer 2 directly) and confirm Layer 2 catches it. If a layer can be bypassed silently, it's not really a layer.

## Worked example

**Bug:** an empty `projectDir` caused `git init` to run inside the source tree.

**Data flow:**

1. Test fixture provided an empty string.
2. `Project.create(name, '')` accepted it.
3. `WorkspaceManager.createWorkspace('')` accepted it.
4. `gitInit('')` resolved an empty `cwd` to `process.cwd()` — the source tree.

**Layers added after the fix:**

- Layer 1: `Project.create()` validates `workingDirectory` is non-empty, exists, and is a directory.
- Layer 2: `WorkspaceManager` validates `projectDir` is non-empty.
- Layer 3: `gitInit` refuses to run outside `tmpdir()` when `NODE_ENV === 'test'`.
- Layer 4: stack-trace logging immediately before `git init` runs.

**Result:** all 1847 tests passed; the bug is impossible to reproduce. During the rollout, each layer caught at least one bypass attempt:

- A different code path skipped Layer 1.
- A test that mocked `Project.create` skipped Layer 2.
- An edge case on a different platform produced inputs that looked legitimate to the upper layers — Layer 3 caught it.
- Layer 4's logging revealed a structural misuse that wasn't a bug per se but was about to become one.

All four layers turned out to matter. None were redundant.

## When *not* to use defense-in-depth

Don't bolt validation onto every operation reflexively. The pattern earns its place when:

- The data has flowed through multiple components before causing harm.
- The operation has dangerous side effects (writes to disk, network calls, irreversible state changes).
- The bug has surfaced more than once in different forms.

For a small function with one caller, single-layer validation is fine. The pattern is for code that lives in a system, not for code that lives alone.
