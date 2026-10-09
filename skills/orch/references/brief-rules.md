# Standing rules for every brief

Every brief an orchestrator writes carries these, by pointer when lore notes are present
(coordination rules 2, 10, 11, 12) and in full when it is not. They exist because each one was
paid for by a broken machine, a lost edit or a wasted run.

Resources and safety

- Check free disk before a build or a download; stop and say so under a few gigabytes.
- Shared daemons (Gradle, Docker, databases, package caches) belong to everyone on the machine:
  isolate yours (for Gradle, `GRADLE_OPTS=-Dorg.gradle.daemon=false`), never kill or restart them.
- One device or emulator per agent. No machine-wide kills, restarts or reboots.
- No CPU stress tests, benchmarks or load runs while the user may be using the machine.
- Start in the default permission mode; the user switches it. Never pass an auto mode yourself.

Files and git

- Edit only inside your own worktree. Never run `git checkout`, `git reset` or `git clean` in
  the main checkout, and never move work between branches with stash.
- Format only the files you changed: never pass a directory to a formatter, and read what a
  lint script does before running it (it may be `eslint --fix`).
- Commit only when your brief says so, with explicit paths staged and the message read back.

Output and proof

- Send a long job's full output to a log file and read the file; never pipe it through `tail`.
- Proof is real command output, a screenshot of your own build, or a failing reproduction that
  no longer fails. Say what was and was not verified in the same sentence as the result.
- Write the report and the handoff to the files the brief names and reply with their paths and
  a short summary. Keep the handoff current enough that a fresh agent could resume from it.

When stopped by a usage limit

- A resume brief means: work alone, no sub-agents, continue from the handoff.
