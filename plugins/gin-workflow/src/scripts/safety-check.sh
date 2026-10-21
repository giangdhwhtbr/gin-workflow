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
    elif command -v python3 >/dev/null 2>&1; then
      COMMAND=$(printf '%s' "$INPUT" | python3 -c 'import json, sys; print((json.load(sys.stdin).get("tool_input") or {}).get("command") or "")' 2>/dev/null) || {
        echo "Error: failed to parse PreToolUse hook payload as JSON." >&2
        exit 2
      }
      CWD=$(printf '%s' "$INPUT" | python3 -c 'import json, sys; print(json.load(sys.stdin).get("cwd") or "")' 2>/dev/null) || CWD=""
    else
      echo "Error: jq or python3 is required to parse PreToolUse hook payload but neither is installed." >&2
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
# Check each simple command on its own, from its `rm` onward, so a flag or
# target elsewhere in a compound command (`cd ~/x && rm y`) does not count
# against the removal. Separators inside quotes or after a backslash do not split.
segments=() segment="" quote=""
for ((i = 0; i < ${#COMMAND}; i++)); do
  c=${COMMAND:i:1}
  if [ "$quote" = '"' ] && [ "$c" = "\\" ]; then
    segment+=$c; i=$((i + 1)); c=${COMMAND:i:1}
  elif [ -n "$quote" ]; then
    [ "$c" = "$quote" ] && quote=""
  elif [ "$c" = "\\" ]; then
    segment+=$c; i=$((i + 1)); c=${COMMAND:i:1}
  elif [ "$c" = "'" ] || [ "$c" = '"' ]; then
    quote=$c
  elif [[ "$c" == [\;\&\|$'\n'] ]]; then
    segments+=("$segment"); segment=""; continue
  fi
  segment+=$c
done
segments+=("$segment")
for segment in "${segments[@]}"; do
  [[ "$segment" =~ (^|[[:space:]/])rm([[:space:]].*|$) ]] || continue
  removal=${BASH_REMATCH[2]} before=${segment%"${BASH_REMATCH[0]}"}
  # `git rm --cached` only touches the index.
  [[ "$before" =~ ^[[:space:]]*git([[:space:]][^\"\']*)?$ && "$removal" =~ [[:space:]]--cached([[:space:]]|$) ]] && continue
  segment=$removal
  if [[ "$segment" =~ [[:space:]]-[a-zA-Z]*[rR] ]] || [[ "$segment" =~ --recursive ]]; then
    # Also catch quoted/slash forms the bare-target regex misses:
    #   rm -rf "$HOME"   rm -rf "$VAR"   rm -rf ~/*   rm -rf ~/...   rm -rf $HOME/...
    quoted_re='[[:space:]]("\$HOME|"\$|~/|\$HOME/)'
    if [[ "$segment" =~ [[:space:]](\/|\/\*|\.|\.\.|\*|~|\$HOME|\$)($|[[:space:]]) ]] || \
       [[ "$segment" =~ [[:space:]](\.\/|\.\.\/) ]] || \
       [[ "$segment" =~ --no-preserve-root ]] || \
       [[ "$segment" =~ $quoted_re ]]; then
      echo "Blocked: Dangerous recursive file removal target or option detected." >&2
      exit 2
    fi
  fi
done

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
