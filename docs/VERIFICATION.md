# Implementation verification

Current release: see [engine 6.7 verification](RFNBO_GWP_VERIFICATION.md)
for reward-aware allocation, separate FuelEU/ETS factors and September 10 checks.
[Engine 6.6 verification](PRIORITIZED_ALLOCATION_VERIFICATION.md) records the
preceding method, whose RFNBO ordering and FuelEU GWP factors were corrected.
The dated records below describe earlier releases.

Completed locally on 2026-09-07. LNG/RFNBO source review and engine revision are
dated 2026-09-07 (`6.0.0`, `EU-2026-09-07`).

## Verified

- Customer application: Django checks, migrations and static-asset collection.
- Production configuration: `check --deploy --fail-level WARNING` passes with
  secure production variables. This check does not establish database connectivity
  or certify a deployed hosting environment.
- Regulatory/physical reference tests: target boundaries, independently calculated
  penalties, ETS reporting-year phase-in and gases, proportional scope, GT boundary,
  fuel-energy conservation, generator/OPS efficiency and electricity/investment costs.
- Financial/accounting tests: ship-specific banks, no automatic surplus income,
  conservation of internal pool allocations, external capacity/cost, repeated
  penalties, shared supply limits, ledger/cost/NPV reconciliation and fast-score
  equivalence to a complete ledger.
- Search verification: one-ship result matches exhaustive evaluation of the same
  discrete grid; repeatability and evidence/compatibility gates are checked.
- Input validation: NaN/infinity, types, impossible scope shares, unknown fields,
  duplicate vessels, IMO check digits, pre-2025 history, evidence and inconsistent
  fossil-pathway factors.
- Customer security/workflow: login, safe redirects, CSRF, company isolation,
  read-only roles, expiry/suspension, stale revisions, stable snapshots, escaped
  exports, user limits, deactivation and secure company provisioning.
- CSV import: strict template, bounded size, percentage conversion, all-or-nothing
  validation and no implicit technical-compatibility approval.
- Real headless Edge acceptance: login → case creation → vessel entry → evidence
  review → comparison → strategy selection → CSV/JSON download → colleague creation
  → mobile navigation → logout. Browser console recorded no JavaScript errors.
- Desktop login/report and 390px mobile screenshots inspected. Mobile page has no
  document-level horizontal overflow. Wide ledgers scroll within their table panels.
- JavaScript syntax checks and `git diff --check` pass.
- Production dependencies and their transitive dependencies were checked with
  `pip-audit`: no known vulnerabilities were reported at the time of the check.

## Current Django-only verification · 2026-09-08

Engine 6.4.2: 152 tests discovered, 148 passed and four optional browser tests
skipped in the latest local run. This includes per-fuel replacement, high-price
eligibility regressions, saved-input exclusion notices and tenant-scoped exports.
The strategy-action regression reproduces the shore-power/no-pooling case,
prefers the non-pooling policy at equal cost, distinguishes internal and zero-price
external pooling, and verifies old reports render without snapshot changes.
Earlier browser evidence below describes earlier runs, not a new browser check.
The repository and development setup now contain only the Django application.


## LNG/RFNBO extension verification

- Four LNG consumer classes checked against independent hand calculations of
  combusted CO2/N2O, slipped CH4, derived FuelEU WtW and reporting-year ETS.
- LNG as a current or alternative fuel; bio-LNG/e-LNG keep methane and N2O when
  their CO2 is zero-rated. Different consumers using the same gas give different
  intensities and ETS emissions without changing the fuel purchase price.
- RFNBO denominator reward, optional non-election, mixed fuel/pilot/berth energy,
  2033/2034 expiry and physical (not rewarded) compliance-balance energy.
- Distinct hydrogen fuel-cell/combustion paths; ammonia N2O affects both regimes;
  missing TBM factors or WtT/evidence cannot activate a renewable pathway.
- Service-demand allocation with efficiency and pilot; full conversion cost only
  when switching, first-year capex and annual cost, shared pilot supply limits.
- Every new fuel's one-vessel optimum equals exhaustive evaluation of its grid;
  changing conversion cost can reverse a selected LNG switch. Ledger costs reconcile.
- Conditional RFNBO stress-test shortfall excludes OPS, retains physical energy,
  requires explicit price/rationale, and is not erased by a GHG bank or pool.
- All eight new library entries saved, calculated, rendered and exported through
  authenticated customer views; CSV totals reconcile and historical v5 rows still
  render/export without reinterpretation.
- Old libraries extend only by explicit, revision-checked, tenant/role-protected
  POST. Existing fuel overrides and historical inputs remain unchanged.
- Real headless Edge flow: create a 2033–2034 case, enter LNG main engine and pilot,
  enable reviewed e-LNG evidence, calculate, inspect reward expiry and nonzero ETS
  from pilot/non-CO2. Desktop report and mobile report/evidence-form screenshots
  inspected; no document-level mobile overflow or browser page errors.
- Existing full customer desktop/mobile acceptance test passes again. The public
  `/demo/?fuels=transition` example responds HTTP 200 with fictional transition data.
- Django checks, migration-drift check, static collection, Python compilation and
  diff whitespace checks pass. No new dependency or database migration was needed.

## Performance observation

On this workstation, a deliberately large 20-ship, 2026–2050 case, with 100%
maximum alternative shares and OPS choices, took approximately 19.6 seconds
after scenario-local profile/score caching (previously 55.8 seconds). This is
an indicative local measurement, not a production capacity or latency guarantee.
The caches exist only within one calculation and do not share customer data.

The v6 mixed e-LNG/e-methanol stress case (20 ships, 2026–2050, all replacement
shares, pilot/conversion costs and OPS choices) completed in 40.25 seconds on
this workstation while the historical regression suite was also running. Its
lowest evaluated NPV was EUR 1,717,017,976.84 for that artificial fixture. This is
a different workload from the earlier oil/HVO observation, not a like-for-like
speed comparison or production response-time guarantee.

## Evidence artifacts

Ignored local artifacts are in `test-artifacts/`:

- `login-desktop.png`
- `customer-report-desktop.png`
- `example-fleet-desktop.png`
- `example-fleet-mobile.png`
- `acceptance-report.csv`
- `acceptance-audit.json`
- `lng-vessel-desktop.png`
- `lng-rfnbo-report-desktop.png`
- `lng-rfnbo-report-mobile.png`
- `rfnbo-evidence-mobile.png`

These contain fictional test fixtures. Browser tests use an isolated test database
that is destroyed afterwards. No test customer accounts are left in the local
workspace database. No default or hard-coded customer password is installed.

## Not established by these tests

An actual PostgreSQL/container deployment, production concurrency/restore testing,
external penetration testing, customer-specific monitoring-plan reconciliation,
verifier approval, universal regulatory coverage and a global fleet optimum are
not established. Docker is not installed in this workspace, so the supplied image
definition has not been built here. No public hosting, payment integration or
external messages were performed. See DEPLOYMENT.md for the commercial launch work.
