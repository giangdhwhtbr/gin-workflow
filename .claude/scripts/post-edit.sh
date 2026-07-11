#!/bin/bash
# post-edit.sh
# Runs after files are modified to perform styling/lint formatting if desired.

set -euo pipefail

# Read from stdin if not a TTY (JSON data sent by hook runner)
if [ ! -t 0 ]; then
  INPUT=$(cat)
  if [ -n "$INPUT" ] && command -v jq >/dev/null 2>&1; then
    TARGET_FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
  else
    TARGET_FILE="${1:-}"
  fi
else
  TARGET_FILE="${1:-}"
fi

if [ -n "${TARGET_FILE:-}" ]; then
  echo "Post-edit hook run on: $TARGET_FILE"
fi
