# Optional hybrid genetic search

The **GA On/Off** switch is below **Compare strategies**. It defaults to Off
on each case-page load and applies only to that comparison. Saved vessel and
financial inputs are not changed.

- **Off:** the existing comparison and optimization path runs unchanged.
- **On:** each optimized policy first runs the existing optimizer, then a genetic
  search over complete fleet plans. Its best improvement is passed through the
  existing continuous voyage-leg refinement. The original feasible result is
  retained unless the full calculator returns a strictly cheaper plan.
- The four policy choices, report layout, annual ledgers, sensitivities and
  CSV columns are unchanged. An On report adds an explanation to the existing
  limitations list. Its saved/JSON result includes `ga_search` metadata for
  each optimized policy.

## Implementation scope

`portal/engine/ga_optimizer.py` contains the new search, using the Python standard
library. No dependency or database migration is required. Existing-code changes
are limited to the switch/style, request routing, optional optimizer selection
and an optional initial result for the existing leg refinement.

The regulatory equations and physical accounting remain in the existing
`profile()` and `simulate()` functions. The search does not add fuel pathways,
change settlement policies, optimize installation dates or add annual decisions.

Each individual contains real-valued voyage-leg replacement fractions and
allowed shore-power/wind retrofit switches for all ships. Crossover mixes ship
plans or their fractions; mutations can affect multiple ships. Elites preserve
good plans and fresh random plans maintain variety. Exact zero-replacement and
cap/equipment starts preserve no-investment options.

Vessel fractions are repaired using the existing original sea-energy weights.
Shared fuel constraints are repaired along a joint replacement line with fixed
equipment choices. Physical fuel purchases are affine along that line, including
wind, pilot fuel and alternative-system efficiency. The original simulator then
checks supply limits and calculates settlement independently in every year.

The defaults are 32 population members, up to 24 generations and a fixed random
seed of 1729. Each policy's evolutionary stage has a 10-second time limit,
checked between candidate evaluations; one evaluation can finish after this
limit. The original optimization and final refinement have their existing
runtime behaviour and are additional to that limit. Profile-cache memory is
bounded. Search settings and completed evaluation counts are saved with results.
With a time limit reached, different machines may complete different numbers of
evaluations; a fixed seed alone does not guarantee identical timed runs.

GA is a best-found heuristic, not a certificate of global optimality. A run may
return exactly the same strategy as Off. It cannot worsen the retained cost.

## Verification

- `test_ga_optimizer.py`: default/explicit Off identity and no GA invocation;
  shared supply caps, pilot energy and blend weights; eligibility/readiness;
  wind; the 2033/2034 RFNBO change with bank/streak history; seeded refinement;
  deterministic untimed completion; zero-budget fallback; unchanged baselines,
  report/export contract, snapshots and access/revision checks.
- An independently enumerated four-ship case checks all 16 OPS combinations:
  the original pooled search costs EUR 3,948,958.78; GA finds EUR 3,942,486.77,
  matching the exhaustive minimum and improving cost by EUR 6,472.01.
- `test_ga_browser.py`: desktop/mobile position, default Off, keyboard and label
  activation, both real submissions, saved results and return-to-case behaviour.
- Full application suite: 243 tests, OK with 10 optional browser checks skipped;
  the dedicated GA browser check also passed separately using headless Edge.

Browser screenshots are generated under `test-artifacts/ga-toggle/`.
