# Desktop release sanity check — 9 September 2026

Historical artifact: the recorded figures/screenshots below predate engine 6.6.0 annual prioritized FuelEU allocation. They are retained as the original review record; use the updated analyst guide and PRIORITIZED_ALLOCATION_VERIFICATION.md for the current engine.

Engine: 6.5.2. Ruleset remains EU-2026-09-07. This review verifies software behavior under recorded assumptions; it is not a new legal or certification audit.

## Result

The tested calculations conserve replacement-system energy on the selected voyage and sea leg, reconcile purchase costs and fleet totals, respect shared annual fuel caps and vessel service-share limits, and retain or improve the previous fuel-level search incumbent. Replaying saved leg decisions reproduces the result. These checks do not prove global optimality.

A desktop visual review found one presentation defect: a numerical settlement residual of 2.744727112e-9 tCO2e (EUR 0.00000052 at the fixture's pool price) labelled an internal fleet pool as also buying external surplus. Action summaries now suppress pooling quantities up to 1e-7 tCO2e. Exact amounts remain in the raw accounting/export ledgers. A regression checks both negligible residuals and a real external purchase.

## Calculation coverage

Eleven fictional scenarios are implemented in `portal/tests/test_desktop_sanity.py`:

- Mixed HSFO, VLSFO and MGO, with HVO substitution and two voyage identifiers, including outside-scope sea and non-EU berth fuel.
- Two vessels sharing a fractional FAME supply cap, with an opening FuelEU bank, partial EU berth OPS eligibility and fleet settlement.
- Fossil LNG substitution with a reviewed engine, alternative pilot and 80% relative energy requirement.
- LNG-to-bio-LNG with separate current and alternative methane consumers.
- E-methanol, e-ammonia and fuel-cell hydrogen alternatives with their required evidence and factors.
- E-diesel over 2033–2035, including reward expiry and an explicitly active future-subtarget stress assumption.
- Renewable fuel excluded when FuelEU eligibility is disabled.
- Outside-scope-only operation: fuel costs remain, with no modelled ETS/FuelEU charge.
- Three ships at 4,999, 5,000 and 5,001 GT to exercise the implemented coverage thresholds.

The existing one-vessel HVO regression continues to find approximately 21.875943 tonnes of MGO replaced by 21.229608 tonnes of HVO on Voyage 1's intra-EU sea category, at EUR 833,155.12 total annual cost. The new mixed-oil scenario includes extra outside-scope fuel and therefore has a different total; those figures should not be confused.

## Desktop workflow coverage

A headless Edge browser at 1600×1000 exercised five fictional cases in an isolated Django test database: mixed oils/HVO, the two-vessel FAME fleet, bio-LNG, e-methanol and multi-year e-diesel. It signed in, saved vessel forms, changed a voyage identifier and decimal consumption, calculated reports, selected every displayed strategy, checked leg remarks against the actual audit, and downloaded/reconciled CSV and JSON. No JavaScript page errors were reported.

The primary application database and customer cases were not edited by this campaign. Screenshots and exported fictional data are local QA artifacts under ignored `test-artifacts/desktop-release/`. Mobile viewports and the pre-existing browser tests containing mobile checks were not run.

## Verification commands and outcomes

- `manage.py test portal.tests --noinput`: 168 discovered tests, 163 passed and 5 optional browser tests skipped; no failures.
- `RUN_BROWSER_TESTS=1 PLAYWRIGHT_CHANNEL=msedge manage.py test portal.tests.test_desktop_sanity.DesktopReleaseTests --noinput`: the desktop test separately passed all five cases.
- `manage.py check`: no issues.
- `manage.py makemigrations --check --dry-run`: no migration changes.
- `manage.py collectstatic --noinput`: completed successfully.
- `pip_audit -r requirements-web.txt`: no known vulnerabilities found.
- `manage.py check --deploy --fail-level WARNING` with production-style settings: no issues.
- `git diff --check`: no whitespace errors.

The fixture checks compare physical inventory arithmetic, accounting totals and saved-decision replay, rather than only asserting that a report page loads. Existing tests also cover tenancy, roles, immutable snapshots, evidence gates, older reports and export behavior.

## Repeating the desktop review on Windows

Set `DJANGO_DEBUG=1`, `RUN_BROWSER_TESTS=1` and `PLAYWRIGHT_CHANNEL=msedge`, then run the desktop test above with the project's virtual-environment Python. The test uses the existing Edge installation and creates its own fictional workspace. Run the full suite without `RUN_BROWSER_TESTS` to avoid the unrelated optional mobile browser tests.

The Word guide is generated from `docs/ANALYST_GUIDE.md` using `docs/build_analyst_guide.py`. Document-tooling dependencies are separate from the application requirements. The guide contains 230 paragraphs, approximately 7,200 words and no tables. It was rendered with the Documents skill's `render_docx.py` through LibreOffice; all 21 page images were visually reviewed. Text-boundary checks found no content outside the page margins. It is a review draft rather than an approved customer manual.
