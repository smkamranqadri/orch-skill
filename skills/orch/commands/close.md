---
description: Synchronize KIS, review cleanup candidates, and deregister this orch.
argument-hint: [optional summary]
---

# Orch Close

Close finished workers, run `kis:sync`, and run `/lore:retro` if lore is installed. List merged
branches and worktrees; ask the owner before each removal and use `orch close` only after approval.
Then run `orch deregister`. Report remaining workers, branches, worktrees, and queues.
