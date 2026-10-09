# Maritime Carbon

A customer application for comparing fleet FuelEU Maritime and EU ETS planning
costs. The supported application is now **Django**, with password accounts,
company workspaces, user roles, subscription expiry, saved decision cases, and
immutable calculation snapshots.

The detailed [analyst guide](docs/Maritime_Carbon_Analyst_Guide.docx) is available
as a Word review draft, with a [readable source](docs/ANALYST_GUIDE.md). It explains
every desktop input, the voyage-leg recommendations, worked examples and exports.
See the [desktop release checks](docs/RELEASE_SANITY_CHECK.md) and
[pitch-video storyboard](docs/VIDEO_DEMO_PLAN.md). The latest
[single-voyage pitch video notes](docs/VIDEO_CURRENT_ENGINE_REVIEW.md) document
the current-engine rerun, fuel menu, shore-power setting and prioritized allocation.
The first video review cut has
[review notes and draft LinkedIn text](docs/VIDEO_REVIEW_NOTES.md), with
[reproducible recording and editing scripts](scripts/video/README.md).

## Try the application

Python 3.12 is recommended. On Windows:

```powershell
.\run-local.ps1 -Install
```

Open [the example fleet](http://127.0.0.1:8000/demo/) or
[the company sign-in page](http://127.0.0.1:8000/accounts/login/).
The example uses fictional data and does not create an account.
For a free hosted beta with private registration links, follow
[the Render setup](docs/RENDER_FREE.md). Operators create single-use trial
invitations in `/admin/`; recipients choose their own passwords and receive a
separate company workspace with a fictional example case.
There is also an [LNG/RFNBO transition example](http://127.0.0.1:8000/demo/?fuels=transition)
with an existing LNG vessel and a methanol-conversion candidate.

To create your company and its administrator, open a second PowerShell terminal:

```powershell
$env:DJANGO_DEBUG = '1'
.\.venv\Scripts\python.exe manage.py provision_company --company "Your company" --username "your.admin" --email "admin@your-company.com" --status active --days 365
```

The command asks for a password securely. No default customer password exists.
Company administrators can create colleagues in **Company & team**. Passwords
must have at least 12 characters; users can change them from **Account**.

For the service operator's separate administration console:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Then use `/admin/` to manage subscriptions, expiry dates and account recovery.
Operator access is privileged across companies. Customer accounts are not staff.

## Customer workflow

1. Create a **decision case** with reporting years, prices, discount rate, optional
   external-pool terms and a confirmed ordinary-EU voyage scope.
2. Add vessels individually or import the **Excel fleet template**, with separate
   Vessels and Consumption sheets, embedded instructions and a worked example.
   The [review workbook](docs/Maritime_Carbon_Fleet_Import.xlsx) matches the app's
   download. Excel uploads support up to 20 vessels and 2,000 consumption rows;
   a row-based CSV alternative and the older CSV format are also supported.
   In the consumption table, select Voyage 1–100, then a voyage/berth category,
   fuel, tonnes and shore-power share. Each voyage can have rows for
   intra-EU sea, EU/non-EU sea, other sea, EU berth or non-EU berth. Enter annual
   tonnes, including current pilot fuel in the appropriate row. A fuel may appear
   in several voyages and categories. All entered voyages form the annual plan. All library fuels are selectable at berth as well as
   at sea, subject to evidence and operating restrictions. EU berth rows can
   specify the share replaceable by shore power. Existing percentages and
   separate pilot/berth inputs are converted to rows when editing; saved reports
   retain their original inputs. The basic CSV retains its legacy columns.
3. Review the case's fuel library. Prices are illustrative. Renewable substitution
   requires both recorded eligibility evidence and vessel compatibility. LNG needs
   its engine class; RFNBOs need certified FuelEU WtT, any required measured engine
   factors and a separate ETS zero-rating review. Record pilot and conversion costs.
4. Compare four strategies. Select any strategy to inspect costs, vessel actions,
   banking, residual deficits, price sensitivity and assumptions.
   Policy names describe permitted choices; the recommendation names the actions
   actually selected. Shore-power electricity is separate from pooling purchases.
   A pooling-enabled policy may need no pooling. Equal-cost choices prefer the
   reference first, then a policy without pooling.
5. Download a CSV or complete JSON audit record, or print the report. Editing a
   case creates a new revision; previous reports keep their original inputs.
6. Analysts and company administrators can delete a saved report from the reports
   list or report page, or a decision case from the overview or case page. Each
   action opens a confirmation page. Deleting a case permanently removes its
   associated reports too; deleting a report keeps its case and other reports.
   Deletion events remain in company activity. Read-only viewers cannot delete.

Each account belongs to one company. Administrators manage colleagues, analysts
edit and calculate, and viewers read and export. Subscription entitlements are
checked on each protected request. The current supported case limit is 20 ships.

## What the model includes

- Reporting years 2025–2050 and the enacted FuelEU intensity-reduction pathway.
- Annual FuelEU balances and consecutive-deficit penalties **per ship**.
- Annual prioritized FuelEU attribution: eligible energy sources, including
  conventional fuels and alternatives, fill covered energy to minimize attained
  intensity including the elected RFNBO reward. Without an active reward this
  reduces to lowest-WtW order. FuelEU CH4/N2O factors are 25/298; ETS uses 28/265.
  Full EU–non-EU consumption is eligible; ETS remains proportional.
- ETS phase-in by **emissions reporting year**, proportional voyage allocation,
  and CH4/N2O from 2026. Eligible renewable CO2 zero-rating does not erase these gases.
- FuelEU banks retained by the originating ship, with no assumed cash or terminal value.
- Conditional fleet/external pooling, limited by entered annual capacity.
- Oil, HVO/FAME, LNG and bio-LNG, plus RFNBO e-LNG, e-methanol, e-ammonia,
  hydrogen (separate fuel-cell/combustion pathways) and e-diesel.
- Four LNG consumer/slip defaults; elective RFNBO reward through 2033; separate
  FuelEU and ETS eligibility; no invented zero for unknown CH4/N2O factors.
- Service-equivalent substitution with relative efficiency, MGO pilot, conversion/
  downtime investment, extra annual costs, technical limits and shared supply caps.
- Conditional post-2033 RFNBO shortfall reporting and explicitly assumed future-
  rule stress tests, with assumed charges separated in the audit/export.
- Shore electricity, generator/connection efficiency, OPS capital and annual cost.
- Wind-assisted propulsion combined with fuel switching and pooling: reviewed
  propulsion shares and net savings per sea row, retrofit/existing baseline
  treatment, investment and annual costs, and a separate FuelEU wind reward.
  See the [wind setup and accounting guide](docs/WIND_ASSISTANCE.md).
- Fuel, ETS, FuelEU penalties, pooling, electricity and other costs on a consistent
  horizon, with explicit discounting and price sensitivities.
- Reproducible inputs, SHA-256 fingerprint, engine/rule versions and source snapshots.

The search selects replacement separately by voyage, current fuel and sea-leg
category. Removed fuel and the alternative system's fuel/pilot energy stay on
the same leg. The ship's replacement cap and annual fleet fuel supply remain
shared constraints. The initial grid uses 2% of total sea energy; each leg
search samples its feasible range in 2% intervals, then refines between points.
A fuel-level search provides an incumbent; two leg-level
starts and up to three fleet passes add continuous quantity refinement,
FuelEU source-exhaustion boundaries, verified compliance-balance roots, supply
boundaries and transfers between legs. Each candidate is repriced using the
new annual FuelEU attribution, including the current-fuel baseline.
Reports identify the voyage, leg, removed tonnes, added alternative tonnes and
pilot tonnes. The report and CSV/JSON also expose the annual FuelEU source
inventory and allocated physical MJ. Decisions stay fixed over the horizon. **Lowest evaluated cost
is not a guarantee of the globally optimal fleet strategy.**

The case page and reports identify selected alternatives excluded by eligibility,
compatibility, replacement limits or zero supply. A low WtW entry does not enable
renewable-fuel eligibility or ETS CO2 zero-rating. Those settings must be reviewed
in the fuel library. Reports explain their saved inputs, including older runs;
edit the case and run a new comparison to use changed assumptions.

## Regulatory boundaries

The workflow supports cargo/tanker, container and passenger ships with the fuel
pathways listed above. One alternative system per vessel is evaluated per case.
Mixed consumer classes within a sea or berth category, measured/load-dependent
slip, non-MGO pilot for the alternative system,
borrowing optimization, mandatory OPS port-call penalties, voyage derogations,
ice-class adjustments and EEA timing differences need separate assessment.
The conditional RFNBO subtarget from 2034 is unresolved by default; an explicit
active/inactive stress test is not confirmation of a future rule or tariff.
Affected reports show a prominent partial-cost warning.

Existing Django cases keep their original fuel library. Use **Add available fuel
pathways** on the case page to extend it without replacing existing assumptions.
Engine 6.9.0 uses ruleset EU-2026-10-04-review. Saved reports retain their original
engine, inputs and results; pre-6.6 reports disclose their proportional FuelEU
attribution, while 6.6 reports retain physical-WtW ordering. Review saved fuel
inputs before rerunning with the current method. Older fossil oil overrides
are blocked until explicitly restored through **Restore fossil fuel defaults**.
RFNBO shortfalls now use physical scoped fuel energy separately from GHG
attribution, excluding actual shore electricity. See the
[LNG/RFNBO setup guide](docs/ALTERNATIVE_FUELS.md) for the new inputs.

This is a planning product, not a verifier, compliance filing service or fuel
certification system. Review the [regulatory basis](docs/REGULATORY_BASIS.md).
The application links directly to its primary legal and Commission sources.

## Production and selling access

The implemented commercial model is **company access activated by the operator**,
suitable for invoiced subscriptions or agreed trials. It includes active/trial/
suspended status, expiry dates and user/vessel limits. No card charges or payment
provider are connected.

Production uses PostgreSQL, HTTPS and the supplied Docker/Waitress application.
It refuses to start without a real secret, explicit allowed hosts and a
PostgreSQL connection. SQLite and the Django development server are local tools.

Follow [DEPLOYMENT.md](docs/DEPLOYMENT.md) for setup, provisioning, backups,
maintenance, and the remaining commercial launch requirements. The service has
not been deployed to a public domain, independently certified, or penetration tested.
The supplied [Render Free blueprint](render.yaml) uses an external PostgreSQL
database and a separate Render entry point; see [RENDER_FREE.md](docs/RENDER_FREE.md).

## Verification

```powershell
$env:DJANGO_DEBUG = '1'
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test portal.tests
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
```

Optional real-browser acceptance test, using an isolated test database:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:RUN_BROWSER_TESTS = '1'
$env:PLAYWRIGHT_CHANNEL = 'msedge'
.\.venv\Scripts\python.exe manage.py test portal.tests.test_browser
```

On Linux, install Playwright Chromium and leave `PLAYWRIGHT_CHANNEL` unset.
Screenshots and example exports go to ignored `test-artifacts/`.

GitHub Actions runs Django checks/tests, a production settings check, a dependency
audit and a Docker image build on push and pull request. Dependabot proposes
weekly dependency updates. See [SECURITY.md](SECURITY.md) for the security-file
map and the secrets that must stay outside GitHub.

## Structure

```text
manage.py                    Customer application entry point
maritime/                    Django configuration and routing
portal/engine/               Framework-independent calculation engine
portal/models.py             Companies, roles, cases, reports and activity
portal/tests/                Regulatory, security, workflow and browser checks
templates/ + static/         Responsive customer interface
docs/                        Regulatory basis, deployment and verification
SECURITY.md                  Security controls and production secrets guide
```

Current correction release: engine **6.9.0**, ruleset **EU-2026-10-04-review**.
See [the 4 October corrections and verification](docs/CORRECTIONS_2026-10-04.md).
See [RFNBO and GWP verification](docs/RFNBO_GWP_VERIFICATION.md). Saved results
retain their original factors and method; review saved complete WtW inputs before rerunning.

The [1 October UI and sanity review](docs/SANITY_CHECK_2026-10-01.md) records
compact vessel/methodology sections, operational checks and current source review.
Banked surplus is reserved for its originating ship by this model; bank-funded
pooling permitted in Commission guidance requires separate assessment.
