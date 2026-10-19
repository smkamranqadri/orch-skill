# Security

## Reporting a problem

Please report vulnerabilities privately through GitHub's
[security advisories](https://github.com/smkamranqadri/orch-skill/security/advisories/new), not
in a public issue.

## What orch touches

- **Reads:** Herdr pane and agent state needed to maintain the orch registry and route notices.
- **Writes:** `${XDG_STATE_HOME:-~/.local/state}/orch/registry.json`, installed skill and command
  links, the `~/.local/bin/orch` link, and Herdr's plugin registration through `herdr plugin`.
- **Runs:** Herdr CLI commands for pane, agent, workspace, and worktree operations. Worktree
  cleanup is guarded by merge and cleanliness checks unless an explicit discard option is used.
- **Sends:** queued worker status notices to the owning orch through Herdr's agent prompt command.

orch has no network service of its own. A release install uses GitHub to fetch the source and
Herdr's plugin installer. The installer does not edit Herdr's keybinding config; the optional
`prefix+b` snippet is printed for the user to add manually.

## Safeguards

- Registry changes are locked and scoped by Herdr session.
- Installer links and skill paths are checked before writing. A foreign skill directory or file
  is preserved and the operation stops.
- Automatic notices are capped; a paused orch stays paused until an explicit resume.
- Tests use temporary homes and fake Herdr commands.
