# Cycle 2 review-fix handoff

Branch: `cycle2`
Date: 2026-10-19
Push: not performed.
KIS: unchanged as instructed.
Live Herdr panes: not opened, closed, or moved. Plugin link state was not changed.

## Fix commits

```text
9e495f9 fix(board): reserve worker identity in narrow layouts
3fbc255 fix(orch): scope adoption ownership to session and pane
2ef0fa4 fix(orch): prune stale pane rows during idempotent adopt
```

## Changes

- Adoption now resolves collisions only within the current Herdr session and checks pane and alias conflicts before mutating the registry. Idempotence requires the same session, owner, alias, and target pane; an active alias change fails clearly.
- Same-session agents can be adopted across workspace IDs. Foreign session targets stay unresolvable through Herdr’s session-scoped lookup.
- Closing an adopted agent retains the safe external-resource early return and releases the pane for a later adoption. New and idempotent adoption successes retry queued delivery under the registry lock; failed prompts leave the queue intact.
- Board layout reserves the state field, separators, up to six owner columns, and up to twenty worker-leaf columns before showing HOST / MODEL. Runtime is omitted if fewer than twelve columns remain and capped to the available width. Long worker names retain their suffix; orphan rows keep their status rank.
- Idempotent adoption removes stale tombstones before returning, keeping at most one active registry row for a session and pane.
- Added regression tests for the eight reviewer findings, including exact 50/60/67 layouts with shared worker prefixes, session collisions, alias consistency, tombstone reuse, retry delivery, and orphan ordering.

## Verification

Command: `./tests/run.sh`
Exit: 0
Result: 107 tests passed in 34.955s. The exact full output follows.

```text
test_blocked_and_orphan_rows_use_distinct_styles_and_markers (test_board.BoardTests.test_blocked_and_orphan_rows_use_distinct_styles_and_markers) ... ok
test_cli_accepts_width_below_40_and_clips_each_line (test_board.BoardTests.test_cli_accepts_width_below_40_and_clips_each_line) ... ok
test_cli_registry_uses_project_orch_agent_hierarchy (test_board.BoardTests.test_cli_registry_uses_project_orch_agent_hierarchy) ... ok
test_cli_renders_cli_generated_cycle2_fixture_with_adopted_closed_and_orphan_rows (test_board.BoardTests.test_cli_renders_cli_generated_cycle2_fixture_with_adopted_closed_and_orphan_rows) ... ok
test_closed_agents_and_gone_orchs_are_not_counted_but_closed_rows_are_dim (test_board.BoardTests.test_closed_agents_and_gone_orchs_are_not_counted_but_closed_rows_are_dim) ... ok
test_crowded_hierarchy_rows_drop_project_and_keep_names_at_100_and_60 (test_board.BoardTests.test_crowded_hierarchy_rows_drop_project_and_keep_names_at_100_and_60) ... ok
test_empty_registry_has_explicit_state_and_footer (test_board.BoardTests.test_empty_registry_has_explicit_state_and_footer) ... ok
test_footer_fits_real_timestamp_at_accepted_widths (test_board.BoardTests.test_footer_fits_real_timestamp_at_accepted_widths) ... ok
test_header_and_rows_share_separator_columns_at_100_with_color (test_board.BoardTests.test_header_and_rows_share_separator_columns_at_100_with_color) ... ok
test_header_and_rows_share_separator_columns_at_60 (test_board.BoardTests.test_header_and_rows_share_separator_columns_at_60) ... ok
test_long_names_truncate_with_one_ellipsis_without_exceeding_width (test_board.BoardTests.test_long_names_truncate_with_one_ellipsis_without_exceeding_width) ... ok
test_long_parent_components_keep_distinct_worker_names_at_60 (test_board.BoardTests.test_long_parent_components_keep_distinct_worker_names_at_60) ... ok
test_manifest_declares_board_action_and_pane_commands (test_board.BoardTests.test_manifest_declares_board_action_and_pane_commands) ... ok
test_narrow_board_exact_rows_at_40_60_and_100_columns (test_board.BoardTests.test_narrow_board_exact_rows_at_40_60_and_100_columns) ... ok
test_no_color_contains_no_ansi_sequences (test_board.BoardTests.test_no_color_contains_no_ansi_sequences) ... ok
test_no_color_environment_disables_terminal_styles (test_board.BoardTests.test_no_color_environment_disables_terminal_styles) ... ok
test_open_action_direction_defaults_right_and_accepts_down (test_board.BoardTests.test_open_action_direction_defaults_right_and_accepts_down) ... ok
test_open_action_rejects_invalid_direction_before_herdr_call (test_board.BoardTests.test_open_action_rejects_invalid_direction_before_herdr_call) ... ok
test_open_action_targets_current_pane_without_changing_plugin_cwd (test_board.BoardTests.test_open_action_targets_current_pane_without_changing_plugin_cwd) ... ok
test_orch_groups_and_projects_have_exactly_one_blank_line_between_them (test_board.BoardTests.test_orch_groups_and_projects_have_exactly_one_blank_line_between_them) ... ok
test_orphan_rows_keep_status_order (test_board.BoardTests.test_orphan_rows_keep_status_order) ... ok
test_q_exits_after_initial_render (test_board.BoardTests.test_q_exits_after_initial_render) ... ok
test_refresh_only_changes_when_registry_mtime_changes (test_board.BoardTests.test_refresh_only_changes_when_registry_mtime_changes) ... ok
test_renderer_fits_60_columns_and_has_narrow_rows (test_board.BoardTests.test_renderer_fits_60_columns_and_has_narrow_rows) ... ok
test_renderer_has_anchored_rows_and_project_queue_counts_at_100 (test_board.BoardTests.test_renderer_has_anchored_rows_and_project_queue_counts_at_100) ... ok
test_renderer_uses_plural_count_labels (test_board.BoardTests.test_renderer_uses_plural_count_labels) ... ok
test_renderer_uses_singular_count_labels (test_board.BoardTests.test_renderer_uses_singular_count_labels) ... ok
test_resize_redraws_at_new_width_without_registry_change (test_board.BoardTests.test_resize_redraws_at_new_width_without_registry_change) ... ok
test_runtime_column_fits_narrow_width_and_smaller_width_degrades (test_board.BoardTests.test_runtime_column_fits_narrow_width_and_smaller_width_degrades) ... ok
test_runtime_reserves_owner_separator_and_worker_leaf_at_50_60_and_67 (test_board.BoardTests.test_runtime_reserves_owner_separator_and_worker_leaf_at_50_60_and_67) ... ok
test_status_glyphs_render_without_legend_or_color_at_60_and_100 (test_board.BoardTests.test_status_glyphs_render_without_legend_or_color_at_60_and_100) ... ok
test_active_adoption_rejects_alias_change_without_rekeying (test_phase1.PhaseOne.test_active_adoption_rejects_alias_change_without_rekeying) ... ok
test_adopt_reads_agent_and_pane_then_lists_and_is_idempotent (test_phase1.PhaseOne.test_adopt_reads_agent_and_pane_then_lists_and_is_idempotent) ... ok
test_adopt_refuses_agent_owned_by_another_live_orch (test_phase1.PhaseOne.test_adopt_refuses_agent_owned_by_another_live_orch) ... ok
test_adopt_rejects_unknown_foreign_and_unregistered (test_phase1.PhaseOne.test_adopt_rejects_unknown_foreign_and_unregistered) ... ok
test_adopted_agent_hook_notice_routes_to_registered_owner (test_phase1.PhaseOne.test_adopted_agent_hook_notice_routes_to_registered_owner) ... ok
test_adopted_close_only_deregisters_even_with_discard (test_phase1.PhaseOne.test_adopted_close_only_deregisters_even_with_discard) ... ok
test_adoption_moves_queue_and_reactivation_does_not_redeliver (test_phase1.PhaseOne.test_adoption_moves_queue_and_reactivation_does_not_redeliver) ... ok
test_adoption_retries_pending_delivery_on_new_and_idempotent_success (test_phase1.PhaseOne.test_adoption_retries_pending_delivery_on_new_and_idempotent_success) ... ok
test_alias_collision_does_not_mask_another_live_pane_owner (test_phase1.PhaseOne.test_alias_collision_does_not_mask_another_live_pane_owner) ... ok
test_cleanup_reservation_blocks_name_replacement (test_phase1.PhaseOne.test_cleanup_reservation_blocks_name_replacement) ... ok
test_cleanup_writer_reservation_blocks_second_writer (test_phase1.PhaseOne.test_cleanup_writer_reservation_blocks_second_writer) ... ok
test_cli_retries_queue_only_when_orch_is_idle_or_done (test_phase1.PhaseOne.test_cli_retries_queue_only_when_orch_is_idle_or_done) ... ok
test_close_after_merge_into_linked_orch (test_phase1.PhaseOne.test_close_after_merge_into_linked_orch) ... ok
test_close_only_created_and_discard_override (test_phase1.PhaseOne.test_close_only_created_and_discard_override) ... ok
test_close_refuses_ignored_paths_without_stopping (test_phase1.PhaseOne.test_close_refuses_ignored_paths_without_stopping) ... ok
test_close_refuses_unmerged_branch (test_phase1.PhaseOne.test_close_refuses_unmerged_branch) ... ok
test_close_retry_rechecks_checkout_before_destructive_calls (test_phase1.PhaseOne.test_close_retry_rechecks_checkout_before_destructive_calls) ... ok
test_close_worktree_preflight_does_not_stop (test_phase1.PhaseOne.test_close_worktree_preflight_does_not_stop) ... ok
test_closed_adopted_pane_can_be_adopted_by_another_owner (test_phase1.PhaseOne.test_closed_adopted_pane_can_be_adopted_by_another_owner) ... ok
test_deregister_marks_gone (test_phase1.PhaseOne.test_deregister_marks_gone) ... ok
test_discard_overrides_close_preflight (test_phase1.PhaseOne.test_discard_overrides_close_preflight) ... ok
test_discard_removes_untracked_and_modified_worktrees_without_force (test_phase1.PhaseOne.test_discard_removes_untracked_and_modified_worktrees_without_force) ... ok
test_duplicate_and_outside_herdr_errors (test_phase1.PhaseOne.test_duplicate_and_outside_herdr_errors) ... ok
test_duplicate_live_herdr_agent_name_refused_exactly (test_phase1.PhaseOne.test_duplicate_live_herdr_agent_name_refused_exactly) ... ok
test_failed_cleanup_keeps_retryable_reservation (test_phase1.PhaseOne.test_failed_cleanup_keeps_retryable_reservation) ... ok
test_failed_delivery_keeps_queue (test_phase1.PhaseOne.test_failed_delivery_keeps_queue) ... ok
test_failed_worktree_rollback_keeps_branch_for_retry (test_phase1.PhaseOne.test_failed_worktree_rollback_keeps_branch_for_retry) ... ok
test_fake_herdr_rejects_worktree_workspace_and_cwd_together (test_phase1.PhaseOne.test_fake_herdr_rejects_worktree_workspace_and_cwd_together) ... ok
test_fixture_git_environment_is_isolated (test_phase1.PhaseOne.test_fixture_git_environment_is_isolated) ... ok
test_foreign_session_orphan_is_not_adopted (test_phase1.PhaseOne.test_foreign_session_orphan_is_not_adopted) ... ok
test_foreign_session_pane_collision_does_not_block_adoption (test_phase1.PhaseOne.test_foreign_session_pane_collision_does_not_block_adoption) ... ok
test_idempotent_adoption_removes_stale_pane_tombstones (test_phase1.PhaseOne.test_idempotent_adoption_removes_stale_pane_tombstones) ... ok
test_linked_worktree_project_resolution (test_phase1.PhaseOne.test_linked_worktree_project_resolution) ... ok
test_list_role_idle_filters (test_phase1.PhaseOne.test_list_role_idle_filters) ... ok
test_liveness_reconcile_marks_missing_orch_gone (test_phase1.PhaseOne.test_liveness_reconcile_marks_missing_orch_gone) ... ok
test_main_writer_and_worktree_writer_reserve_distinct_trees (test_phase1.PhaseOne.test_main_writer_and_worktree_writer_reserve_distinct_trees) ... ok
test_missing_workspace_marks_owner_gone_and_adopts (test_phase1.PhaseOne.test_missing_workspace_marks_owner_gone_and_adopts) ... ok
test_other_workspace_listing_error_does_not_complete_registration (test_phase1.PhaseOne.test_other_workspace_listing_error_does_not_complete_registration) ... ok
test_parallel_writers_same_tree_allow_only_one (test_phase1.PhaseOne.test_parallel_writers_same_tree_allow_only_one) ... ok
test_partial_close_resumes_successful_steps (test_phase1.PhaseOne.test_partial_close_resumes_successful_steps) ... ok
test_python_version_guard (test_phase1.PhaseOne.test_python_version_guard) ... orch: Python 3.11 or newer is required
ok
test_register_board_direction_uses_environment (test_phase1.PhaseOne.test_register_board_direction_uses_environment) ... ok
test_register_reconcile_adopts_queue_and_notices (test_phase1.PhaseOne.test_register_reconcile_adopts_queue_and_notices) ... ok
test_reregister_reactivates_gone_and_adopts (test_phase1.PhaseOne.test_reregister_reactivates_gone_and_adopts) ... ok
test_rollback_stops_when_child_close_fails (test_phase1.PhaseOne.test_rollback_stops_when_child_close_fails) ... ok
test_session_isolates_delivery_reconcile_and_adoption (test_phase1.PhaseOne.test_session_isolates_delivery_reconcile_and_adoption) ... ok
test_spawn_failure_rolls_back_created_resources (test_phase1.PhaseOne.test_spawn_failure_rolls_back_created_resources) ... ok
test_spawn_locations_flags_host_argv_and_role (test_phase1.PhaseOne.test_spawn_locations_flags_host_argv_and_role) ... ok
test_start_sees_durable_starting_reservation_and_created_pane (test_phase1.PhaseOne.test_start_sees_durable_starting_reservation_and_created_pane) ... ok
test_two_registers_idempotence_adoption_and_sessions (test_phase1.PhaseOne.test_two_registers_idempotence_adoption_and_sessions) ... ok
test_unregistered_caller_is_refused (test_phase1.PhaseOne.test_unregistered_caller_is_refused) ... ok
test_worktree_rollback_retains_unmerged_branch_and_cleanup_record (test_phase1.PhaseOne.test_worktree_rollback_retains_unmerged_branch_and_cleanup_record) ... ok
test_worktree_spawn_and_writer_refusal (test_phase1.PhaseOne.test_worktree_spawn_and_writer_refusal) ... ok
test_worktree_start_failure_removes_branch_without_force (test_phase1.PhaseOne.test_worktree_start_failure_removes_branch_without_force) ... ok
test_worktree_writer_then_main_writer_are_independent (test_phase1.PhaseOne.test_worktree_writer_then_main_writer_are_independent) ... ok
test_adoption_coalesces_duplicate_pending_notices_before_delivery (test_phase2.PhaseTwo.test_adoption_coalesces_duplicate_pending_notices_before_delivery) ... ok
test_closed_worker_notice_delivers_to_idle_owner (test_phase2.PhaseTwo.test_closed_worker_notice_delivers_to_idle_owner) ... ok
test_closed_worktree_worker_is_cleaned_up_by_orch_close (test_phase2.PhaseTwo.test_closed_worktree_worker_is_cleaned_up_by_orch_close) ... ok
test_done_idle_flip_queues_no_notice (test_phase2.PhaseTwo.test_done_idle_flip_queues_no_notice) ... ok
test_events_after_close_are_ignored (test_phase2.PhaseTwo.test_events_after_close_are_ignored) ... ok
test_failed_closed_worker_delivery_keeps_queue (test_phase2.PhaseTwo.test_failed_closed_worker_delivery_keeps_queue) ... ok
test_failed_prompt_keeps_queue_and_next_cli_command_delivers (test_phase2.PhaseTwo.test_failed_prompt_keeps_queue_and_next_cli_command_delivers) ... ok
test_fixture_events_cover_provider_and_custom_statuses (test_phase2.PhaseTwo.test_fixture_events_cover_provider_and_custom_statuses) ... ok
test_herdr_lookup_error_does_not_mark_agent_closed (test_phase2.PhaseTwo.test_herdr_lookup_error_does_not_mark_agent_closed) ... ok
test_idle_and_unknown_to_blocked_queue_notice (test_phase2.PhaseTwo.test_idle_and_unknown_to_blocked_queue_notice) ... ok
test_manifest_declares_only_the_two_phase_two_events (test_phase2.PhaseTwo.test_manifest_declares_only_the_two_phase_two_events) ... ok
test_missing_live_agent_is_treated_as_closed (test_phase2.PhaseTwo.test_missing_live_agent_is_treated_as_closed) ... ok
test_notice_is_queued_for_the_owning_orch_only (test_phase2.PhaseTwo.test_notice_is_queued_for_the_owning_orch_only) ... ok
test_orch_close_keeps_queue_and_adoption_delivers (test_phase2.PhaseTwo.test_orch_close_keeps_queue_and_adoption_delivers) ... ok
test_out_of_order_event_uses_live_status (test_phase2.PhaseTwo.test_out_of_order_event_uses_live_status) ... ok
test_parallel_hooks_do_not_lose_notices (test_phase2.PhaseTwo.test_parallel_hooks_do_not_lose_notices) ... ok
test_parent_git_config_hook_is_not_executed (test_phase2.PhaseTwo.test_parent_git_config_hook_is_not_executed) ... ok
test_queue_flushes_as_one_prompt_when_orch_goes_idle (test_phase2.PhaseTwo.test_queue_flushes_as_one_prompt_when_orch_goes_idle) ... ok
test_queue_is_held_while_orch_is_working_or_blocked (test_phase2.PhaseTwo.test_queue_is_held_while_orch_is_working_or_blocked) ... ok
test_queue_notice_coalesces_duplicate_done_and_closed_messages (test_phase2.PhaseTwo.test_queue_notice_coalesces_duplicate_done_and_closed_messages) ... ok
test_repeated_status_queues_one_notice (test_phase2.PhaseTwo.test_repeated_status_queues_one_notice) ... ok

----------------------------------------------------------------------
Ran 107 tests in 34.955s

OK
```

## Mutation checks

Each of the 14 literal mutations made its named test fail. The changed file was restored from saved bytes and verified byte-identical with `cmp` before moving on.

| Guard | Mutation | Test result | Restore |
|---|---|---|---|
| Alias collision guard | Bypassed alias conflict detection for an existing different pane. | `test_alias_collision_does_not_mask_another_live_pane_owner` failed | Byte-identical (`cmp`) |
| Herdr session scope | Allowed agent lookup across session IDs. | `test_adopt_rejects_unknown_foreign_and_unregistered` failed | Byte-identical (`cmp`) |
| Session-scoped pane match | Applied the session prefix only to name matching, allowing a foreign pane collision into the local conflict set. | `test_foreign_session_pane_collision_does_not_block_adoption` failed | Byte-identical (`cmp`) |
| Workspace/session distinction | Reintroduced workspace ID equality as a session check. | `test_adopt_rejects_unknown_foreign_and_unregistered` failed | Byte-identical (`cmp`) |
| Alias consistency | Bypassed rejection of an active adopted agent alias change. | `test_active_adoption_rejects_alias_change_without_rekeying` failed | Byte-identical (`cmp`) |
| Closed adopted tombstone | Stopped treating closed adopted rows as releasable pane ownership. | `test_closed_adopted_pane_can_be_adopted_by_another_owner` failed | Byte-identical (`cmp`) |
| Adopted close safety | Bypassed close’s adopted-agent external-resource early return. | `test_adopted_close_only_deregisters_even_with_discard` failed | Byte-identical (`cmp`) |
| New adoption delivery | Removed pending delivery on the new-adoption success path. | `test_adoption_retries_pending_delivery_on_new_and_idempotent_success` failed | Byte-identical (`cmp`) |
| Idempotent adoption delivery | Removed pending delivery on the idempotent success path. | `test_adoption_retries_pending_delivery_on_new_and_idempotent_success` failed | Byte-identical (`cmp`) |
| Idempotent stale-row cleanup | Removed stale pane tombstone pruning from the idempotent success path. | `test_idempotent_adoption_removes_stale_pane_tombstones` failed | Byte-identical (`cmp`) |
| Orphan status ranking | Forced orphan rows to a fixed rank ahead of status ordering. | `test_orphan_rows_keep_status_order` failed | Byte-identical (`cmp`) |
| Worker leaf reservation | Reduced the reserved worker leaf from 20 to 6 columns. | `test_runtime_reserves_owner_separator_and_worker_leaf_at_50_60_and_67` failed | Byte-identical (`cmp`) |
| Suffix-preserving truncation | Replaced middle truncation with prefix-only truncation. | `test_runtime_reserves_owner_separator_and_worker_leaf_at_50_60_and_67` failed | Byte-identical (`cmp`) |
| Runtime cutoff | Reduced the display threshold from 12 remaining columns to 11. | `test_runtime_column_fits_narrow_width_and_smaller_width_degrades` failed | Byte-identical (`cmp`) |

## Board captures

Generated with `python3 plugin/board.py --once --width <width> --registry tests/fixtures/board-registry-cycle2.json`. The CLI-generated registry includes a closed worker, an orphan, and an adopted agent. Capture time in these outputs: 11:20:40.

### 100 columns

```text
ORCH BOARD · 1 project · 1 orch · 2 agents
----------------------------------------------------------------------------------------------------
STATE              | HIERARCHY PATH                                          | HOST / MODEL         
cycle2-garden · 0 queued notices
○ IDLE             | orch                                                    | claude · Q:0
▶ WORKING          | orch > fictional-adopted-builder                        | codex fictional-model
× CLOSED           | orch > fictional-closed-worker                          | claude

▶ WORKING *        | ORPHAN > fictional-orphan-worker                        | claude
refreshed 11:20:40
```

### 67 columns

```text
ORCH BOARD · 1 project · 1 orch · 2 agents
-------------------------------------------------------------------
STATE       | HIERARCHY PATH                | HOST / MODEL         
cycle2-garden · 0 queued notices
○ IDLE      | orch                          | claude · Q:0
▶ WORKING   | orch > fictional-a…ed-builder | codex fictional-model
× CLOSED    | orch > fictional-c…sed-worker | claude

▶ WORKING * | ORPHAN > fictional-…an-worker | claude
refreshed 11:20:40
```

### 60 columns

```text
ORCH BOARD · 1 project · 1 orch · 2 agents
------------------------------------------------------------
STATE       | HIERARCHY PATH                | HOST / MODEL  
cycle2-garden · 0 queued notices
○ IDLE      | orch                          | claude · Q:0
▶ WORKING   | orch > fictional-a…ed-builder | codex fiction…
× CLOSED    | orch > fictional-c…sed-worker | claude

▶ WORKING * | ORPHAN > fictional-…an-worker | claude
refreshed 11:20:40
```

### 50 columns

```text
ORCH BOARD · 1 project · 1 orch · 2 agents
--------------------------------------------------
STATE       | HIERARCHY PATH                      
cycle2-garden · 0 queued notices
○ IDLE      | orch                                
▶ WORKING   | orch > fictional-adopted-builder    
× CLOSED    | orch > fictional-closed-worker      

▶ WORKING * | ORPHAN > fictional-orphan-worker    
refreshed 11:20:40
```

## Open questions and owner live check

- Herdr may omit the model field; adoption stores an empty model in that case. No implementation question remains.
- Live behavior remains unverified because this brief prohibits changing owner panes. No real agent was adopted.
- Owner check in the live Herdr session: run `herdr agent get <agent-name-or-pane>`, adopt an existing agent with `orch adopt <agent-name-or-pane> --role review`, and verify `orch list` plus its board row. Then run `orch close <name> --discard` and confirm the external pane remains open. Also confirm that a target from another Herdr session cannot be resolved for adoption.

## Full-screen board overlay action

Branch: `cycle2`
Date: 2026-10-19
History: commit `890e254` was not rewritten.
Push: not performed.
KIS: unchanged, as this brief instructed.
Live Herdr panes: not opened, closed, or moved. Plugin link state and Herdr config were not changed.

### Action and overlay behavior

Added the `board-full` pane action titled `Orch board, full screen`. It calls the existing `board.py --open` path with `--placement overlay`. The original `board` action still uses the split placement and `ORCH_BOARD_DIRECTION` remains limited to that split.

Checked `herdr 0.9.5`, `herdr plugin pane open --help`, `herdr plugin --help`, and `herdr plugin pane --help` on 2026-10-19. Local help lists `overlay` as an accepted placement but does not describe size, focus, or process-exit behavior. Herdr's [plugin CLI docs](https://herdr.dev/docs/cli-reference/) describe overlay as a temporary zoomed overlay over the active pane; the [socket API docs](https://herdr.dev/docs/socket-api/) say overlay panes behave as normal Herdr panes and can be focused or closed through plugin pane APIs. The docs do not guarantee that a plugin overlay closes when its command exits. They explicitly describe command-exit closure for `popup`, which is a different placement. The board's `q` exits its process, but automatic overlay closure on that exit remains unverified. No cleanup workaround was added; the owner must verify this behavior in the live check.

### Exact-row captures

Captured from `tests/fixtures/board-registry-cycle2.json` with `NO_COLOR=1`, timestamp fixed at `12:34:56`. The renderer emits 10 lines total at both widths, so it fits within 43 rows and 30 rows. Rows below are exact; the wider capture gives the hierarchy path 110 columns while retaining the 26-column runtime field.

160×43:

```text
○ IDLE             | orch                                                                                                                | claude · Q:0
▶ WORKING          | orch > fictional-adopted-builder                                                                                    | codex fictional-model
× CLOSED           | orch > fictional-closed-worker                                                                                      | claude
▶ WORKING *        | ORPHAN > fictional-orphan-worker                                                                                    | claude
```

100×30:

```text
○ IDLE             | orch                                                    | claude · Q:0
▶ WORKING          | orch > fictional-adopted-builder                        | codex fictional-model
× CLOSED           | orch > fictional-closed-worker                          | claude
▶ WORKING *        | ORPHAN > fictional-orphan-worker                        | claude
```

Reproduce with:

```sh
NO_COLOR=1 python3 plugin/board.py --once --width 160 --registry tests/fixtures/board-registry-cycle2.json
NO_COLOR=1 python3 plugin/board.py --once --width 100 --registry tests/fixtures/board-registry-cycle2.json
```

### Tests and mutations

- `test_manifest_declares_board_action_and_pane_commands` asserts the exact `board-full` manifest entry and keeps the split entry unchanged.
- `test_full_board_open_action_uses_overlay_without_split_arguments` asserts exact Herdr argv including `--plugin orch`, `--entrypoint board`, and `--placement overlay`; it also proves an invalid split direction does not affect the overlay action.
- `test_full_board_exact_rows_at_160_and_100_columns` pins each fixture row and enforces the requested width limit.
- Focused tests passed: manifest, split argv, overlay argv, and 160/100 exact rows (4 tests).
- Mutation check: changed the `board-full` manifest command from `overlay` to `split`; `test_manifest_declares_board_action_and_pane_commands` failed. Restored the manifest and verified it byte-identical with `cmp`.
- Mutation check: changed the overlay argv construction from the requested placement to `split`; `test_full_board_open_action_uses_overlay_without_split_arguments` failed. Restored `board.py` and verified it byte-identical with `cmp`.
- `./tests/run.sh` passed: 109 tests in 37.673s.

### Owner live check

From Herdr after the updated plugin is available, invoke the action:

```sh
herdr plugin action invoke board-full --plugin orch
```

Confirm the board fills the active pane as an overlay, press `q`, and confirm whether the overlay closes and focus/zoom return. Then bind `prefix+b` in the owner's `config.toml` to action `orch.board-full` and verify that binding. The default `prefix+b` binding may need to be replaced by the owner.
