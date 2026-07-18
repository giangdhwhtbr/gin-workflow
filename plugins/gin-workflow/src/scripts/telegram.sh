#!/usr/bin/env bash
# telegram.sh — Send messages and poll for replies via Telegram Bot API.
# Part of gin-workflow plugin.
#
# Usage:
#   telegram.sh send "message"
#   telegram.sh ask  "message" [--timeout 600] [--session-id ID]
#
# Environment (both required — if either is unset, the script exits 0 silently):
#   TELEGRAM_BOT_TOKEN  — Bot API token from @BotFather
#   TELEGRAM_CHAT_ID    — Numeric chat ID for your private conversation
#
# Exit codes:
#   0   — Success (for ask: reply text printed to stdout)
#   1   — Error (API failure, missing dependencies)
#   124 — Timeout (ask mode: no reply within the polling window)

set -euo pipefail

# ── Opt-in guard ─────────────────────────────────────────────────────
# If credentials are not configured, exit silently so callers can
# unconditionally invoke this script without error handling.
if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]]; then
  exit 0
fi

readonly API_BASE="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"
readonly CHAT_ID="${TELEGRAM_CHAT_ID}"
readonly DEFAULT_TIMEOUT=600
readonly POLL_INTERVAL=5

# ── Dependency check ─────────────────────────────────────────────────
command -v curl &>/dev/null || {
  echo "telegram.sh: curl is required but not found" >&2
  exit 1
}

HAS_JQ=false
command -v jq &>/dev/null && HAS_JQ=true

# ── API helpers ──────────────────────────────────────────────────────

# Send a plain-text message. Uses form-encoded POST to avoid JSON
# escaping issues — handles newlines, emoji, and special characters.
tg_send() {
  local text="$1"
  local response
  response=$(curl -sS -X POST "${API_BASE}/sendMessage" \
    --data-urlencode "chat_id=${CHAT_ID}" \
    --data-urlencode "text=${text}" \
    2>&1) || {
    echo "telegram.sh: sendMessage request failed" >&2
    return 1
  }

  # Verify success — works with or without jq
  if ! printf '%s' "$response" | grep -q '"ok" *: *true'; then
    echo "telegram.sh: sendMessage returned error" >&2
    echo "$response" >&2
    return 1
  fi
}

# Fetch updates from the bot. Long-polls for $2 seconds.
tg_get_updates() {
  local offset="$1" poll_timeout="${2:-$POLL_INTERVAL}"
  curl -sS "${API_BASE}/getUpdates?offset=${offset}&timeout=${poll_timeout}&allowed_updates=%5B%22message%22%5D" 2>/dev/null
}

# ── Commands ─────────────────────────────────────────────────────────

cmd_send() {
  if [[ $# -lt 1 ]]; then
    echo "Usage: telegram.sh send \"message\"" >&2
    exit 1
  fi
  tg_send "$1"
}

cmd_ask() {
  if [[ $# -lt 1 ]]; then
    echo "Usage: telegram.sh ask \"message\" [--timeout N] [--session-id ID]" >&2
    exit 1
  fi

  local message="$1"
  shift

  local timeout="$DEFAULT_TIMEOUT"
  local session_id=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --timeout)    timeout="$2"; shift 2 ;;
      --session-id) session_id="$2"; shift 2 ;;
      *)            shift ;;
    esac
  done

  # Append session ID to message if provided
  if [[ -n "$session_id" ]]; then
    message="${message}

📎 Session: ${session_id}"
  fi

  # jq is required for ask mode (JSON polling/parsing)
  if ! $HAS_JQ; then
    echo "telegram.sh: jq is required for 'ask' mode — falling back to send-only" >&2
    tg_send "$message"
    exit 124
  fi

  # Establish offset: skip all existing unprocessed updates
  local init_response
  init_response=$(tg_get_updates 0 0)
  local offset
  offset=$(printf '%s' "$init_response" | jq '[.result[].update_id] | max // 0') || offset=0
  offset=$((offset + 1))

  # Send the question
  tg_send "$message"

  # Poll for reply
  local elapsed=0
  while [[ $elapsed -lt $timeout ]]; do
    local response
    response=$(tg_get_updates "$offset" "$POLL_INTERVAL") || {
      # Network hiccup — retry next iteration
      elapsed=$((elapsed + POLL_INTERVAL))
      continue
    }

    local count
    count=$(printf '%s' "$response" | jq '.result | length') || count=0

    if [[ "$count" -gt 0 ]]; then
      # Find first text message from our chat
      local reply
      reply=$(printf '%s' "$response" | jq -r \
        --argjson cid "$CHAT_ID" \
        '[.result[] | select(.message.chat.id == $cid and .message.text != null)] | first | .message.text // empty' \
      ) || reply=""

      # Advance offset past all processed updates
      local max_id
      max_id=$(printf '%s' "$response" | jq '[.result[].update_id] | max') || max_id=$((offset - 1))
      offset=$((max_id + 1))

      if [[ -n "$reply" ]]; then
        printf '%s\n' "$reply"
        exit 0
      fi
    fi

    elapsed=$((elapsed + POLL_INTERVAL))
  done

  # Timeout — no reply received
  exit 124
}

# ── Main ─────────────────────────────────────────────────────────────
case "${1:-}" in
  send) shift; cmd_send "$@" ;;
  ask)  shift; cmd_ask "$@" ;;
  *)
    cat >&2 <<'EOF'
Usage: telegram.sh <command> [options]

Commands:
  send "message"                          Fire-and-forget notification
  ask  "message" [--timeout N] [--sid ID] Send and wait for reply

Environment:
  TELEGRAM_BOT_TOKEN   Bot API token from @BotFather
  TELEGRAM_CHAT_ID     Numeric chat ID

Exit codes:
  0    Success (ask: reply on stdout)
  1    Error
  124  Timeout (ask: no reply within window)
EOF
    exit 1
    ;;
esac
