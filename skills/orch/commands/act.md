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

## Proof flow

1. Spawn the builder with `--test-cmd` set to the Command line from KIS State. Spawn a reviewer's
   brief with the builder's checkout path; reviewers need no `--test-cmd`.
2. On a `done` notice for a build or review worker, run `orch verify NAME` as one background job
   (the clean test run can take minutes). On `[orch] NAME stopped, no proof`, read the pane and
   re-prompt for the missing proof; do not review yet.
3. When the build verifies, spawn the reviewer. When the review is written, run
   `orch verify REVIEWER --against BUILDER_CHECKOUT`. Findings that do not reproduce go back to
   the reviewer, not the builder.
4. Send the verified findings to the builder as one batch. After the fix, run
   `orch verify BUILDER` again, then `orch verify REVIEWER --against BUILDER_CHECKOUT --want NOT-REPRODUCED`.
5. Merge, then `orch close` both workers. Build and review workers are never reused: spawn fresh
   ones for the next task.
