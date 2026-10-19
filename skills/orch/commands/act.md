---
description: Delegate an approved KIS plan to workers and integrate verified results.
argument-hint: [task or scope]
---

# Orch Act

Run `kis:act` through workers only after the owner approves the plan. For each task, reuse an idle
worker of the needed role or propose a spawn from the matrix. Wait for approval when required,
send a brief file with a short pointer prompt, wait for its notice, then review with a different
model. Batch fixes, verify proof yourself, and merge only after review and verification pass.
Never write product code in the orch session. Follow the prompt and review-round limits.
