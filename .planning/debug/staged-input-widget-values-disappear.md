---
status: awaiting_human_verify
trigger: "After commit 39a6806 added staged analysis inputs and an explicit Run analysis button, changing a value in the voyage portfolio data_editor or the left sidebar still causes a small Streamlit rerun. Table cell edits can disappear/reset, forcing the user to enter the same value several times before it sticks. Find and fix this UI-state regression while preserving the explicit Run analysis behavior."
created: 2026-08-10T16:22:09.5980618+03:00
updated: 2026-08-10T18:03:00+03:00
---

## Current Focus

hypothesis: verified in automated coverage — immutable editor sources keep Streamlit element IDs stable across ordinary edits, and on_change callbacks persist events before rerun
test: user rapidly edits multiple cells in both tables, interleaves an unrelated sidebar change and a sidebar fuel-price change, then presses Run analysis
expecting: every table value sticks on first entry; ordinary refreshes do not recreate either editor; the fuel-price sidebar event safely rebases only the fuel editor from the complete draft; results stay unchanged before Run and update afterward
next_action: await human verification in the real browser workflow that previously required repeated entry

## Symptoms

expected: A sidebar or voyage-table edit is accepted once, remains visible as a pending draft, and does not run the expensive optimizer. Multiple draft edits can be made quickly, then all are applied by ▶ Run analysis.
actual: Each edit triggers a small automatic refresh; table values sometimes disappear/revert, requiring repeated entry before acceptance.
errors: No exception reported; incorrect widget/session-state behavior.
reproduction: On current main at commit 39a6806, edit a numeric cell in Voyage Portfolio or change a sidebar input. Observe rerun and whether the draft cell persists. Repeat across fuel/segment editor and sidebar fuel-price synchronization.
started: Began with the staged Run analysis implementation in commit 39a6806.

## Eliminated

- hypothesis: Stable-key segment_editor edits are lost on the following unrelated sidebar rerun because init_state sanitizes and reassigns segments_df.
  evidence: Minimal AppTest changed Annual trips from 1 to 77; the draft remained 77 after a later EUA sidebar rerun while the applied snapshot remained 1. The raw edited_rows delta was consumed/cleared, but the sanitized backing DataFrame preserved it.
  timestamp: 2026-08-10T16:31:09.2053457+03:00

- hypothesis: The old sidebar fuel-price value deterministically overwrites a just-entered fuel-table price on the next sequential rerun.
  evidence: Minimal AppTest changed HSFO Price_EUR_t from 470 to 555; after an unrelated sidebar rerun fuels_df remained 555, sidebar_price_HSFO synchronized to 555, the applied snapshot stayed 470, and the editor revision stayed 0.
  timestamp: 2026-08-10T16:35:27.7500013+03:00

## Evidence

- timestamp: 2026-08-10T16:22:53.5886174+03:00
  checked: .planning/debug/knowledge-base.md
  found: No project debug knowledge base exists.
  implication: There is no known-pattern candidate to prioritize.

- timestamp: 2026-08-10T16:22:53.5886174+03:00
  checked: git status and commit 39a6806
  found: Worktree was clean apart from this new debug record; commit 39a6806 changed app.py and tests/test_strategy_selection_ui.py, introducing the analysis snapshot plus Run button while retaining rerun-driven widget updates.
  implication: The regression is tightly time-correlated with the staged-input state-flow change and can be investigated without disentangling unrelated local edits.

- timestamp: 2026-08-10T16:22:53.5886174+03:00
  checked: widget-state references in app.py
  found: Sidebar prices write into fuels_df and increment _fuel_editor_revision; the fuel editor key embeds that revision; both editors then overwrite fuels_df/segments_df from their return values on every run; _analysis_snapshot is updated only initially or when Run is clicked.
  implication: Draft/applied separation exists for calculations, but draft widget identity and backing state still have multiple writers during automatic reruns.

- timestamp: 2026-08-10T16:24:34.6384535+03:00
  checked: complete init_state and staged UI control block
  found: init_state sanitizes and reassigns fuels_df and segments_df before widget construction on every run. Sidebar fuel-price changes additionally increment the fuel editor key before its construction. The segment editor uses a stable key, and both editor return values are sanitized and written back immediately.
  implication: A data-editor delta is being layered onto externally rewritten widget data during the same rerun, violating single-owner state discipline; sidebar synchronization also guarantees a brand-new fuel-editor widget exactly when a sidebar price changes.

- timestamp: 2026-08-10T16:24:34.6384535+03:00
  checked: initial unittest invocation
  found: Module-style invocation failed because tests is not an importable package.
  implication: Baseline must be run by test-file path; this does not bear on the product defect.

- timestamp: 2026-08-10T16:26:10.6060928+03:00
  checked: installed Streamlit test element implementation
  found: Streamlit 1.41.1 exposes data_editor as a read-only Dataframe element in AppTest; editor changes must be simulated through the widget's edited_rows session-state payload, matching the existing test's approach.
  implication: A controlled session-state probe can reproduce the rerun lifecycle even though AppTest has no data_editor.set_value helper.

- timestamp: 2026-08-10T16:26:10.6060928+03:00
  checked: test-file invocation environment
  found: Direct execution sets tests as the import root, so AppTest cannot import regulatory_costs; the default OS temp cleanup is also sandbox-blocked.
  implication: Verification needs PYTHONPATH set to the repository and TEMP/TMP pointed to a workspace-local directory; these are harness issues, not application failures.

- timestamp: 2026-08-10T16:29:34.9293437+03:00
  checked: first controlled AppTest probe on the default portfolio
  found: The initial app calculation exceeded AppTest's 120-second timeout before any state transition was exercised.
  implication: This probe is confounded by the intentionally large default strategy search; using a minimal prefilled scenario isolates widget persistence and is required for a useful experiment.

- timestamp: 2026-08-10T16:31:09.2053457+03:00
  checked: minimal segment_editor AppTest lifecycle
  found: Annual trips changed from 1 to 77 on the first editor rerun and remained 77 after an unrelated EUA sidebar rerun; _analysis_snapshot stayed at 1, and Streamlit cleared edited_rows after incorporating it into the new base.
  implication: Stable-key segment edits and draft/applied separation work in isolation. The reset requires the bidirectional fuel-price synchronization/key-revision path or another distinct trigger.

- timestamp: 2026-08-10T16:35:27.7500013+03:00
  checked: minimal fuel_editor AppTest lifecycle
  found: A sequential table-price edit persisted and remained draft-only, but synchronization relied on Streamlit recreating/reconciling the earlier sidebar widget from its changed default rather than explicit application state.
  implication: The failure is timing-sensitive rather than a deterministic snapshot overwrite; sequential AppTest does not model a second browser edit arriving while the prior full rerun rebuilds the widget tree.

- timestamp: 2026-08-10T16:35:27.7500013+03:00
  checked: Streamlit execution-flow and widget-lifecycle documentation
  found: Non-form widgets trigger script reruns; callbacks run before the rerun; widgets retain state only while identity is stable; changing a key deliberately creates a new widget; permanent state should be separate from temporary widget state and copied explicitly before construction.
  implication: The revision-derived editor key plus implicit bidirectional default reconciliation is incompatible with robust rapid staging. Stable keys and explicit pre-construction synchronization directly address the reported reset window while preserving analysis snapshot gating.

- timestamp: 2026-08-10T16:40:46.6623729+03:00
  checked: initial fix verification
  found: git diff --check and py_compile passed; focused AppTest passed a 45.6-second sequence covering segment, general sidebar, fuel-table, sidebar fuel-price, pre-Run, and post-Run state.
  implication: The basic fix works, but a stale queued table price could still beat an immediately subsequent sidebar price event unless callback order explicitly gives the newest user event precedence; that edge case was added before final verification.

- timestamp: 2026-08-10T16:42:54.7025979+03:00
  checked: final focused AppTest after latest-event callback
  found: The 63.1-second persistence test passed. Segment editor, general sidebar, fuel editor, queued table-to-sidebar sync, immediately newer sidebar fuel-price edit, pre-Run snapshot immutability, and post-Run application all matched expectations.
  implication: Automated reproduction coverage verifies first-entry persistence and explicit Run semantics, including the highest-risk cross-widget ordering.

- timestamp: 2026-08-10T16:42:54.7025979+03:00
  checked: static and adjacent regression checks
  found: git diff --check and py_compile passed; all 8 tests in tests/test_regulatory_costs.py passed.
  implication: The fix is syntactically valid, whitespace-clean, and did not regress the adjacent regulatory cost engine.

- timestamp: 2026-08-10T16:50:30+03:00
  checked: existing strategy-selection Streamlit suite after the persistence fix
  found: The pooling workflow test passed, but a later selector-only rerun timed out because an explicit Run in another AppTest globally cleared evaluate_strategies for every session. The cache key already includes all applied inputs.
  implication: Global cache invalidation was unnecessary and could make an unrelated session perform the full optimizer again. It was removed; changed snapshots still produce distinct cache keys and recalculate normally.

- timestamp: 2026-08-10T17:05:00+03:00
  checked: human verification after the first persistence fix
  found: The browser behavior improved, but table values still disappear on some small refreshes and may require multiple attempts before they stick.
  implication: Stable keys and sidebar/table precedence removed one reset mechanism but did not close the event-to-durable-draft timing window; the session returns to investigation.

- timestamp: 2026-08-10T17:12:00+03:00
  checked: installed Streamlit 1.41.1 data_editor implementation
  found: data_editor supports on_change, but compute_and_register_element_id includes the serialized Arrow dataframe bytes in the widget identity in addition to the user key. The app currently supplies fuels_df/segments_df after each prior edit as the next data argument.
  implication: The editors are recreated after every edit because their source bytes change. This directly explains why stable explicit keys improved but did not eliminate real-browser resets; callback timing alone cannot make a widget with changing identity stable.

- timestamp: 2026-08-10T17:19:00+03:00
  checked: minimal AppTest editor protobuf IDs across sequential table events
  found: Initial IDs were fuel e1ce64... and segment 9311ba.... The segment-edit rerun still rendered the old source, but the following fuel-edit rerun changed the segment ID to 077145... while its explicit key remained segment_editor. This is the exact one-rerun-late recreation predicted by the source-hash hypothesis.
  implication: Root cause is confirmed with direct runtime evidence. The editor source must remain byte-stable during ordinary cell edits; intentional scenario/reset/schema changes may replace it explicitly.

- timestamp: 2026-08-10T17:31:00+03:00
  checked: first focused verification with immutable editor sources
  found: Editor IDs stayed stable through the first segment edit, and segments_df became 77 on that run. On the subsequent synthetic AppTest sidebar event, segments_df returned to 1 because AppTest had cleared the manually injected edited_rows payload instead of resending browser widget state.
  implication: The identity fix works, but the test injection does not yet model persistent frontend delta. Inspect post-run state before choosing between explicit callback persistence and a more faithful test sequence.

- timestamp: 2026-08-10T17:37:00+03:00
  checked: post-run data-editor session state after synthetic segment edit
  found: The segment_editor payload still contained edited_rows={0: {Annual trips: 77}} and the protobuf ID remained 9311ba... immediately after the editor run. AppTest drops that non-addressable dataframe-widget payload only when a different test widget builds its next synthetic state message.
  implication: Immutable source behavior matches browser state retention. Added on_change callbacks to durably persist real editor events before rerun and guarded ordinary reruns from replacing the durable draft when no editor delta is present.

- timestamp: 2026-08-10T17:42:00+03:00
  checked: focused verification of sidebar price precedence with stable editor source
  found: Streamlit raised StreamlitValueAssignmentNotAllowedError when the sidebar callback assigned edited_rows to the existing data_editor session-state key. Data-editor widget values cannot be set programmatically.
  implication: Eliminate that unsupported synchronization method. A sidebar fuel-price event must explicitly rebase the immutable fuel source from the already durable complete draft and use a new revision key; this is safe and intentional, unlike recreation after every table edit.

- timestamp: 2026-08-10T17:52:00+03:00
  checked: final focused stable-source AppTest
  found: The complete persistence/Run test passed in 9.1 seconds. Both editor IDs remained unchanged through segment edit, unrelated sidebar edit, two fuel-table edits, and table-to-sidebar synchronization. A sidebar fuel-price edit performed one intentional fuel-editor rebase while preserving the segment ID and all draft values; the rebased IDs then remained stable through Run.
  implication: The runtime identity regression is fixed in automated coverage, including durable event callbacks, cross-widget price precedence, and explicit analysis snapshot gating.

- timestamp: 2026-08-10T17:55:00+03:00
  checked: static validation and regulatory unit suite
  found: python -m py_compile app.py and git diff --check passed; all 8 regulatory cost tests passed.
  implication: The stable-source/callback changes are syntactically valid, whitespace-clean, and preserve the adjacent regulatory calculation engine.

- timestamp: 2026-08-10T17:59:00+03:00
  checked: adjacent strategy-selection Streamlit suite
  found: Both strategy-selection UI tests passed in 30.5 seconds.
  implication: Stable editor sources and callback persistence did not regress the selector/pooling workflows or explicit Run behavior covered by the adjacent UI suite.

- timestamp: 2026-08-10T18:03:00+03:00
  checked: final diff and worktree scope
  found: Changes are limited to app.py, the focused untracked persistence test, and this debug session. The final app diff contains stable editor sources, event callbacks, safe explicit source replacement paths, the earlier price synchronization fix, and removal of unnecessary global cache clearing; no unrelated tracked files were modified.
  implication: The fix is targeted and ready for real-browser verification before archiving or committing.

## Resolution

root_cause: Streamlit 1.41.1 includes the serialized input dataframe bytes in each data_editor element ID. The app stored every editor return value into fuels_df/segments_df and then passed that changed dataframe back as the next data argument. Consequently, every ordinary cell edit changed the editor's element ID one rerun later despite a stable explicit key, recreating the browser widget while further edits could still be in flight and discarding them. The first fix removed additional key revisions but left this source-hash identity change intact.
fix: Kept the first fix's synchronization ordering, then separated immutable _fuel_editor_source_df/_segment_editor_source_df values from mutable fuels_df/segments_df drafts. Ordinary editor events are applied to the stable source in on_change callbacks before rerun and update only the mutable draft, so input bytes and element IDs remain stable. Unrelated reruns cannot replace a durable draft when an editor payload is absent. Scenario/reset/schema operations explicitly replace sources; a sidebar fuel-price edit safely rebases only the fuel editor from the complete durable draft and advances its revision because Streamlit forbids programmatic data-editor state assignment. Removed unnecessary global cache invalidation and added element-ID regression coverage.
verification: Focused AppTest passed in 9.1 seconds across segment edits, unrelated sidebar reruns, repeated fuel-table edits, queued price synchronization, one intentional sidebar-price rebase, stable IDs through Run, draft-only state before Run, and snapshot application after Run. py_compile and git diff --check passed; 8/8 regulatory tests and 2/2 strategy-selection UI tests passed. Real-browser rapid-edit confirmation remains required.
files_changed: [app.py, tests/test_staged_input_persistence_ui.py]
