# Windows: spawning .cmd shims, UTF-8, and porting the safety hook

**Context**
Epic `gin-workflow-rm-windows-parity` (2026-11-02) made the CLI, the safety hook, and gin-orchestrator workers run on Windows without Git Bash. Three design points came out of review and cost a review cycle each; they apply to any future code that starts a process on Windows or parses shell text in Python.

**Decision/Solution**
- An npm CLI on Windows is a `.cmd` shim, and `cmd.exe` re-parses the whole command line. `NativeCliRunner` therefore runs a `.cmd`/`.bat` as one string: `"<SystemRoot>\System32\cmd.exe" /d /s /v:off /c "<args>"`, every argument wrapped in double quotes with a trailing backslash run doubled, and it refuses up front any argument that contains `"`, `%`, `\r`, `\n` or makes the line longer than 8191 characters (`NativeCliError(SERVICE, "argument cannot be passed safely through cmd.exe")`). `subprocess.list2cmdline` is not enough: it leaves `& | < > ^` unquoted when the argument has no space. Workers that pass the prompt in argv (opencode, antigravity) hit the refusal when their CLI is only a shim; the prompt belongs on stdin.
- The CLI process runs in UTF-8 mode from the shim (`py -3 -X utf8` or `python -X utf8`) and the Windows CI job sets `PYTHONUTF8=1`, so no `subprocess(text=True)` call needs `encoding=`.
- `executable_resolver` probes `PATHEXT` extensions before the bare name on `nt`; `PATHEXT` is always `;`-separated regardless of `os.pathsep`, and `os.access(X_OK)` is only an existence check on Windows, so the bare `claude` sh script would otherwise win over `claude.cmd`.
- `hooks._run_commands` splits a leading `NAME=value` prefix into the child environment only when the value has no quote, `$`, backtick, `;`, `|`, `&`, `<`, `>`, `(`, `)` or backslash; anything else goes to the shell unchanged.
- `safety_check.py` parses the command one character per byte (UTF-8 bytes mapped through latin-1) to match `LC_ALL=C` in the old bash script, and its `--no-veri`, `commit -n`, and `sh -c` checks scan in linear time (`in_order`, `wrapped_payloads`). A direct translation of the bash regexes backtracked quadratically in Python's `re`: a 30K-character command exceeded the 30 s hook timeout, which fails open.

**Consequences**
- Tests that patch `os.name = "nt"` on Linux must build every `Path` before the patch and use `os.path` inside the code under test; `pathlib` raises `NotImplementedError` for `WindowsPath` on POSIX.
- A parity port of a security check needs a differential oracle (the old script kept in a scratch dir and run on fuzzed inputs), plus a long-input timing test; equivalence on the unit tests alone missed the timeout.
- Real Windows behavior of the shim line and `taskkill /T` is only proven by the `windows-latest` job; every local test mocks `Popen`.

**References**
- `plugins/gin-orchestrator/src/scripts/gin_orchestrator/native_cli.py` (`_cmd_shim_line`, `_taskkill_tree`)
- `plugins/gin-workflow/src/scripts/workflow_core/executable_resolver.py`, `hooks.py`
- `plugins/gin-workflow/src/scripts/safety_check.py`, `tests/test_safety_check.py`
- `install.ps1` (shim content, `Register-UserPath`), `.planning/specs/2026-11-02-windows-parity-design.md` R3, R8, R9, R10
- Beads: `gin-workflow-rm-windows-parity.2`, `.3`, `.4`; follow-ups `gin-workflow-inhi`, `gin-workflow-dexy`, `gin-workflow-fo2j`, `gin-workflow-6xcx`, `gin-workflow-orr6`

**Scope**
gin-workflow and gin-orchestrator; any code that spawns a CLI on Windows or ports a shell-text check to Python.
