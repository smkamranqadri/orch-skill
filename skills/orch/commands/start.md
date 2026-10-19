---
description: Initialize KIS if needed, register this orch, and recover project state.
argument-hint: [optional task]
---

# Orch Start

If KIS is absent, install it and run `kis:init`; do not offer a decline path:

```sh
curl -fsSL https://raw.githubusercontent.com/smkamranqadri/kis-skill/main/bootstrap.sh | bash -s -- install --repo https://github.com/smkamranqadri/kis-skill.git
```

Then run `kis:start`, register with `orch register`, adopt orphaned project agents, and open the
board if registration did not. Report branch, task, blocker, proof, and next action. Do not
implement work in this command.
