# Design workflow: two paths, one review

Any screen a person will see is designed and approved before its code (preference 1). The
design stream is the first stream of a feature; implementation briefs point at the approved
exports, never at prose (coordination rule 3). This reference says how, with and without pen.dev,
and what the user gets to review. The design brief points here.

## Which path

At the start of a design stream the orchestrator checks for pen.dev: the Pencil MCP tools are in
the session, or the `pen` CLI answers `pen --version`, or `/Applications/Pen.app` exists.

- **Present**: the Pencil path below.
- **Absent**: ask the user, once, with a recommendation: install pen.dev (then the Pencil path),
  or skip the design step for this task (the agent builds from the written spec and the real
  screens are reviewed after, with the same review page built from screenshots of the build).
  Nothing else is invented: no HTML mockups, no wireframes, no other tool unless the user names one.

## The Pencil path

1. The design agent (the `designer` sub-agent, or a pane agent on Opus for new design and Sonnet
   for edits, preference 29) reads `Gotchas: Pencil MCP` first when the lessons space is present.
   Every screen group gets a desktop frame and a phone frame at 390 wide; copy is true to what the
   product does and carries no placeholders (preferences 1 and 2).
2. Frames are named `<Layout> · <state>` (`Desktop 1280 · editor`, `Viewport 390 × 844 · editor`).
   Before frames come from a read-only snapshot of the real app, carried unchanged into the after
   frames (the last tartib round fell short of this: its before frames were reconstructions, and
   its handoff said so; the rule stands). Superseded frames are renamed `ARCHIVE …`, never exported over an approved image.
3. Exports go to `<round dir>/exports/<frameId>.png` at scale 1, in a separate call from the
   edits, at most about five frames per call, and each one is opened and checked (size, bytes per
   pixel, matches the node tree). The .pen file is saved after every finished item and the save
   is proved by mtime and `git status`.
4. The agent writes three small JSON files beside the exports, in the shapes
   `scripts/design-pages.py` documents: `inventory.json` (every frame: id, name, size, which one
   starts the prototype), `links.json` (hotspots: the bounds of each button or link that leads to
   another frame, in frame pixels, taken from Pencil's node bounds relative to the frame), and
   `review.json` (only the screens this round changed or added: one sentence on what changed and
   why, the user's earlier words on that screen, before and after images for desktop and phone,
   and the ids to review first).

The round dir is `.orch/<agent>/round-<n>/`, next to the agent's brief.

## The two pages, every round

`python3 ~/.agents/skills/orch/scripts/design-pages.py check <dir>`, then `review <dir>` and
`prototype <dir>`. Both are local HTML files that open from disk; nothing is published unless the
user is away from the machine and asks for a link (coordination rule 30).

- **review.html** is the round's review (preferences 7 and 8): only the changed screens, each
  with its id, one sentence, the user's feedback above it, before and after side by side with the
  phone next to the desktop, and a "review these first" list at the top. A module's first round
  shows every screen once; later rounds show only what changed. The user answers in chat by id:
  "03 approved", "05 needs change: the counter is too small".
- **prototype.html** is the whole app as it stands, as far as the inventory reaches: every
  exported frame listed by desktop and phone, the current frame shown with clickable regions from `links.json`, back and hotspot
  toggles, and a hash per frame so a link can open any screen. It is rebuilt every round from the
  full inventory, so the user can walk the entire app at once whenever they want, not only the
  changed screens. `prototype.html?hot#<frameId>` shows the hotspots, which is how the agent
  proves placement: render it headless and look at the picture before reporting. The inventory
  must cover every frame the user should be able to reach, across .pen files when a module has
  more than one, and the previous round's frames stay in it until the user drops them:
  `check <dir> --previous <last round dir>` names any frame that was reachable last round and
  is not now.

## Reporting a round

The design agent's report names the round dir, the two pages, the ids it wants reviewed first,
and one plain sentence per changed frame. The orchestrator opens the two pages itself (headless
render of `review.html` and of `prototype.html?hot` for two frames), checks `design-pages.py
check` is clean, and only then tells the user the round is ready, in one line with the two
paths. After the user answers, the next round's `review.json` carries their words into the
`feedback` field of each screen they spoke about.

## Approval and after

A module's screens are approved once, on one review page that shows all of them; a revision shows
only the changed screens (preference 8). Approval is the user's words in chat ("all approved",
or per id). The orchestrator records it in the ledger's Open decisions and, with KIS, in the
plan. Implementation briefs then point at `exports/<frameId>.png` of the approved frames and at
`prototype.html` for flow, never at prose descriptions of the design.
