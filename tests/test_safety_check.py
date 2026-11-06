"""safety_check.py blocks commands that skip the gin git hooks or remove broad paths."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "plugins/gin-workflow/src/scripts/safety_check.py"


def exit_code(command):
    return subprocess.run([sys.executable, str(SCRIPT), command], stdin=subprocess.DEVNULL, capture_output=True).returncode


class TestNoVerifyBlocked(unittest.TestCase):
    def test_blocks_no_verify_on_commit_push_merge(self):
        for command in ("git commit --no-verify -m x", "git push --no-verify", "git push origin main --no-verify",
                        "git merge --no-verify topic", "git -C /tmp/r commit -am x --no-verify",
                        'git "commit" --no-verify', "git 'push' --no-verify"):
            self.assertEqual(2, exit_code(command), command)

    def test_allows_normal_commands(self):
        for command in ("git commit -m 'fix -n flag'", "git push -n", "git push origin main", "git status"):
            self.assertEqual(0, exit_code(command), command)

    def test_blocks_abbreviated_no_verify(self):
        # git accepts unambiguous prefixes of a long option: --no-veri and --no-verif are --no-verify.
        for command in ("git commit --no-veri -m x", "git commit -m x --no-verif", "git push --no-veri",
                        "git push origin main --no-verif"):
            self.assertEqual(2, exit_code(command), command)

    def test_allows_other_no_options(self):
        for command in ("git merge --no-ff topic", "git commit --no-verbose -m x", "git log -n 3"):
            self.assertEqual(0, exit_code(command), command)


class TestHookBypassBlocked(unittest.TestCase):
    def test_us2_blocks_hook_bypasses(self):
        for command in ("git commit -n -m x", "git commit -anm x", "git commit -m x -n",
                        "git -c core.hooksPath=/dev/null commit -m x", "git -c core.hookspath=/tmp push",
                        "git config core.hooksPath /tmp/h", 'git config --local core.hooksPath "/tmp/h"',
                        "git config set core.hooksPath /tmp/h", "git config --unset core.hooksPath",
                        "cd /tmp && git commit -n -m x", "/usr/bin/git commit -n -m x",
                        "git -c 'core.hooksPath=/x' commit -m y", 'git -c "core.hooksPath=/x" commit -m y',
                        "git config 'core.hooksPath' /tmp/h",
                        "git config core.hooksPath /x core.hooksPath"):
            self.assertEqual(2, exit_code(command), command)

    @unittest.skipIf(os.name == "nt", "passes a 120,000-character argv over the 32,767-character Windows command line; needs POSIX ARG_MAX")
    def test_repeated_config_words_stay_linear(self):
        # 10000 words took 15-18 s with a quadratic pattern and the cost grows with the square of the length; 15000 words
        # stay under the 128 KB limit of one argument.
        for command, expected in (("git" + " config" * 15000, 0), ("git" + " config" * 15000 + " core.hooksPath /x", 2),
                                  ("git" + " config" * 15000 + " core.hooksPath", 0)):
            done = subprocess.run([sys.executable, str(SCRIPT), command], stdin=subprocess.DEVNULL, capture_output=True,
                                  timeout=10)
            self.assertEqual(expected, done.returncode, command[-30:])

    def test_us2_blocks_subshell_and_group_forms(self):
        for command in ("(git commit -n -m x)", "cd d && (git commit -a -n)", "echo $(git commit -n -m x)",
                        "echo `git commit -n -m x`", "git commit -m x -n)", "{ git commit -n -m x; }"):
            self.assertEqual(2, exit_code(command), command)

    def test_us2_blocks_git_config_env_hookspath(self):
        for command in ("GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/x git commit",
                        "git --config-env=core.hooksPath=FOO commit",
                        "git --config-env core.hooksPath=FOO commit",
                        "GIT_CONFIG_PARAMETERS=\"'core.hooksPath'='/x'\" git commit"):
            self.assertEqual(2, exit_code(command), command)

    def test_blocks_quoted_flags_and_words(self):
        for command in ('git commit "-n"', "git commit '-n' -m x", 'git "commit" -n', '"git" commit -n',
                        'git commit -m x ""-n', 'git -c "core.hooksPath"=/x commit', 'git "config" core.hooksPath /x'):
            self.assertEqual(2, exit_code(command), command)

    def test_blocks_shell_and_eval_wrapped_commands(self):
        for command in ('sh -c "git commit -n"', 'bash -c "git commit -n"', "zsh -c 'git commit -n'",
                        'eval "git commit -n"', 'bash -lc "git commit -n"', 'cd x && sh -c "git commit -n"',
                        'sh -c "bash -c \'git commit -n\'"', 'sh -c "sh -c \\"git commit -n\\""',
                        'sh -c "rm -rf /"', 'sh -c "sh -c \'sh -c \\"sh -c ls\\"\'"',
                        'bash -o pipefail -c "git commit -n"', 'dash -c "git commit -n"', 'ksh -c "git commit -n"',
                        'bash --norc -ce "git commit -n"', 'bash -c "git commit -n -c x"'):
            self.assertEqual(2, exit_code(command), command)

    def test_blocks_wrapped_command_after_a_quoted_decoy_wrapper(self):
        for command in ("X=\"a sh -c '\" bash -c \"git commit -n\" Y=\"'\"",
                        "X=\"a sh -c '\" bash -c \"git commit -n\"",
                        "env X=\"a eval '\" bash -c \"git commit -n\"",
                        "X=\"a eval '\" eval \"git commit -n\"",
                        "X=\"a sh -c '\" bash -c \"git -c core.hooksPath=/x commit\""):
            self.assertEqual(2, exit_code(command), command)

    def test_blocks_ansi_c_quoted_and_escaped_flags(self):
        for command in ("git commit $'-n'", 'git commit $"-n"', "git commit \\-n", "git \\commit -n",
                        "git \\\ncommit -n", "git commit \\\n-n", "git commit -m x \\\n-n"):
            self.assertEqual(2, exit_code(command), command)

    def test_blocks_ansi_c_escapes(self):
        # bash decodes $'...': \x2d and \055 are `-`, \x63 is `c`.
        for command in ("git commit $'\\x2dn'", "git commit $'\\055n'", "git commit $'\\55n'",
                        "git commit $'\\x2d\\x2dno-verify' -m x", "git $'commit' -n", "git $'\\x63ommit' -n",
                        "sh -c $'git commit \\x2dn'", "git commit $'\\'' $'\\x2dn'"):
            self.assertEqual(2, exit_code(command), command)

    def test_blocks_ansi_c_control_characters(self):
        # bash makes \cJ a newline and \cI a tab, so they split commands and words.
        for command in ("sh -c $'true\\cJgit commit -n'", "eval $'true\\cJgit commit -n'",
                        "sh -c $'git commit\\cI-n'"):
            self.assertEqual(2, exit_code(command), command)

    def test_blocks_ansi_c_control_of_a_backslash_or_multibyte_character(self):
        # \c\\ is one control character (0x1c), and \c uses the first byte of a multibyte character (ʀ: 0xca, newline).
        for command in (r"sh -c $'true;\c\\000;git commit -n'", r"sh -c $'true;\c\\x00;git commit -n'",
                        "sh -c $'true\\cʀ;git commit -n'"):
            self.assertEqual(2, exit_code(command), command)

    def test_allows_ansi_c_quoted_messages(self):
        for command in ("git commit -m $'fix \\x2dn flag'", "git commit -m $'it\\'s -n'",
                        "git commit -m $'a\\nb' -a"):
            self.assertEqual(0, exit_code(command), command)

    def test_blocks_git_alias_definitions(self):
        # An alias can run commit under another name, so any alias defined on the command line is blocked.
        for command in ("git -c alias.x=commit x -n", "git -c 'alias.x=commit' x", 'git -c "alias.x=commit" x',
                        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.y GIT_CONFIG_VALUE_0=commit git y -n",
                        "git --config-env=alias.z=A z", "git --config-env alias.z=A z",
                        "A=commit git --config-env  alias.z=A z -n", "A=commit git --config-env\talias.z=A z -n"):
            self.assertEqual(2, exit_code(command), command)

    def test_blocks_git_config_env_exported_in_an_earlier_command(self):
        for command in ("export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.y GIT_CONFIG_VALUE_0=commit; git y -n",
                        "export GIT_CONFIG_PARAMETERS=\"'alias.x'='commit'\" && git x -n"):
            self.assertEqual(2, exit_code(command), command)

    def test_allows_other_config_overrides(self):
        for command in ("git -c user.name=x commit -m y", "git -c core.editor=vim commit"):
            self.assertEqual(0, exit_code(command), command)

    def test_blocks_commit_after_global_options_and_value_options(self):
        for command in ("git -C . -c x=y commit -n", "git --no-pager commit -n", 'git commit --author "x" -n',
                        "git commit -F msg.txt -n", "git -C . commit -n", "git commit -an", "git commit -nm x",
                        "git commit -am x -n", "git --git-dir=.git --work-tree . commit -n",
                        "git commit -mdoc -n", "git commit -mm -n", "git commit -Cabc -n", 'git commit -m"a b"c -n',
                        "git commit -tm -n", "git commit --message=fix/git -n", "git commit -mfix/git -n",
                        'git commit --message="docs/git" -n', "git commit -m v vendor/git -n", "git commit -a git -n",
                        'git commit -m "" -n -m "real message"', 'git commit --allow-empty-message -m "" -n',
                        "git commit -m $'' -n", "git commit -n>/dev/null"):
            self.assertEqual(2, exit_code(command), command)

    def test_allows_commit_word_as_option_value_and_n_as_message(self):
        for command in ('git log --grep "commit" -n 5', 'git log --author "commit" -n 3', 'git commit -m "-n"',
                        'git commit -m "-nightly"', 'git commit -m "a" -m "-n"', "git log --grep commit -n 5",
                        "git show -n 1", "git stash list -n 2", "git commit --message=-n", "git commit -F -n"):
            self.assertEqual(0, exit_code(command), command)

    def test_allows_escaped_space_inside_a_word(self):
        self.assertEqual(0, exit_code("git commit -m fix\\ -n"))

    def test_allows_shell_wrapped_safe_commands_and_quoted_payloads(self):
        for command in ('git commit -m "sh -c git commit -n"', 'bash -c "git commit -m \\"fix -n\\""',
                        "sh -c 'git status'", 'eval "git log -n 3"'):
            self.assertEqual(0, exit_code(command), command)

    def test_us2_allows_reads_and_quoted_text(self):
        for command in ("git commit -m 'fix -n flag'", 'git commit -m "fix -n" -a', "git status",
                        "git commit -m '$(git log -n 1)'", "(git log -n 1)", 'git commit -m "skip -n"', "git push -n",
                        "git config core.hooksPath", "git config --get core.hooksPath",
                        "git commit --amend --no-edit", "git log -n 3",
                        'bd create --description "git commit -n"'):
            self.assertEqual(0, exit_code(command), command)


class TestRecursiveRemoval(unittest.TestCase):
    def test_blocks_dangerous_targets(self):
        for command in ("rm -rf /", "rm -rf ~", "rm -rf ~/", "rm -r .", "rm -fr ..", 'rm -rf "$HOME"', "rm --recursive $HOME",
                        "cd /tmp && rm -rf ~/*", "ls; sudo rm -rf /", "git rm -r .", "find . -exec rm -rf ./ \\;",
                        'rm -rf "a;b" ~', "echo x ; rm -rf 'a|b' /", "rm -rf a\\;b ~", "echo ok\nrm -rf ~",
                        'git diff --cached -- "a\\"b" ; rm -rf /', 'git log "x" rm -rf --cached /',
                        "echo $(rm -rf ~)", "echo `rm -rf ~`", "git log $(rm -rf ~ --cached )", "git log rm -rf --cached ~",
                        "git -C rm -rf --cached ~", "git -C $(rm -rf ~ --cached ) status", "git -C$(rm -rf ~ --cached ) status", "git -c x=`rm -rf ~ --cached ` status",
                        "git rm --cached $(rm -rf ~)", "git rm -r --cached x $(rm -rf ~ --cached )"):
            self.assertEqual(2, exit_code(command), command)

    def test_checks_each_command_of_a_compound_command_on_its_own(self):
        for command in ("cd ~/gin-console && git rm -r --cached .beads", "cd ~/x && rm -r build",
                        "git -C ~/gin-console rm -r --cached .beads", "git -c core.quotepath=off rm -r --cached .",
                        "x=$(rm -f tmp.txt)",
                        "cd /tmp/a && rm .beads && ls -R ~/", "unlink /home/u/gin-workflow/.beads && ls ~/",
                        "rm /tmp/gin-workflow/x.txt", 'bd create --description "cd ~/x && git rm -r --cached .beads"'):
            self.assertEqual(0, exit_code(command), command)


class TestPayloadFromStdin(unittest.TestCase):
    def test_python_parses_the_payload_without_jq_or_bash(self):
        # PATH holds an empty directory: no jq, bash, or other tool is needed.
        with tempfile.TemporaryDirectory() as directory:
            for command, expected in (("git commit --no-verify -m x", 2), ("git status", 0)):
                payload = json.dumps({"tool_input": {"command": command}, "cwd": directory})
                done = subprocess.run([sys.executable, str(SCRIPT)], input=payload.encode(),
                                      env={"PATH": directory}, capture_output=True)
                self.assertEqual(expected, done.returncode, (command, done.stderr))


    def test_us4_malformed_payload_is_blocked(self):
        for payload in (b"{not json", b"[1]", b'{"tool_input": "x"}', b'{"tool_input": {"command": "ls \\ud800"}}'):
            done = subprocess.run([sys.executable, str(SCRIPT)], input=payload, capture_output=True)
            self.assertEqual(2, done.returncode, payload)
            self.assertIn(b"Error: failed to parse PreToolUse hook payload as JSON.", done.stderr)


    def test_us4_long_command_is_checked_within_the_hook_timeout(self):
        # A heredoc that mentions git commit, push, and GIT_CONFIG_* many times must not backtrack for minutes.
        line = "Run git commit -m x, then git push and git merge; GIT_CONFIG_KEY_0=user.name stays. " * 20
        payload = json.dumps({"tool_input": {"command": "cat > notes.md <<'EOF'\n" + (line + "\n") * 80 + "EOF"}})
        done = subprocess.run([sys.executable, str(SCRIPT)], input=payload.encode(), capture_output=True, timeout=10)
        self.assertEqual(0, done.returncode, done.stderr)

    @unittest.skipIf(os.name == "nt", "passes an argv over the 32,767-character Windows command line; needs POSIX ARG_MAX")
    def test_long_flag_and_wrapper_runs_are_checked_in_linear_time(self):
        for command in ("git commit -" + "n" * 40000 + "! ; git commit -n -m x", "sh " * 20000 + "; git commit -n"):
            start = time.monotonic()
            self.assertEqual(2, exit_code(command), command[:40])
            self.assertLess(time.monotonic() - start, 5, command[:40])

    def test_parser_errors_are_blocked(self):
        for payload in (b"[" * 100000, b'{"tool_input": []}', b'{"tool_input": 0}', b'{"tool_input": false}'):
            done = subprocess.run([sys.executable, str(SCRIPT)], input=payload, capture_output=True)
            self.assertEqual(2, done.returncode, payload[:40])
            self.assertIn(b"Error: failed to parse PreToolUse hook payload as JSON.", done.stderr)

    def test_invalid_depth_is_blocked(self):
        done = subprocess.run([sys.executable, str(SCRIPT), "ls"], stdin=subprocess.DEVNULL, capture_output=True,
                              env={**os.environ, "SAFETY_CHECK_DEPTH": "abc"})
        self.assertEqual(2, done.returncode)
        self.assertIn(b"Error: SAFETY_CHECK_DEPTH", done.stderr)
        self.assertNotIn(b"Traceback", done.stderr)


class TestWorktreeBoundary(unittest.TestCase):
    def exit_code_in(self, worktree, cwd):
        payload = json.dumps({"tool_input": {"command": "ls"}, "cwd": cwd})
        return subprocess.run([sys.executable, str(SCRIPT)], input=payload.encode(), capture_output=True,
                              env={**os.environ, "WORKTREE_PATH": worktree}).returncode

    def test_only_the_last_component_of_cwd_may_be_missing(self):
        # GNU `realpath -q` resolves a missing last component but fails on a missing parent; `$(...)` dropped the
        # trailing newline jq printed after the cwd.
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(0, self.exit_code_in(directory, directory + "/missing-leaf"))
            self.assertEqual(0, self.exit_code_in(directory, directory + "\n"))
            self.assertEqual(2, self.exit_code_in(directory, directory + "/missing/leaf"))
            self.assertEqual(2, self.exit_code_in(directory, "/"))

    def test_a_sibling_whose_name_extends_the_worktree_path_is_outside(self):
        with tempfile.TemporaryDirectory() as parent:
            worktree, sibling = os.path.join(parent, "wt"), os.path.join(parent, "wt2")
            os.mkdir(worktree)
            os.mkdir(sibling)
            os.mkdir(os.path.join(worktree, "sub"))
            self.assertEqual(2, self.exit_code_in(worktree, sibling))
            self.assertEqual(0, self.exit_code_in(worktree, worktree))
            self.assertEqual(0, self.exit_code_in(worktree, os.path.join(worktree, "sub")))


class TestCopilotPayloads(unittest.TestCase):
    def test_safety_check_blocks_dangerous_command_from_copilot_payload(self):
        payload = json.dumps({"tool_name": "bash", "tool_input": {"command": "rm -rf /"}, "cwd": "/tmp"})
        done = subprocess.run([sys.executable, str(SCRIPT)], input=payload.encode(), capture_output=True)
        self.assertEqual(2, done.returncode)

    def test_safety_check_allows_safe_command_from_copilot_payload(self):
        payload = json.dumps({"tool_name": "bash", "tool_input": {"command": "ls"}, "cwd": "/tmp"})
        done = subprocess.run([sys.executable, str(SCRIPT)], input=payload.encode(), capture_output=True)
        self.assertEqual(0, done.returncode)


if __name__ == "__main__":
    unittest.main()
