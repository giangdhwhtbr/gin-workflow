#!/bin/bash
# safety-check.sh
# Invoked by PreToolUse hook to validate running commands.

set -euo pipefail

# Read from stdin if not a TTY (JSON data sent by hook runner)
if [ ! -t 0 ]; then
  INPUT=$(cat)
  if [ -n "$INPUT" ]; then
    if command -v jq >/dev/null 2>&1; then
      # Fail closed: if the payload is not valid JSON, block rather than
      # silently allowing the command through with an empty COMMAND.
      COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null) || {
        echo "Error: failed to parse PreToolUse hook payload as JSON." >&2
        exit 2
      }
      CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty' 2>/dev/null) || CWD=""
    else
      echo "Error: jq is required to parse PreToolUse hook payload but is missing." >&2
      exit 2
    fi
  else
    COMMAND="${1:-}"
    CWD="${2:-}"
  fi
else
  COMMAND="${1:-}"
  CWD="${2:-}"
fi

# 1. Block destructive operations
if [[ "$COMMAND" =~ (^|[[:space:]/])rm([[:space:]]|$) ]]; then
  IS_RECURSIVE=false
  if [[ "$COMMAND" =~ -[a-zA-Z]*[rR][a-zA-Z]* ]] || [[ "$COMMAND" =~ --recursive ]]; then
    IS_RECURSIVE=true
  fi

  if [ "$IS_RECURSIVE" = true ]; then
    # Also catch quoted/slash forms the bare-target regex misses:
    #   rm -rf "$HOME"   rm -rf "$VAR"   rm -rf ~/*   rm -rf ~/...   rm -rf $HOME/...
    quoted_re='[[:space:]]("\$HOME|"\$|~/|\$HOME/)'
    if [[ "$COMMAND" =~ [[:space:]](\/|\/\*|\.|\.\.|\*|~|\$HOME|\$)($|[[:space:]]) ]] || \
       [[ "$COMMAND" =~ [[:space:]](\.\/|\.\.\/) ]] || \
       [[ "$COMMAND" =~ --no-preserve-root ]] || \
       [[ "$COMMAND" =~ $quoted_re ]]; then
      echo "Blocked: Dangerous recursive file removal target or option detected." >&2
      exit 2
    fi
  fi
fi

# 1b. The git hooks are the quality gate: never skip them.
if [[ "$COMMAND" =~ git[[:space:]].*(commit|push|merge)[[:space:]].*--no-verify ]] || \
   [[ "$COMMAND" =~ git[[:space:]].*--no-verify.*(commit|push|merge) ]]; then
  echo "Blocked: --no-verify skips the gin-workflow git hooks; fix the failing check instead." >&2
  exit 2
fi

# 2. Path constraint validation for worktree executions
# If running inside a subagent worker that has a worktree context, verify all operations stay inside it.
if [ -n "${WORKTREE_PATH:-}" ]; then
  if [ -z "${CWD:-}" ]; then
    CWD="."
  fi
  REAL_CWD=$(realpath -q "$CWD" || true)
  REAL_WT=$(realpath -q "$WORKTREE_PATH" || true)
  
  if [ -z "$REAL_CWD" ] || [ -z "$REAL_WT" ] || [[ "$REAL_CWD" != "$REAL_WT"* ]]; then
    echo "Blocked: Operation directory ($REAL_CWD) is outside the assigned worktree ($REAL_WT)." >&2
    exit 2
  fi
fi

exit 0
