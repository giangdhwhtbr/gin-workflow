# Team hosts

One row per `team.host`. Open a pull request with the host's command, and set the branch protection and approval reset the row names. Self-hosted Gitea and the CodeCommit approval rule template are in docs/guides/team.md.

| host | CLI | login | open a pull request | branch protection | approvals reset on push |
|---|---|---|---|---|---|
| github | `gh` | `gh auth login` | `gh pr create --fill` | "Require review from Code Owners" | "Dismiss stale pull request approvals" (recommended) |
| gitlab | `glab` | `glab auth login` | `glab mr create --fill` | Premium "Code owner approval" | "Reset approvals on push" (required for `ship`) |
| gitea | `gt` | `gt auth login --host <instance URL>` with `--with-token` or `--oauth` | `gt pr create --fill` | protected branch with required approvals | "Dismiss stale approvals" |
| codecommit | `aws` | `aws configure` or `aws sso login` | `aws codecommit create-pull-request --title <title> --targets repositoryName=<repo>,sourceReference=<branch>` | approval rule template associated with the repository | not a setting: approvals are per revision |

Without team mode, open the pull request with `gh pr create --fill`.
