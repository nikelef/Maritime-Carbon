# RFNBO allocation and GWP correction verification

10 September 2026 · Engine 6.7.0 · Ruleset EU-2026-09-10-r2.

## Corrections and regulatory basis

FuelEU now uses CH4=25 and N2O=298, independently of ETS CH4=28 and N2O=265.
Derived methane/RFNBO intensities, new-case oil defaults and fossil consistency
validation use the FuelEU factors. ETS mass, coverage and factors are unchanged.

Annual attribution now minimizes the complete ratio of lifecycle emissions to
physical covered energy plus the elected extra RFNBO reward energy. It solves
the bounded linear-fractional inventory problem, including partial sources,
OPS, negative intensities and fixed per-fuel reward elections. The fleet search
evaluates this allocation for every physical candidate and includes source
capacity and reward-order boundaries in both the pre-2034 and post-2033 regimes.

Basis: [Commission FuelEU guidance](https://transport.ec.europa.eu/document/download/d4426ccc-ef46-4292-8b6d-5bf7a620f5ba_en?filename=fueleu_guidance_document_for_shipping_companies.pdf),
sections 4.3.3, 4.3.6 and 4.4; FuelEU Annex I refers to RED Annex V Part C(4).
The minimum-intensity allocation is the application's election under permitted
annual free attribution. It is not a legally mandatory ordering. See
[REGULATORY_BASIS.md](REGULATORY_BASIS.md) for formulas, scope and limitations.

## Independent numerical evidence

- Commission e-diesel example: WtT=-63.2, LCV=42,700 MJ/t, CO2=3.206,
  CH4=0.00005, N2O=0.00018. FuelEU WtW is 13.1674473068 g/MJ and its pure-fuel
  rewarded intensity is 6.5837236534. The former shared-factor calculation gave
  13.0318501171 and 6.5159250585 respectively.
- Reported 50-MJ example: eligible 40 bio at WtW 20, 20 RFNBO at 25 and 40
  fossil at 90. The active reward allocates 30 bio + 20 RFNBO, giving
  15.7142857143 g/MJ, versus 17.5 from the previous physical-WtW ordering.
  Reward disabled/expired gives 40 bio + 10 RFNBO and intensity 21.
- A separate OPS example demonstrates that sorting by WtW/reward alone is also
  incorrect: 40 OPS + 10 bio at WtW 20 beats using RFNBO at WtW 30, despite
  its standalone rewarded intensity of 15.
- 100 deterministic randomized inventories, each tested with reward 1 and 2,
  match independent exhaustive vertex enumeration to 9 decimal places. Tests
  include negative intensities, OPS, inventory bounds and row-order independence.
- 30 randomized affine inventory changes, each in both reward regimes, verify
  that the computed boundaries partition allocation into affine segments.
  A constructed case independently verifies the exact reward-order change at
  t=0.5, and clipped search intervals exclude roots outside their feasible range.
- Full-profile checks include extra-EU scope, OPS, MGO pilot and 2033/2034 reward
  expiry. A full-horizon optimizer check compares both OPS choices with a dense
  201-point fuel-quantity grid. Existing multi-year bank, subtarget, supply and
  reconstructed-inventory tests remain in the suite.

The analyst guide's corrected oil/HVO exercise removes 23.180977789 t/year MGO
and adds 22.496085264 t/year HVO on the intra-EU leg. Annual cost is
EUR 833,822.73; the current-fuel external-pooling alternative is EUR 835,273.05.
These figures use newly initialized oil factors, not preserved older inputs.

## Verification performed

- Full suite: 209 tests discovered; 202 passed, 7 optional browser tests skipped;
  no failures (91.7 seconds, with desktop checks running concurrently).
- Separate Edge desktop release test: five scenarios, strategy selection,
  allocation display and CSV/JSON export reconciliation passed; no JavaScript
  errors (34.2 seconds).
- Report/export tests cover `annual_reward_aware`, source `reward_multiplier`,
  unchanged historical proportional reports and distinct 6.6 physical-WtW reports.
- Django system check, migration dry-run, static-file collection and production
  security configuration checks passed. No schema migration or application
  dependency change is required.
- Word analyst guide rebuilt from Markdown and rendered to 22 pages. All page
  layouts and the desktop allocation table were visually checked.

## Existing data and limits

Saved reports keep their original version, inputs and results. Previously entered
complete WtW values remain user inputs and must be reviewed before rerunning an
older case. The update does not silently overwrite supplier values or customer
fuel libraries. Tests use isolated databases and fictional scenarios.

The fixed-inventory annual intensity minimum is solved to numerical tolerance;
the overall fleet-cost optimizer remains a bounded search without a global
optimum guarantee. Reward election remains fixed. The conditional RFNBO
subtarget retains its existing stress-test scope; separate RFNBO banking,
pooling and equivalent-fuel exemptions are not added by this correction.
