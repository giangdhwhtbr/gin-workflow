#!/usr/bin/env python3
"""PreToolUse safety hook: blocks hook bypasses, broad recursive removals, and work outside the assigned worktree.

Input is the hook JSON on stdin, or the command and cwd as arguments. Exit 2 blocks the command; exit 0 allows it.
The parser works on one character per byte, like bash under `LC_ALL=C`; no multibyte character is a shell
metacharacter. Every pattern uses ASCII classes (`\\s` is `[ \\t\\n\\r\\f\\v]`, POSIX `[[:space:]]` in the C locale)
and DOTALL, because a POSIX `.` also matches a newline.
"""

from dataclasses import dataclass
import json
import os
import re
import sys

BLOCK = 2
MAX_DEPTH = 3
SPACES = " \t\n\r\f\v"


def pattern(text, ignore_case=False):
    return re.compile(text, re.ASCII | re.DOTALL | (re.IGNORECASE if ignore_case else 0))


# Case-sensitive patterns.
RM_RE = pattern(r"(^|[\s/])rm(\s.*|\Z)")
GIT_RM_BEFORE_RE = pattern(r"^\s*git(\s[^\"']*)?\Z")
CACHED_RE = pattern(r"\s--cached(\s|\Z)")
RECURSIVE_RE = pattern(r"\s-[a-zA-Z]*[rR]|--recursive")
# Bare targets, `./` and `../`, and quoted or slash forms: rm -rf "$HOME", "$VAR", ~/*, ~/..., $HOME/...
DANGEROUS_TARGET_RE = pattern(r'\s(/|/\*|\.|\.\.|\*|~|\$HOME|\$)(\Z|\s)|\s(\./|\.\./)|--no-preserve-root'
                              r'|\s("\$HOME|"\$|~/|\$HOME/)')
# `git\s.*(commit|push|merge)\s.*--no-veri` or `git\s.*--no-veri.*(commit|push|merge)`, as parts found in order
# (see `in_order`). git takes an unambiguous prefix of a long option: `--no-veri` and `--no-verif` are `--no-verify`.
GIT_SPACE_RE = pattern(r"git\s")
SUBCOMMAND_SPACE_RE = pattern(r"(commit|push|merge)\s")
SUBCOMMAND_RE = pattern(r"commit|push|merge")
NO_VERI_RE = pattern(r"--no-veri")

# Case-insensitive patterns: git config keys and subcommand words ignore case here (`core.HOOKSPATH`).
QUOTE = "[\"']?"
# An alias defined on the command line (`-c alias.x=commit x -n`) hides the subcommand, so block any.
HOOKS_C_RE = pattern(rf"\s-c\s*{QUOTE}(core\.hookspath=|alias\.)", True)
# `(`, a backtick or `{` may precede git; `)`, `;` or a backtick may follow a flag.
GIT_RE = pattern(r"(^|[\s/(`{])git(\s|\Z)", True)
GIT_WORD_RE = pattern(r"^(.*[/(`{])?git\Z", True)
GIT_VALUE_OPT_RE = pattern(r"^(-C|-c|--git-dir|--work-tree|--namespace|--config-env|--super-prefix"
                           r"|--attr-source)\Z", True)
# The lookahead finds the n once; `-[a-z]*n[a-z]*` retries every n of a long run and is quadratic.
COMMIT_N_WORD_RE = pattern(r"^-(?=[a-z]*n)[a-z]*([);`<>].*)?\Z", True)
# A short cluster takes the next word only when its first value letter ends it (`-am x`; `-mdoc` is -m doc).
# -S, -u and -t glue their values too, so they may not precede it; ignoring case makes -s and -S one letter.
COMMIT_VALUE_OPT_RE = pattern(r"^(-[^-mfcstu]*[mfc]|--(message|file|author|date|trailer|reuse-message"
                              r"|reedit-message|fixup|squash))\Z", True)
# `GIT_CONFIG_(KEY_[0-9]+|PARAMETERS)=.*(core\.hookspath|alias\.)` as parts in order, or `--config-env` with the key.
CONFIG_ENV_ASSIGN_RE = pattern(r"GIT_CONFIG_(KEY_[0-9]+|PARAMETERS)=", True)
HOOKS_KEY_RE = pattern(r"core\.hookspath|alias\.", True)
CONFIG_ENV_FLAG_RE = pattern(r"--config-env(=|\s+)(core\.hookspath|alias\.)", True)
# `(.*?\s)??` prefers the first `core.hookspath`; a greedy group matched the last one, so a value followed by the
# key again (`core.hooksPath /x core.hooksPath`) looked like a read. The outer `??` is needed too: `(.*?\s)?`
# still enters the group and reaches the last key.
HOOKS_CONFIG_RE = pattern(rf"\sconfig\s(.*?\s)??{QUOTE}core\.hookspath{QUOTE}(\s+(.*))?\Z", True)
UNSET_RE = pattern(r"(--unset|\sunset\s)", True)
GET_RE = pattern(r"\s--get", True)
# `sh -c`, `bash -o pipefail -lc`, `dash -c` or `eval` (see `wrapped_payloads`). Words before the `-c` flag are
# long options, short flags without c, or option values, so the first `-…c…` flag is the one.
SHELL_NAME_RE = pattern(r"(ba|z|da|k|mk)?sh", True)
EVAL_NAME_RE = pattern(r"eval", True)
SHELL_OPTION_WORD_RE = pattern(r"--\S*|-(?!-)[^c\s]*|[^-\s]\S*", True)
SHELL_C_FLAG_RE = pattern(r"-(?=[a-z]*c)[a-z]*", True)
WORD_RE = pattern(r"\S+")
# `read -ra` splits on the default IFS only.
IFS_RE = re.compile("[ \t\n]+")

SIMPLE_ESCAPES = {"a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b", "f": "\f", "n": "\n", "r": "\r", "t": "\t",
                  "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?"}
OCTAL = "01234567"
HEX = "0123456789abcdefABCDEF"


@dataclass
class Segment:
    raw: str  # the simple command as typed
    bare: str  # one quoting layer removed; quoted text with spaces, or an empty whole-word quote, becomes "Q"
    unquoted: str  # one quoting layer removed, text kept


def to_bytes_str(text):
    """One character per UTF-8 byte; `surrogateescape` restores the bytes of an argument that is not UTF-8."""
    return text.encode("utf-8", "surrogateescape").decode("latin-1")


def read_input(argv):
    """(command, cwd): the hook JSON on stdin when stdin is not a terminal and not empty, else the arguments."""
    if not sys.stdin.isatty():
        raw = sys.stdin.buffer.read()
        if raw.strip():
            try:
                payload = json.loads(raw)
                tool_input = payload.get("tool_input")
                if not isinstance(tool_input, (dict, type(None))):
                    raise ValueError("tool_input is not an object")  # jq cannot index it either
                command = str((tool_input or {}).get("command") or "")
                cwd = str(payload.get("cwd") or "")
                (command + cwd).encode("utf-8")  # a lone surrogate (`\ud800`) is malformed, as jq reports it
            except (ValueError, AttributeError, RecursionError):
                print("Error: failed to parse PreToolUse hook payload as JSON.", file=sys.stderr)
                raise SystemExit(BLOCK)
            # Drop NUL bytes and trailing newlines like bash `$(...)`, so `-\u0000n` reads as `-n`.
            return command.replace("\0", "").rstrip("\n"), cwd.replace("\0", "").rstrip("\n")
    return (argv[1] if len(argv) > 1 else ""), (argv[2] if len(argv) > 2 else "")


def unicode_bytes(value):
    """bash's `\\u` and `\\U` above 0x7f: UTF-8 bytes; values from 0x80000000 decode to nothing."""
    if value >= 0x80000000:
        return ""
    # simplified: a value above U+10FFFF becomes one 0xff byte where bash writes 4 to 6; both are non-ASCII,
    # which is all the rules read. Write bash's extended UTF-8 if a rule ever reads these bytes.
    if value > 0x10FFFF:
        return "\xff"
    return chr(value).encode("utf-8", "surrogatepass").decode("latin-1")


def decode_ansi_c(text):
    """The text of a bash `$'...'` quote, decoded; a NUL ends it, as it ends a bash string."""
    out = []
    i = 0
    while i < len(text):
        c = text[i]
        i += 1
        if c != "\\" or i == len(text):
            out.append(c)
            continue
        e = text[i]
        i += 1
        if e in SIMPLE_ESCAPES:
            out.append(SIMPLE_ESCAPES[e])
        elif e in OCTAL:
            end = i
            while end < i + 2 and end < len(text) and text[end] in OCTAL:
                end += 1
            out.append(chr(int(e + text[i:end], 8) & 0xFF))
            i = end
        elif e == "c":
            # `\cX` is the control character X & 31; `\c\\` is the control character of one backslash.
            control = "\\" if text[i:i + 2] == "\\\\" else text[i:i + 1]
            i += 2 if text[i:i + 2] == "\\\\" else 1
            out.append(chr(ord(control) & 31) if control else "\0")
        elif e in "xuU":
            width = {"x": 2, "u": 4, "U": 8}[e]
            end = i
            while end < i + width and end < len(text) and text[end] in HEX:
                end += 1
            if end == i:
                out.append("\\" + e)
            elif e == "x":
                out.append(chr(int(text[i:end], 16)))
            else:
                value = int(text[i:end], 16)
                out.append(chr(value) if value <= 0x7F else unicode_bytes(value))
            i = end
        else:
            out.append("\\" + e)
    return "".join(out).split("\0", 1)[0]


def split_segments(command):
    """Split on `;`, `&`, `|` and newline outside quotes and escapes, removing one layer of quoting."""
    segments = []
    segment = bare = unquoted = quote = ""
    ansi = False
    quote_start = 0
    i = 0
    while i < len(command):
        c = command[i]
        if quote == '"' and c == "\\":
            segment += c
            i += 1
            c = command[i:i + 1]
            unquoted += c
        elif ansi and c == "\\":
            # In `$'...'` an escape is two characters (`\'` does not close the quote); both stay for the decode.
            segment += c
            unquoted += c
            i += 1
            c = command[i:i + 1]
            unquoted += c
        elif c == quote:
            # A quoted flag or word ("-n", "commit") counts as unquoted; quoted text with spaces (a message) is Q,
            # and so is an empty quote that is a whole word (`-m ""`), so it still counts as a word.
            quote = ""
            quoted = unquoted[quote_start:]
            following = command[i + 1:i + 2]
            if ansi:
                ansi = False
                quoted = decode_ansi_c(quoted)
                unquoted = unquoted[:quote_start] + quoted
            if any(char in SPACES for char in quoted):
                bare += "Q"
            elif not quoted and (not bare or bare[-1] in SPACES) and (not following or following in SPACES + ";&|"):
                bare += "Q"
            else:
                bare += quoted
        elif quote:
            unquoted += c
        elif c == "\\":
            # `\-n` is `-n`; an escaped space (`fix\ -n`) keeps the word whole, so bare gets Q for it;
            # `\` + newline is a line continuation the shell drops.
            segment += c
            i += 1
            c = command[i:i + 1]
            if c == "\n":
                pass
            elif c and c in SPACES:
                bare += "Q"
                unquoted += c
            else:
                bare += c
                unquoted += c
        elif c == "$" and command[i + 1:i + 2] in ("'", '"'):
            # `$'-n'` and `$"-n"` are quoted words: drop the `$`; `$'...'` also decodes its escapes.
            ansi = command[i + 1] == "'"
        elif c in "'\"":
            quote = c
            quote_start = len(unquoted)
        elif c in ";&|\n":
            segments.append(Segment(segment, bare, unquoted))
            segment = bare = unquoted = ""
            i += 1
            continue
        else:
            bare += c
            unquoted += c
        segment += c
        i += 1
    segments.append(Segment(segment, bare, unquoted))
    return segments


def in_order(text, *parts):
    """True when each part matches after the previous one ends: `A.*B.*C` in linear time, where one regex with
    several `.*` backtracks polynomially on a long command. Taking each part's first match is enough because
    no part's match can sit inside a later-starting one."""
    position = 0
    for part in parts:
        match = part.search(text, position)
        if not match:
            return False
        position = match.end()
    return True


def wrapped_payloads(text):
    r"""The payload of each wrapper, left to right, each searched for in the previous payload: group 7 of
    `(^|[\s/(`{])((ba|z|da|k|mk)?sh(\s+(--\S*|-(?!-)[^c\s]*|[^-\s]\S*))*\s+-[a-z]*c[a-z]*|eval)(\s+(.*)|\Z)`.
    One pass over the words: that regex rescans the rest of the text from every `sh` word, which is quadratic on
    a long run of them."""
    words = list(WORD_RE.finditer(text))
    # first_flag[i]: the first word from i on that is a short flag with c, the only kind that ends the shell options.
    first_flag = [len(words)] * (len(words) + 1)
    for i in range(len(words) - 1, -1, -1):
        first_flag[i] = first_flag[i + 1] if SHELL_OPTION_WORD_RE.fullmatch(words[i].group()) else i
    i = 0
    while i < len(words):
        # The wrapper name starts the word or follows its last `/`, `(`, backtick or `{`.
        name = re.split("[/(`{]", words[i].group())[-1]
        flag = first_flag[i + 1]
        if EVAL_NAME_RE.fullmatch(name):
            end = i
        elif SHELL_NAME_RE.fullmatch(name) and flag < len(words) and SHELL_C_FLAG_RE.fullmatch(words[flag].group()):
            end = flag
        else:
            i += 1
            continue
        yield text[words[end].end():].lstrip(SPACES)
        i = end + 1


def block(message):
    print(f"Blocked: {message} skips the gin-workflow git hooks; fix the failing check instead.", file=sys.stderr)
    raise SystemExit(BLOCK)


def check_removal(segments):
    """Check each simple command from its `rm` onward, so a flag or target elsewhere in a compound command
    (`cd ~/x && rm y`) does not count against the removal."""
    for segment in segments:
        match = RM_RE.search(segment.raw)
        if not match:
            continue
        removal = match.group(2)
        # `git rm --cached` only touches the index.
        if GIT_RM_BEFORE_RE.search(segment.raw[:match.start()]) and CACHED_RE.search(removal):
            continue
        if RECURSIVE_RE.search(removal) and DANGEROUS_TARGET_RE.search(removal):
            print("Blocked: Dangerous recursive file removal target or option detected.", file=sys.stderr)
            raise SystemExit(BLOCK)


def check_git_words(bare):
    """-n on commit only, outside quotes: `-m 'fix -n flag'` is a message, not a flag. After each git, global
    options (and the value of -C, -c, --git-dir, ...) come first; the first other word is the subcommand.
    In a commit, the word after a value option (-m, -F, --author, ...) is that value, not a flag."""
    sub = ""
    skip = False
    for word in IFS_RE.split(bare):
        if not word:
            continue
        if skip:
            skip = False
        elif sub.lower() == "commit":
            # A commit's words stay its arguments (`-m fix/git -n`); a git among them can only over-block.
            if COMMIT_N_WORD_RE.search(word):
                block("git commit -n")
            if COMMIT_VALUE_OPT_RE.search(word):
                skip = True
        elif GIT_WORD_RE.search(word):
            sub = "git"
        elif sub == "git":
            if GIT_VALUE_OPT_RE.search(word):
                skip = True
            elif not word.startswith("-"):
                sub = word


def check_hooks_path(segment):
    """hooksPath rules read the raw segment too, so a quoted key or value with spaces still matches."""
    for text in (segment.raw, segment.bare):
        if HOOKS_C_RE.search(text):
            block("-c core.hooksPath or -c alias.*")
        match = HOOKS_CONFIG_RE.search(text)
        if match:
            if UNSET_RE.search(text):
                block("unsetting core.hooksPath")
            if GET_RE.search(text):
                return
            if (match.group(3) or "").replace(" ", ""):
                block("setting core.hooksPath")


def check_hooks(command, segments, cwd, depth):
    """The git hooks are the quality gate: never skip them."""
    bares = " ".join(segment.bare for segment in segments)
    for text in (command, bares):
        if (in_order(text, GIT_SPACE_RE, SUBCOMMAND_SPACE_RE, NO_VERI_RE)
                or in_order(text, GIT_SPACE_RE, NO_VERI_RE, SUBCOMMAND_RE)):
            block("--no-verify")
    # An exported GIT_CONFIG_* reaches a git in a later command (`export ...; git y -n`), so check the whole line.
    for text in (command, bares):
        if in_order(text, CONFIG_ENV_ASSIGN_RE, HOOKS_KEY_RE) or CONFIG_ENV_FLAG_RE.search(text):
            block("core.hooksPath or an alias via the git config environment")
    for segment in segments:
        # Check a wrapped payload as its own command. Detect on bare (a quoted message is not run), take payloads
        # from the unquoted text. A quoted decoy (`X="a sh -c '"`) can match there first, so check the payload of
        # every match: each payload is searched again, and one of them starts at the real wrapper.
        if next(wrapped_payloads(segment.bare), None) is not None:
            if depth >= MAX_DEPTH:
                block("a command nested in sh -c or eval more than 3 levels deep")
            for payload in wrapped_payloads(segment.unquoted):
                check(payload, cwd, depth + 1)
        # `/usr/bin/git` counts; a `git` inside quotes (bare has it as Q) does not.
        if GIT_RE.search(segment.bare):
            check_git_words(segment.bare)
            check_hooks_path(segment)


def real_path(path):
    """GNU `realpath -q`: None when a component other than the last does not exist; the last may be missing."""
    resolved = os.path.realpath(path)
    return resolved if os.path.isdir(os.path.dirname(resolved)) else None


def check_worktree(cwd):
    """Inside a worker with a worktree context, every operation stays inside it."""
    worktree = os.environ.get("WORKTREE_PATH", "")
    if not worktree:
        return
    real_cwd = real_path(cwd or ".") or ""
    real_worktree = real_path(worktree) or ""
    if not real_cwd or not real_worktree or not real_cwd.startswith(real_worktree):
        print(f"Blocked: Operation directory ({real_cwd}) is outside the assigned worktree ({real_worktree}).",
              file=sys.stderr)
        raise SystemExit(BLOCK)


def check(command, cwd, depth):
    segments = split_segments(command)
    check_removal(segments)
    check_hooks(command, segments, cwd, depth)
    check_worktree(cwd)


def main(argv):
    command, cwd = read_input(argv)
    try:
        depth = int(os.environ.get("SAFETY_CHECK_DEPTH", "0") or 0)
    except ValueError:
        print("Error: SAFETY_CHECK_DEPTH must be an integer.", file=sys.stderr)
        raise SystemExit(BLOCK)
    check(to_bytes_str(command), cwd, depth)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
