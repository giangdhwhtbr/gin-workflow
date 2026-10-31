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
segments=() bares=() segment="" bare="" quote=""
for ((i = 0; i < ${#COMMAND}; i++)); do
  c=${COMMAND:i:1}
  if [ "$quote" = '"' ] && [ "$c" = "\\" ]; then
    segment+=$c; i=$((i + 1)); c=${COMMAND:i:1}
  elif [ -n "$quote" ]; then
    [ "$c" = "$quote" ] && quote=""
  elif [ "$c" = "\\" ]; then
    segment+=$c; bare+=$c; i=$((i + 1)); c=${COMMAND:i:1}; bare+=$c
  elif [ "$c" = "'" ] || [ "$c" = '"' ]; then
    quote=$c; bare+=Q
  elif [[ "$c" == [\;\&\|$'\n'] ]]; then
    segments+=("$segment"); bares+=("$bare"); segment=""; bare=""; continue
  else
    bare+=$c
  fi
  segment+=$c
done
segments+=("$segment"); bares+=("$bare")
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
block_hooks() { echo "Blocked: $1 skips the gin-workflow git hooks; fix the failing check instead." >&2; exit 2; }
if [[ "$COMMAND" =~ git[[:space:]].*(commit|push|merge)[[:space:]].*--no-verify ]] || \
   [[ "$COMMAND" =~ git[[:space:]].*--no-verify.*(commit|push|merge) ]]; then
  block_hooks "--no-verify"
fi
q="[\"']?"
hooks_c_re="[[:space:]]-c[[:space:]]*${q}core\.hookspath="
# `(`, a backtick or `{` may precede git; `)`, `;` or a backtick may follow a flag.
git_re='(^|[[:space:]/(`{])git([[:space:]]|$)'
commit_n_re='[[:space:]]commit([[:space:]].*)?[[:space:]]-[a-z]*n[a-z]*([[:space:]);`]|$)'
config_env_re='(GIT_CONFIG_(KEY_[0-9]+|PARAMETERS)=.*|--config-env[= ])core\.hookspath'
hooks_config_re="[[:space:]]config[[:space:]](.*[[:space:]])?${q}core\.hookspath${q}([[:space:]]+(.*))?$"
shopt -s nocasematch
for i in "${!segments[@]}"; do
  raw=${segments[i]} bare=${bares[i]}
  # `/usr/bin/git` counts; a `git` inside quotes (bare has it as Q) does not.
  [[ "$bare" =~ $git_re ]] || continue
  # -n on commit only, outside quotes: `-m 'fix -n flag'` is a message, not a flag.
  [[ "$bare" =~ $commit_n_re ]] && block_hooks "git commit -n"
  # hooksPath rules read the raw segment, so a quoted key or value still matches.
  [[ "$raw" =~ $hooks_c_re ]] && block_hooks "-c core.hooksPath"
  [[ "$raw" =~ $config_env_re ]] && block_hooks "core.hooksPath via the git config environment"
  if [[ "$raw" =~ $hooks_config_re ]]; then
    rest=${BASH_REMATCH[3]}
    [[ "$raw" =~ (--unset|[[:space:]]unset[[:space:]]) ]] && block_hooks "unsetting core.hooksPath"
    [[ "$raw" =~ [[:space:]]--get ]] && continue
    [ -n "${rest// /}" ] && block_hooks "setting core.hooksPath"
  fi
done
shopt -u nocasematch

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
