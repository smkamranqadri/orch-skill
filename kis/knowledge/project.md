# orch-skill

Public source repo (`smkamranqadri/orch-skill`, MIT) for **orch**: an agent skill plus a Herdr
plugin, both named `orch` (plugin id `orch`), for building with many coding agents at once.
Anyone can use it. KIS is required (orch installs it into a repo that lacks it:
`curl -fsSL https://raw.githubusercontent.com/smkamranqadri/kis-skill/main/bootstrap.sh | bash -s
-- install --repo https://github.com/smkamranqadri/kis-skill.git`, run in the project). lore is
optional.

- **Skill:** the main agent reads it to become the orchestrator: how to act as orch and the
  plugin's API.
- **Plugin:** starts agents in Herdr, records them, watches them, pushes notices to the owning
  orch, and shows the board.

## Model

Many projects run at once; each project can have several orchs; each orch starts agents on any
host. The plugin keeps the registry project -> orch -> agent and routes each agent's notice to the
orch that started it.

## Stack and constraints

- Python 3 standard library only; Linux and macOS (Herdr's platforms).
- Herdr 0.9.5 on the owner's machine. Plugins are a `herdr-plugin.toml` manifest with
  `[[actions]]`, `[[panes]]` and `[[events]]`; event hooks receive `HERDR_PLUGIN_EVENT`
  (`pane.agent_status_changed`, `pane.closed`) and `HERDR_PLUGIN_EVENT_JSON`. Keybindings live in
  Herdr's `config.toml`, not the manifest. `herdr plugin install` takes a GitHub repo subdir.
- Herdr API facts the design rests on: plugin actions take no arguments (so orch's API is a CLI);
  `herdr worktree create --branch --base --path` makes a worktree workspace; `herdr agent start
  --kind --pane` needs a pane at a shell prompt; `herdr agent prompt` refuses a `blocked` agent;
  statuses are idle, working, blocked, done, unknown; `herdr plugin pane open --plugin
  --entrypoint --placement` opens a plugin pane. Agent names are unique per Herdr server.
- Report back is push only: the plugin delivers to orch, orch never polls.
- Keep it small. 0.12.2 grew too heavy (ledger, watcher process, gate, usage reader, handoff).

## Release conventions

Installer and public release follow the sibling repo `../lore-skill`: `bootstrap.sh` curl install
plus `scripts/install-skill.sh`, README with hero image and badges, CHANGELOG, CONTRIBUTING,
SECURITY, LICENSE, GitHub Actions test workflow. Read that repo when building any of these.

## History

`archive/` holds orch 0.12.2 and its old KIS memory, frozen at `613aa67`. Reuse code from it only when chosen. The 0.12.2 install and its test home
were removed from this machine on 2026-10-18.

## Agents for this repo (owner, 2026-10-18)

Start every agent at medium effort or lower; raise to high only when a result is not good.
Reuse agents across tasks instead of starting new ones (each start costs about 110k tokens).

| Job | First choice | Alternative |
| --- | --- | --- |
| Orch | Claude Sonnet 5.5 medium | Codex gpt-6.1-sol low or medium |
| Design, plan | Claude Opus 5.5 medium | Codex gpt-6.1-sol medium |
| Build | Claude Sonnet 5.5 medium | Codex gpt-6-luna medium for mechanical briefs |
| Review | a different model from the builder: Opus 5.5 medium on Sonnet's work | Codex gpt-6.1-sol medium |
| Explore | Claude Haiku 5.5 low | Codex gpt-6-luna low |
| Test runs, repetitive commands | no agent: `herdr pane run` in a plain pane | |

These seed the owner's matrix when `/orch:model` exists (phase 5).
