#!/bin/bash
# safety-check.sh
# Invoked by PreToolUse hook to validate running commands.

set -euo pipefail
# The parser works byte by byte, like bash's `$'\c'`; no multibyte character is a shell metacharacter.
export LC_ALL=C

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
# `unqs` holds each segment with one layer of quoting removed (the text a shell would see).
segments=() bares=() unqs=() segment="" bare="" unq="" quote="" ansi=""
for ((i = 0; i < ${#COMMAND}; i++)); do
  c=${COMMAND:i:1}
  if [ "$quote" = '"' ] && [ "$c" = "\\" ]; then
    segment+=$c; i=$((i + 1)); c=${COMMAND:i:1}; unq+=$c
  elif [ -n "$ansi" ] && [ "$c" = "\\" ]; then
    # In `$'...'` an escape is two characters (`\'` does not close the quote); both stay for the decode below.
    segment+=$c; unq+=$c; i=$((i + 1)); c=${COMMAND:i:1}; unq+=$c
  elif [ "$c" = "$quote" ]; then
    # A quoted flag or word ("-n", "commit") counts as unquoted; quoted text with spaces (a message) stays Q,
    # and so does an empty quote that is a whole word (`-m ""`), so it still counts as a word.
    quote="" q_text=${unq:q_start} next=${COMMAND:i+1:1}
    if [ -n "$ansi" ]; then
      # Decode `$'\x2dn'` (`-n`) with printf %b, which differs from bash's `$'...'` in two ways: it writes
      # octal as `\0nnn` (bash: `\nnn`), it keeps the backslash of `\'`, `\"` and `\?`, and it stops at `\c`,
      # where bash makes `\cX` the control character X & 31 (`\cJ` is a newline, `\cI` a tab).
      ansi="" esc=$q_text q_text=""
      while [[ "$esc" == *\\* ]]; do
        q_text+=${esc%%\\*} esc=${esc#*\\}; e=${esc:0:1} esc=${esc:1}
        case $e in
          [\'\"?]) q_text+=$e ;;
          [0-7]) q_text+="\\0$e" ;;
          c) # `\c\\` is the control character of one backslash.
            if [ "${esc:0:2}" = '\\' ]; then e='\' esc=${esc:2}; else e=${esc:0:1} esc=${esc:1}; fi
            printf -v e '%d' "'$e"; printf -v e '\\0%03o' $((e & 31)); q_text+=$e ;;
          *) q_text+="\\$e" ;;
        esac
      done
      printf -v q_text '%b' "$q_text$esc" 2>/dev/null
      unq=${unq:0:q_start}$q_text
    fi
    if [[ "$q_text" =~ [[:space:]] ]]; then bare+=Q
    elif [ -z "$q_text" ] && [[ "$bare" =~ (^|[[:space:]])$ && "$next" =~ ^([[:space:]\;\&\|]|$) ]]; then bare+=Q
    else bare+=$q_text; fi
  elif [ -n "$quote" ]; then
    unq+=$c
  elif [ "$c" = "\\" ]; then
    # `\-n` is `-n`; an escaped space (`fix\ -n`) keeps the word whole, so bare gets Q for it;
    # `\` + newline is a line continuation the shell drops.
    segment+=$c; i=$((i + 1)); c=${COMMAND:i:1}
    if [ "$c" = $'\n' ]; then :
    elif [[ "$c" == [[:space:]] ]]; then bare+=Q; unq+=$c
    else bare+=$c; unq+=$c; fi
  elif [ "$c" = '$' ] && [[ "${COMMAND:i+1:1}" == [\'\"] ]]; then
    # `$'-n'` and `$"-n"` are quoted words: drop the `$`; `$'...'` also decodes its escapes.
    [ "${COMMAND:i+1:1}" = "'" ] && ansi=1
  elif [ "$c" = "'" ] || [ "$c" = '"' ]; then
    quote=$c q_start=${#unq}
  elif [[ "$c" == [\;\&\|$'\n'] ]]; then
    segments+=("$segment"); bares+=("$bare"); unqs+=("$unq"); segment=""; bare=""; unq=""; continue
  else
    bare+=$c; unq+=$c
  fi
  segment+=$c
done
segments+=("$segment"); bares+=("$bare"); unqs+=("$unq")
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
for s in "$COMMAND" "${bares[*]}"; do
  # git takes an unambiguous prefix of a long option: `--no-veri` and `--no-verif` are `--no-verify`.
  if [[ "$s" =~ git[[:space:]].*(commit|push|merge)[[:space:]].*--no-veri ]] || \
     [[ "$s" =~ git[[:space:]].*--no-veri.*(commit|push|merge) ]]; then
    block_hooks "--no-verify"
  fi
done
q="[\"']?"
# An alias defined on the command line (`-c alias.x=commit x -n`) hides the subcommand, so block any.
hooks_c_re="[[:space:]]-c[[:space:]]*${q}(core\.hookspath=|alias\.)"
# `(`, a backtick or `{` may precede git; `)`, `;` or a backtick may follow a flag.
git_re='(^|[[:space:]/(`{])git([[:space:]]|$)'
git_word_re='^(.*[/(`{])?git$'
git_value_opt_re='^(-C|-c|--git-dir|--work-tree|--namespace|--config-env|--super-prefix|--attr-source)$'
commit_n_word_re='^-[a-z]*n[a-z]*([);`<>].*)?$'
# A short cluster takes the next word only when its first value letter ends it (`-am x`; `-mdoc` is -m doc).
# -S, -u and -t glue their values too, so they may not precede it; nocasematch makes -s and -S one letter.
commit_value_opt_re='^(-[^-mfcstu]*[mfc]|--(message|file|author|date|trailer|reuse-message|reedit-message|fixup|squash))$'
config_env_re='(GIT_CONFIG_(KEY_[0-9]+|PARAMETERS)=.*|--config-env(=|[[:space:]]+))(core\.hookspath|alias\.)'
hooks_config_re="[[:space:]]config[[:space:]](.*[[:space:]])?${q}core\.hookspath${q}([[:space:]]+(.*))?$"
# `sh -c`, `bash -o pipefail -lc`, `dash -c` or `eval`; group 7 is the payload the shell runs. Words before
# the `-c` flag are long options, short flags without c, or option values, so the first `-…c…` flag is the one.
shell_re='(^|[[:space:]/(`{])((ba|z|da|k|mk)?sh([[:space:]]+(--[^[:space:]]*|-[^c[:space:]]*|[^-[:space:]][^[:space:]]*))*[[:space:]]+-[a-z]*c[a-z]*|eval)([[:space:]]+(.*)|$)'
depth=${SAFETY_CHECK_DEPTH:-0}
shopt -s nocasematch
# An exported GIT_CONFIG_* reaches a git in a later command (`export ...; git y -n`), so check the whole line.
for s in "$COMMAND" "${bares[*]}"; do
  [[ "$s" =~ $config_env_re ]] && block_hooks "core.hooksPath or an alias via the git config environment"
done
for i in "${!segments[@]}"; do
  raw=${segments[i]} bare=${bares[i]}
  # Check a wrapped payload as its own command. Detect on bare (a quoted message is not run), take payloads
  # from the unquoted text. A quoted decoy (`X="a sh -c '"`) can match there first, so check the payload of
  # every match: each payload is searched again, and one of them starts at the real wrapper.
  if [[ "$bare" =~ $shell_re ]]; then
    [ "$depth" -lt 3 ] || block_hooks "a command nested in sh -c or eval more than 3 levels deep"
    payload=${unqs[i]}
    while [[ "$payload" =~ $shell_re ]]; do
      payload=${BASH_REMATCH[7]}
      SAFETY_CHECK_DEPTH=$((depth + 1)) bash "${BASH_SOURCE[0]}" "$payload" "$CWD" </dev/null || exit $?
    done
  fi
  # `/usr/bin/git` counts; a `git` inside quotes (bare has it as Q) does not.
  [[ "$bare" =~ $git_re ]] || continue
  # -n on commit only, outside quotes: `-m 'fix -n flag'` is a message, not a flag. After each git, global
  # options (and the value of -C, -c, --git-dir, ...) come first; the first other word is the subcommand.
  # In a commit, the word after a value option (-m, -F, --author, ...) is that value, not a flag.
  read -ra words <<< "$bare"
  sub="" skip=""
  for w in "${words[@]}"; do
    if [ -n "$skip" ]; then skip=""
    elif [[ "$sub" == commit ]]; then
      # A commit's words stay its arguments (`-m fix/git -n`); a git among them can only over-block.
      [[ "$w" =~ $commit_n_word_re ]] && block_hooks "git commit -n"
      [[ "$w" =~ $commit_value_opt_re ]] && skip=1
    elif [[ "$w" =~ $git_word_re ]]; then sub=git
    elif [ "$sub" = git ]; then
      if [[ "$w" =~ $git_value_opt_re ]]; then skip=1; elif [[ "$w" != -* ]]; then sub=$w; fi
    fi
  done
  # hooksPath rules read the raw segment too, so a quoted key or value with spaces still matches.
  for s in "$raw" "$bare"; do
    [[ "$s" =~ $hooks_c_re ]] && block_hooks "-c core.hooksPath or -c alias.*"
    if [[ "$s" =~ $hooks_config_re ]]; then
      rest=${BASH_REMATCH[3]}
      [[ "$s" =~ (--unset|[[:space:]]unset[[:space:]]) ]] && block_hooks "unsetting core.hooksPath"
      [[ "$s" =~ [[:space:]]--get ]] && continue 2
      [ -n "${rest// /}" ] && block_hooks "setting core.hooksPath"
    fi
  done
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
