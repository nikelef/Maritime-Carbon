# Prioritized FuelEU allocation verification — 10 September 2026

Historical engine 6.6.0; ruleset EU-2026-09-10. The RFNBO ordering and FuelEU
GWP factors in this release were subsequently corrected in 6.7.0. Numerical
examples below describe the earlier release; see RFNBO_GWP_VERIFICATION.md.

## Result

The engine now attributes each ship's annual covered physical energy from its
eligible energy inventory in ascending WtW intensity. Conventional fuels,
alternative fuel, pilot and electricity participate. Full eligible EU–non-EU
consumption is available; the 50% weight determines the covered total. Physical
fuel use, ETS allocation, purchase costs and shared supply caps remain separate.
The elected method and excluded activity are described in REGULATORY_BASIS.md.

The optimizer recomputes this attribution for every candidate and the baseline.
It checks cumulative source-capacity boundaries and verifies compliance roots
within the resulting intervals, including nonlinear RFNBO-reward profiles.
Fuel-level incumbents, vessel service limits and shared fleet supply remain
enforced. The search remains bounded and does not prove a global optimum.

## Independent checks

`portal/tests/test_prioritized_allocation.py` covers:

- The 100-unit/50-unit example: 20 alternative, 15 lower-WtW conventional and
  15 of the next conventional source fill the covered total.
- Unchanged proportional ETS emissions and full purchase costs.
- Annual attribution across voyages, deterministic row-order independence,
  conventional-only prioritization, and fully covered consumption.
- Exclusion of outside-scope sea/non-EU berth and separation between ships.
- Mixed-leg physical substitution without leaking outside energy into eligibility.
- Renewable energy capped at the covered total, RFNBO reward expiry and physical MJ.
- OPS, alternative pilot and relative energy requirement.
- Separate methane-consumer intensities for the same fuel.
- An independently solved extra-EU compliance-closing quantity, reconstructed
  final physical inventory and matching cost.
- Source-exhaustion optima, fractional fuel-supply limits, comparison against an
  independent two-leg grid, and saved-decision replay.
- Multi-year RFNBO reward expiry, opening bank, conditional subtarget and supply,
  compared against a dense independent quantity grid.

The broader desktop calculation campaign additionally checks 11 scenarios,
including shared FAME supply, pooling, OPS, LNG/bio-LNG, synthetic fuels and GT
boundaries. All source ledgers conserve the covered total and stay within their
eligible capacities. Earlier reference assertions were updated where their
proportional FuelEU assumptions were superseded; ETS expectations were retained.

## Updated analyst example

For ANALYST_GUIDE.md section 9.1, the independently checked result is:

- MGO removed on Voyage 1, intra-EU sea: 21.738698015 t/year.
- HVO added on that leg: 21.096418301 t/year.
- Total annual cost: EUR 833,084.91.
- Current-fuel external-pooling alternative: EUR 834,421.07.

Conventional-fuel prioritization improves the current-fuel baseline too; the
change is not applied only to alternative-fuel strategies.

## Verification performed

- `manage.py test portal.tests`: 198 tests discovered; 191 passed, 7 optional
  browser tests skipped; no failures (64.2 seconds in the recorded run).
- `RUN_BROWSER_TESTS=1 PLAYWRIGHT_CHANNEL=msedge manage.py test
  portal.tests.test_desktop_sanity.DesktopReleaseTests`: passed five desktop
  scenarios, strategy selection, annual allocation display and CSV/JSON downloads;
  no JavaScript errors (30.3 seconds).
- Report/export regressions verify the allocation method and source ledger.
  Historical reports are displayed without recalculation and disclose their
  original proportional attribution.
- `manage.py check`, `makemigrations --check --dry-run`, `collectstatic --noinput`
  and production-style `check --deploy --fail-level WARNING`: passed.
- Word guide rebuilt from Markdown: 237 paragraphs, 7,682 words, 22 rendered
  pages. All pages visually inspected; final revisions changed only pages 20–22,
  which were inspected again. Desktop allocation table visually inspected.

QA images, temporary rendering dependencies, test databases and exported
fictional scenarios remain outside version control. Existing customer cases and
saved analysis results were not rewritten. New comparisons use the new engine;
old reports retain their saved version and results.
