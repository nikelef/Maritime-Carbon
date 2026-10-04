# UI and application sanity review — 1 October 2026

Engine **6.8.1** · Ruleset **EU-2026-10-01-review**.

Follow-up: the [2 October methodology coverage review](METHODOLOGY_COVERAGE_2026-10-02.md)
expands the guide to 13 linked topics, including a prominent wing setup and
accounting section. The seven-section description below records the 1 October state.

The checks found no new numerical defect in the supported planning calculations.
This release changes the interface, source references and explanations of model
limits. Calculation factors and optimization policy remain those of 6.8.0.
Existing reports retain their saved inputs, results and version identifiers.

## Interface changes

All eight vessel-profile sections and all seven Rules & methodology sections
now use compact disclosure rows with a left-hand arrow. Sections start closed;
clicking the heading or using Enter/Space opens them. Multiple sections can
remain open while editing.

Validation remains usable with hidden inputs: native validation opens the
containing section before focusing the invalid field. Django field/formset
errors expand their section; general form errors expand the editor so the draft
can be corrected. Server-side add-row fallback keeps the consumption section
open. Existing input values survive validation and successful saving.

The wind anchor opens its section, including when the same link is selected
again. Printing expands the methodology and restores the reader's prior open
sections afterwards. Both the current table editor and the legacy form use
the new presentation.

Desktop (1440 × 1000) and mobile (390 × 844) screenshots were inspected.
The browser checks also opened each methodology section at mobile width and
checked for page overflow. Screenshots and the print sample are local, ignored
QA artifacts in `test-artifacts/compact-sections/`.

## Regulatory findings and corrections to the explanation

**Banking and pooling:** the engine reserves banked surplus for the originating
ship and requires a fully settled modelled fleet pool. Those are restrictions
of this search. Commission guidance allows banked surplus to be offered through
pooling. The methodology, opening-bank help and new report warnings now explain
that omitted bank-funded pools, subset pools and partial settlements can affect
costs and strategy rankings. See [FuelEU guidance, sections 11.2–11.3](https://transport.ec.europa.eu/document/download/d4426ccc-ef46-4292-8b6d-5bf7a620f5ba_en?filename=fueleu_guidance_document_for_shipping_companies.pdf#page=116).

**RFNBO flexibility:** the methodology now explicitly describes RFNBO banking
and pooling as unimplemented features of the conditional-subtarget stress test,
rather than suggesting that these mechanisms are legally unavailable. They are
separate from the GHG-intensity balance. See [Commission FuelEU Q&A, Articles 20–21](https://transport.ec.europa.eu/transport-modes/maritime/decarbonising-maritime-transport-fueleu-maritime/questions-and-answers-regulation-eu-20231805-use-renewable-and-low-carbon-fuels-maritime-transport_en).

**Port movements:** the supported-use explanation now flags port movements
outside voyage boundaries for separate scope assessment. ETS covers such
within-port emissions fully; the app has no dedicated port-movement input
category. See [Commission maritime ETS FAQ, “emissions within ports”](https://climate.ec.europa.eu/areas-action/transport-decarbonisation/reducing-emissions-shipping-sector/faq-maritime-transport-eu-emissions-trading-system-ets_en).

**Current sources:** the app now links the [25 June 2026 verification guidance](https://transport.ec.europa.eu/document/download/3b32fff7-c4c0-482c-8882-1ff8bf43648d_en?filename=Guidance_on_verification_for_the_FuelEU_Maritime_Regulation.pdf),
[25 June 2026 enforcement guidance](https://transport.ec.europa.eu/document/download/8522a7d4-3e8d-4e74-85e8-282f0050bd17_en?filename=Guidance_for_Member_State_enforcement_of_the_FuelEU_Maritime_Regulation.pdf),
the [updated ETS/MRV general guidance](https://climate.ec.europa.eu/document/download/31875b4f-39b9-4cde-a4e2-fbb8f65ee703_en?filename=policy_transport_shipping_gd1_maritime_en.pdf)
and [actual methane-slip guidelines](https://transport.ec.europa.eu/document/download/9573f03b-a821-46ee-8131-312832b4ca32_en?filename=guidelines_for_reporting_and_verification_actual_methane_cslip_ef.pdf).
These support verification, evidence and scope boundaries; the product does not
perform their statutory procedures or implement measured slip.

The [Commission implementation index](https://transport.ec.europa.eu/transport-modes/maritime/decarbonising-maritime-transport-fueleu-maritime_en)
was also checked for newer guidance, secondary legislation and exemptions.
It includes the FuelEU database implementing regulation 2026/394 and 2026
national exemptions. Database administration and individual voyage exemptions
remain outside this calculator. Direct EUR-Lex retrieval was blocked by its
browser challenge during this review; accessible official Commission guidance
and Q&A supplied the source cross-check. This is not a complete legal-change
certification or a review of a customer's monitoring plan.

## Calculation checks

| Area | Verification performed |
| --- | --- |
| Coverage and targets | GT boundaries, year boundaries, full/half/zero scope, enacted FuelEU reduction steps and reporting-year ETS phase-in. |
| Fuel emissions | Distinct FuelEU/ETS GWP values; all four default LNG consumers; retained CH4/N2O with eligible renewable CO2 zero-rating. |
| Annual allocation | Eligible inventory bounds, conservation, row-order independence, RFNBO reward expiry and comparison with independently enumerated allocation vertices. |
| Physical choices | Voyage-leg substitution, pilot energy, relative efficiency, shore-power replacement shares and wind savings without double counting. |
| Financial settlement | Ship banks, consecutive penalties, feasible pools, shared supply caps, capital/annual costs, discounting and saved-decision replay. |
| Reporting | CSV/JSON reconciliation, source/version snapshots, historical-report preservation, strategy actions and explicit partial-cost warnings. |

Two additional regression cases use published examples rather than another
call to the same engine. The 100 t HFO + 200 t HVO + 300 t LNG example gives
**2,017.43 tCO2e** with its stated physical factors. See [ETS/MRV guidance, section 4.7](https://climate.ec.europa.eu/document/download/31875b4f-39b9-4cde-a4e2-fbb8f65ee703_en?filename=policy_transport_shipping_gd1_maritime_en.pdf#page=45).
The 1,221.22 tCO2e deficit at 90.77 gCO2e/MJ gives approximately
**EUR 787,551**, matching published whole-euro precision. See [FuelEU guidance, section 12.1](https://transport.ec.europa.eu/document/download/d4426ccc-ef46-4292-8b6d-5bf7a620f5ba_en?filename=fueleu_guidance_document_for_shipping_companies.pdf#page=123).

## Operational checks

The full automated suite and optional browser workflows cover authentication,
company isolation, roles, subscriptions, input validation, imports, editing,
calculation, export, saved reports and deletion confirmations. Tests use
temporary databases and fictional companies, not customer records.

| Check | Outcome |
| --- | --- |
| `manage.py test portal.tests --noinput` | 231 discovered: 222 passed, 9 optional browser tests skipped; no failures. |
| Browser workflows (headless Edge, enabled separately) | All 9 passed across targeted runs: 5 form/disclosure workflows, wind, five-case desktop campaign, Excel import and record deletion. |
| `manage.py check` | No issues. |
| `manage.py makemigrations --check --dry-run` | No changes. |
| `manage.py check --deploy --fail-level WARNING` | No issues with production-style environment settings. |
| `python -m pip check` | No broken requirements. |
| `python -m pip_audit -r requirements-web.txt --progress-spinner off` | No known vulnerabilities found at review time. |
| `manage.py collectstatic --noinput` | Completed; updated CSS/JavaScript and manifest assets generated. |
| `git diff --check` | Passed. |

The production configuration check does not test a live PostgreSQL connection,
reverse proxy, backups or a deployed service. Docker was unavailable here, so
the image build was not repeated. The existing CI workflow includes that build.
Browser coverage used Edge/Chromium; Safari and Firefox were not tested.

## Remaining planning limits

Bank-funded/subset pools, borrowing optimization, measured or mixed-engine LNG
slip, mandatory OPS port-call penalties, route/EEA derogations, port movements,
ice adjustments and RFNBO-specific flexibility still require separate work where
relevant. Future RFNBO activation and tariffs remain explicit stress assumptions.
Fuel evidence and operational compatibility must be reviewed outside the app.
The bounded fleet search does not certify a global optimum. Passing this review
establishes the tested software behavior, not complete statutory compliance.
