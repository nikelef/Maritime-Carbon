---
status: awaiting_human_verify
trigger: "In the strategy selection/ranking, `Pay as-is` cost is always identical to `Pool compliance`, but pool compliance should reflect pool purchases and avoided FuelEU penalty and therefore differ whenever pooling is economically/operationally used."
created: 2026-08-04T17:46:31.5147196+03:00
updated: 2026-08-10T11:58:00+03:00
---

## Current Focus

hypothesis: Fix is self-verified: the exact case now distinguishes an inactive pooling option from duplicate costing, while deficit cases still show real pool economics.
test: User imports the original JSON, reviews the new Pooling_Status/Pool_Bought columns and explanation, then creates a residual deficit (for example 2035-only or 9,000 t HSFO in 2026) and confirms Pool compliance changes to Used with a different NPV.
expecting: Original case says Not needed and explains equal NPV; deficit case says Used, shows a positive pool purchase, and differs from Pay as-is.
next_action: Await user confirmation in the real workflow before archiving/committing the resolved debug session.

## Symptoms

expected: Pool compliance uses pool surplus to cover FuelEU deficit, records pool bought and Pool_Net_Cost_EUR, avoids the corresponding FuelEU penalty, and produces a different compliance/total cost from Pay as-is when there is a deficit and pool price differs from the penalty-equivalent cost.
actual: Pay as-is and Pool compliance always show the same cost in strategy selection.
errors: No exception; incorrect equal strategy results.
reproduction: Run the app with a FuelEU-deficit portfolio and compare Pay as-is versus Pool compliance in the strategy ranking/selection.
started: Reported after recent signed FuelEU and ETS checkbox changes; whether it pre-existed is unknown.

## Eliminated

- hypothesis: Pool compliance is not constructed with pooling enabled.
  evidence: build_strategy_set explicitly sets pool_deficit true and pool_cap_tco2e for Pool compliance, while Pay as-is sets pool_deficit false.
  timestamp: 2026-08-04T17:58:00+03:00

- hypothesis: The simulation or aggregation collapses the two baseline strategies to equal values.
  evidence: Direct execution on the default deficit portfolio produced Pool compliance Total_NPV_EUR 21.6865M with 3,695.17 tCO2e bought and zero penalty, versus Pay as-is Total_NPV_EUR 22.8768M with zero pool bought and 2.3242M FuelEU penalty.
  timestamp: 2026-08-04T17:58:10+03:00

- hypothesis: The exact imported scenario remains equal even after a real FuelEU deficit exists.
  evidence: Exact-case AppTests diverged for 2035-only, 2026-2050, and 2026 with 9,000 t HSFO. In every case Pool compliance bought the deficit and avoided the Pay as-is penalty.
  timestamp: 2026-08-10T11:30:00+03:00

- hypothesis: Interactive HSFO edits are visually accepted but do not propagate into strategy evaluation.
  evidence: Injecting the real `segment_editor` delta changed session `segments_df` from 1,890 to 9,000 t HSFO and immediately produced distinct Pool compliance/Pay as-is totals with positive pool purchase.
  timestamp: 2026-08-10T11:36:00+03:00

## Evidence

- timestamp: 2026-08-04T17:47:30+03:00
  checked: Project debug knowledge base
  found: No .planning/debug/knowledge-base.md exists.
  implication: There is no known-pattern diagnosis to prioritize.

- timestamp: 2026-08-04T17:47:40+03:00
  checked: Repository state before implementation work
  found: git status showed only the newly created .planning debug directory as untracked; no pre-existing code changes were present.
  implication: Investigation starts from clean main, while preserving the required debug artifact.

- timestamp: 2026-08-04T17:47:50+03:00
  checked: Codebase search for strategy names and pooling cost fields
  found: app.py constructs Pay as-is and Pool compliance near lines 1122-1134, computes Pool_Net_Cost_EUR near line 1035, aggregates it near line 1236, and ranks/displays strategies later in the same file.
  implication: The suspected execution path is localized to app.py; tests currently appear concentrated in tests/test_regulatory_costs.py.

- timestamp: 2026-08-04T17:54:20+03:00
  checked: Complete app.py execution path
  found: build_strategy_set creates distinct Pay as-is (pool_deficit false) and Pool compliance (pool_deficit true) dictionaries. simulate_strategy buys up to the negative effective balance, reduces the deficit before calling fueleu_penalty_eur, records Pool_Bought_tCO2e and Pool_Net_Cost_EUR, and aggregates both costs without overwriting them.
  implication: Static inspection does not support missing pool flags, missing pool costing, or aggregation collapse; runtime evidence is required.

- timestamp: 2026-08-04T17:54:35+03:00
  checked: Complete regulatory_costs.py and tests/test_regulatory_costs.py
  found: The penalty helper correctly returns a positive cost for positive deficit and zero for non-positive deficit. Existing tests cover signed segment display costs and ETS certification but do not exercise simulate_strategy, build_strategy_set, or evaluate_strategies.
  implication: The reported strategy regression is currently unprotected and may depend on app-level input/state behavior.

- timestamp: 2026-08-04T17:57:35+03:00
  checked: Direct strategy execution on current main with the default FuelEU-deficit portfolio
  found: Pool compliance Total NPV was approximately EUR 21.6865M, bought 3,695.17 tCO2e, incurred approximately EUR 0.8607M pool cost, and avoided all FuelEU penalty. Pay as-is Total NPV was approximately EUR 22.8768M, bought zero pool, and incurred approximately EUR 2.3242M FuelEU penalty.
  implication: Pool economics are correct and distinct before rendering; equal displayed selection results cannot originate in the cost engine.

- timestamp: 2026-08-04T17:58:15+03:00
  checked: Decision Cockpit and Pooling Desk selection bindings
  found: selected_strategy filters selected_detail only. Metrics k1-k5 read best instead of the selected strategy row, and the Pooling Desk immediately assigns selected_strategy = comparison_df.iloc[0][Strategy], discarding the user's selector choice.
  implication: Selecting Pay as-is or Pool compliance shows the same best-strategy headline/pooling values, which exactly explains the reported UI symptom.

- timestamp: 2026-08-04T18:01:00+03:00
  checked: New Streamlit AppTest regression on current main
  found: Selecting Pay as-is fails to expose a Selected strategy NPV metric because the cockpit only renders the globally optimized NPV; the test errors before comparison, reproducing the disconnected selector contract.
  implication: The regression test fails before the fix for the expected reason and will directly verify selection-dependent cockpit and pooling values afterward.

- timestamp: 2026-08-04T18:05:00+03:00
  checked: Full unittest suite after the fix
  found: All 9 tests passed, including the AppTest that switches from Pay as-is to Pool compliance, verifies different selected-strategy NPVs, verifies zero pool need for Pay as-is, and verifies positive pool need for Pool compliance.
  implication: The original selector symptom is reproduced and corrected, while existing signed FuelEU and ETS behavior remains green.

- timestamp: 2026-08-04T18:05:10+03:00
  checked: Python compilation after the fix
  found: app.py, regulatory_costs.py, tests/test_regulatory_costs.py, and tests/test_strategy_selection_ui.py compiled successfully.
  implication: The implementation and regression test contain no Python syntax errors.

- timestamp: 2026-08-04T18:06:15+03:00
  checked: Final git diff and whitespace validation
  found: git diff --check passed. The only worktree changes are app.py, the new tests/test_strategy_selection_ui.py, and the required .planning debug session.
  implication: The patch is minimal, targeted, and contains no whitespace errors or unrelated edits.

- timestamp: 2026-08-10T00:00:00+03:00
  checked: Human verification of the previously committed selector-binding fix
  found: The user reports the actual issue remains in `maritime_carbon_decision_case _this one.json`: Pay as-is and Pool compliance have the same `Total_NPV_EUR` after changing HSFO quantity or the applicable start/end years.
  implication: The prior UI-selector diagnosis was incomplete; investigation must reproduce the strategy-table calculation with the exact imported scenario and trace restored/edited inputs into the engine.

- timestamp: 2026-08-10T00:10:00+03:00
  checked: Exact user decision-case JSON and its embedded comparison output
  found: The saved 2026 case has attained GFI 83.932 versus a 2026 FuelEU limit of 89.337, zero FuelEU penalty, zero final deficit, zero pool purchase, and identical Pay as-is/Pool compliance totals. Its segment 1 combines 1,890 t HSFO with 200 t FAME and enables `Low-carbon first` on a 50%-scope voyage.
  implication: Pooling is correctly a no-op for the saved one-year surplus case. The decisive reproduction must edit the portfolio/horizon far enough to create a negative FuelEU balance, then determine whether the UI passes that edit to evaluation.

- timestamp: 2026-08-10T00:11:00+03:00
  checked: Repository commits dated 4 August 2026
  found: Four relevant commits exist: signed FuelEU surplus display/cost support, certified ETS zero rating, helper-module reload, and the later selector-binding fix.
  implication: History comparison should focus first on the signed-balance commit and any contemporaneous state/editor changes, while ETS and selector-only diffs are lower-probability causes of baseline simulation equality.

- timestamp: 2026-08-10T11:23:00+03:00
  checked: Exact scenario restored through Streamlit AppTest
  found: The UI strategy table exactly reproduces the JSON baseline: both strategies total EUR 1,937,279.1771 with zero penalty, pool cost, and final deficit. Extending the 42-strategy, 5%-grid case to 2035 did not complete within the 180-second AppTest timeout.
  implication: Scenario restore is correct for the saved baseline, disproving a generic import mismatch. The horizon change needs a reduced baseline-only test to avoid confounding correctness with the app's expensive full recomputation.

- timestamp: 2026-08-10T11:27:00+03:00
  checked: Reduced exact-case AppTest after changing end year from 2026 to 2035
  found: The rerun completed and both totals remained EUR 19,372,791.771 with zero aggregate penalty, pool cost, and final deficit.
  implication: The unchanged table is reproducible, but not yet proof of a defect: Pay as-is banks the large 2026-2029 surpluses and carries them into the tighter 2030/2035 years before any pool purchase is considered. A start-at-2035/no-carry case is required to falsify that explanation.

- timestamp: 2026-08-10T11:30:00+03:00
  checked: Three exact-case deficit-producing AppTests
  found: At 2035-only, Pool compliance cost EUR 1.981M versus Pay as-is EUR 2.141M and bought EUR 43,899 of pool surplus instead of EUR 204,109 penalty. From 2026-2050, totals were EUR 51.487M versus EUR 62.636M. With 9,000 t HSFO in 2026, totals were EUR 7.630M versus EUR 7.660M.
  implication: Simulation, aggregation, scenario restore, and year settings all distinguish strategies once pooling is actually used. The user's ordinary HSFO/horizon edits likely did not cross the bank-adjusted deficit threshold, or the interactive editor failed to propagate the edit.

- timestamp: 2026-08-10T11:33:00+03:00
  checked: Exact restore data-editor state and 4-August signed-cost commit
  found: Streamlit initializes `segment_editor` with an empty edit delta and the restored five-row `segments_df`. The 4-August signed-cost commit changed only current-segment presentation/helper extraction; it did not modify balance, pooling, banking, scenario restore, strategy simulation, or editor state.
  implication: The suspected 4-August engine regression is not supported by the diff. A real editor delta is the last untested input path.

- timestamp: 2026-08-10T11:36:00+03:00
  checked: Exact restore followed by a real Streamlit data-editor delta from 1,890 to 9,000 t HSFO
  found: Session state updated to 9,000 t; Pool compliance total became EUR 7.629642M with EUR 8,906.97 pool cost, while Pay as-is became EUR 7.659509M with EUR 38,773.33 penalty and 59.38 tCO2e deficit.
  implication: Editor propagation is correct. The saved-case equality occurs because pooling is not used, and the UI lacks the fields/explanation needed to make that state visible.

- timestamp: 2026-08-10T11:44:00+03:00
  checked: First focused unittest invocation
  found: `python -m unittest tests.test_strategy_selection_ui` failed before test collection because `tests` is not a Python package (no importable module path).
  implication: This is a test-runner invocation issue, not a product/test failure; run the test file directly as the repository's existing pattern requires.

- timestamp: 2026-08-10T11:46:00+03:00
  checked: Direct execution of tests/test_strategy_selection_ui.py
  found: Streamlit's isolated runner could not import root-level `regulatory_costs` because direct script execution puts `tests/` rather than the repository root on `sys.path`; tests therefore did not reach product assertions.
  implication: Use unittest discovery from the repository root, which preserves the root import path. No behavioral hypothesis was tested by this failed invocation.

- timestamp: 2026-08-10T11:50:00+03:00
  checked: Focused Streamlit strategy-selection regression tests
  found: Both tests passed. The new test observes equal NPV plus `Not needed`, zero purchase, and the explanatory message in surplus state; after a real editor delta creates a deficit, it observes `Used`, positive pool purchase, unequal NPV, and removal of the no-op message. The prior selector-binding regression also remains green.
  implication: The fix addresses the confirmed presentation failure and does not disturb active pooling or selected-strategy behavior.

- timestamp: 2026-08-10T11:53:00+03:00
  checked: Static validation and final worktree scope
  found: app.py and tests/test_strategy_selection_ui.py compile; `git diff --check` passes. Only app.py, tests/test_strategy_selection_ui.py, and the required debug record are modified.
  implication: The patch is syntactically valid, whitespace-clean, and contains no unrelated file changes.

- timestamp: 2026-08-10T11:58:00+03:00
  checked: Exact user JSON after the fix with baseline-only strategy search
  found: No Streamlit exceptions. Pay as-is remains EUR 1.937279M with `Not enabled`; Pool compliance remains EUR 1.937279M with `Not needed`, zero Pool_Bought_tCO2e, and the explicit no-purchase/current-and-banked-surplus explanation.
  implication: The original reproduction is now accurately explained in-place, while previously verified deficit cases continue to expose active pooling and distinct NPVs.

## Resolution

root_cause: The exact saved case is FuelEU-surplus in 2026 (attained 83.932 vs limit 89.337), and earlier surpluses are banked across longer horizons, so Pool compliance legitimately buys nothing and is numerically identical to Pay as-is. The strategy table nevertheless presented it as a separate active option while hiding `Pool_Bought_tCO2e` and providing no no-op status/explanation, making correct conditional behavior look like duplicate costing. The 4-August signed-cost change did not alter strategy simulation.
fix: Retained the selector fix; evaluate each strategy as `Used`, `Not needed`, or `Not enabled`; added Pooling_Status and Pool_Bought_tCO2e to the financial table; and added a no-op explanation when Pay as-is and Pool compliance are equal because no pool is purchased.
verification: Focused Streamlit test file passes 2/2, covering selector binding plus surplus no-op to active-deficit transition. Exact user JSON shows Not needed, zero purchase, explanation, and no exceptions. Deficit cases (2035-only, 2026-2050, and 9,000 t HSFO) show positive pool purchase and distinct NPVs. Python compilation and git diff --check pass.
files_changed: [app.py, tests/test_strategy_selection_ui.py]
