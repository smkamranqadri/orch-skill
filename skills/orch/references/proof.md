## Proof rules (added by `orch spawn`)

Your work is only handed off with proof. When your turn ends without it, the orch is told you
stopped with no proof, not that you are done. Everything below goes in your proof directory:

    {proof_dir}

It is git-excluded, so it never enters the diff or the tree fingerprint. Write there by absolute
path, whatever your shell's cwd is. Do not commit anything. The orch checks the proof with
`orch verify`, so write only what is true.
<!-- role:build -->

### Builder

Test command (the one the orch will run clean): `{test_cmd}`

1. Finish every edit. After the last edit, run the final test run exactly as below, with `<n>` the
   run number (`1`, then `2` after any later edit):

       { {test_cmd} ; } > {proof_dir_q}/run-<n>.log 2>&1; echo "exit=$?" >> {proof_dir_q}/run-<n>.log

   The last line of the log must be `exit=0`. Read the whole log, never only its tail.
2. Right after that run, with no edit in between, print the tree fingerprint from your checkout:

       orch fingerprint

3. Mutation-check every new guard: save the original file, break the guard with a literal edit,
   run its test and watch that specific assertion fail, restore from the saved copy and prove the
   file byte-identical with `cmp`. Append one line per check to `{proof_dir}/mutations.log`:

       <guard> | <test file> | tripped=True|False | restored byte-identical=True|False

   Any other nonblank line makes the log malformed. The latest line per guard decides, so a fixed
   guard gets a new line. Mutating code changes the tree: do the final run and the fingerprint
   after the last mutation check.
4. Write `{proof_dir}/handoff.md` with these fields, one per line as `name: value`. The last
   occurrence of a field wins, so a fix round appends new lines:

       run_log: <absolute path of the run log>
       run_sha256: <sha256 of that log file>
       tree_fingerprint: <output of orch fingerprint>
       mutations_log: <absolute path of mutations.log>
       guards: <comma-separated guard names, or none>

   Add the rest of your handoff (files changed, what it does, what you did not verify) below them.
   Any edit after the fingerprint needs a new final run, fingerprint and handoff.
<!-- role:review -->

### Reviewer

You review the builder's checkout named in your brief. Do not edit it.

1. Write `{proof_dir}/review.md` with a `findings:` line, comma-separated IDs (`F1, F2`) or
   `none`, then the findings. A finding you cannot reproduce by script is marked MANUAL and needs
   a one-sentence reason on its own line: `F2 manual: <reason>`.
2. Write `{proof_dir}/repro.sh`, executable. It takes the absolute checkout path as `$1` and is
   run with that checkout as its cwd. For each finding it prints, in this order:

       F<n> expected=<what should happen> observed=<what happens>
       F<n> REPRODUCED | NOT-REPRODUCED | MANUAL

   It exits 0, only reads the checkout, keeps temp data outside it, uses no model and no network,
   and finishes in under two minutes.
3. Run it against the checkout yourself before you finish. Every non-MANUAL finding must print
   `REPRODUCED` against the tree you reviewed. Fix the script or drop the finding otherwise.
