# orch-skill

Public source repo (`smkamranqadri/orch-skill`, MIT) for **orch**: an agent skill plus a Herdr
plugin, both named `orch` (plugin id `orch`), for building with many coding agents at once.
Anyone can use it, with or without KIS or lore installed.

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
- Herdr 0.9.5 on the owner's machine. Plugins are a `herdr-plugin.toml` manifest with actions and
  panes; event hooks receive `HERDR_PLUGIN_EVENT` (`pane.agent_status_changed`, `pane.closed`)
  and `HERDR_PLUGIN_EVENT_JSON`. Keybindings live in Herdr's `config.toml`, not the manifest.
- Report back is push only: the plugin delivers to orch, orch never polls.
- Keep it small. 0.12.2 grew too heavy (ledger, watcher process, gate, usage reader, handoff).

## Release conventions

Installer and public release follow the sibling repo `../lore-skill`: `bootstrap.sh` curl install
plus `scripts/install-skill.sh`, README with hero image and badges, CHANGELOG, CONTRIBUTING,
SECURITY, LICENSE, GitHub Actions test workflow. Read that repo when building any of these.

## History

`archive/` holds orch 0.12.2 and its old KIS memory, frozen at `613aa67`. Reuse code from it only when chosen. The 0.12.2 install and its test home
were removed from this machine on 2026-10-18.
