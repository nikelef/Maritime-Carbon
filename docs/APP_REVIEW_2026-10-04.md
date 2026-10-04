# Regulatory and operational application review — 4 October 2026

**Correction follow-up:** findings 1–3 below are fixed in engine **6.9.0**.
See [the correction record](CORRECTIONS_2026-10-04.md) for changes and verification.
Findings 4–5 remain open. The original review evidence below describes 6.8.1.

**Verdict: the core planning workflows work, but the application is not fully in order.** Two high-priority issues and three medium-priority issues were reproduced. Correct the fossil-factor guardrails before relying on edited fuel libraries, and correct HTTPS proxy handling before deploying the supplied container. The conditional RFNBO stress test and larger imports also need corrections.

Reviewed the current working tree, including the optional hybrid GA search: engine **6.8.1**, ruleset **EU-2026-10-01-review**. Existing uncommitted work was preserved. This review added this report; application source and customer records were not changed.

## Confirmed findings

| Priority | Finding | Effect |
| --- | --- | --- |
| P1 — high | Known fossil fuel factors can be changed contrary to the applicable default-factor rules. | Accepted edits can turn a FuelEU deficit into a surplus and substantially understate ETS emissions. |
| P1 — high | The container does not configure Waitress to recognize its HTTPS proxy. | The documented TLS-terminating reverse-proxy deployment can redirect repeatedly to the same HTTPS URL. |
| P2 — medium | The conditional RFNBO subtarget reuses the GHG-intensity source allocation. | Actual RFNBO consumption can disappear; OPS can enter the fuel-only denominator. |
| P2 — medium | Import and editor consumption limits use different units. | Valid imported ships with more than 100 leg rows cannot be saved in the vessel editor. |
| P2 — medium | Certain malformed XLSX files escape import validation. | Uploading a corrupt workbook can produce an HTTP 500 instead of a useful validation message. |

### 1. Fossil-factor guardrails allow non-regulatory results

Locations: [fuel fields](../portal/forms.py#L309), [field locking](../portal/forms.py#L334), [engine validation](../portal/engine/schema.py#L83).

The editor exposes MGO's complete WtW and physical CO2 factor. Validation requires positive CO2 and WtW at least equal to the entered combustion intensity, but does not preserve the mandatory fossil WtT and CO2 defaults. Methane pathways have stronger restrictions.

Reproduction used actual `FuelForm` validation, the fuel-edit view's cleaned-data assignment, and `ScenarioInput.validate()`: one ship above 5,000 GT, 1,000 t MGO entirely intra-EU, reporting year 2026, no berth consumption, EUA price EUR 90.

| Accepted MGO inputs | FuelEU balance, tCO2e | ETS emissions, tCO2e |
| --- | ---: | ---: |
| Default WtW 90.7674473; CO2 3.206 t/t | -61.08864 | 3,255.1 |
| WtW 76.3674473; CO2 unchanged | +553.79136 | 3,255.1 |
| WtW 40; CO2 1.0 t/t | +2,106.68136 | 1,049.1 |

The second row removes 14.4 g/MJ of upstream emissions. The third reduces ETS cost from **EUR 292,959 to EUR 94,419**. Both edits pass the application's validation. This example uses MGO, so the disclosed VLSFO composition assumption does not explain it.

FuelEU Article 10(4) and (5) restrict deviations from fossil WtT and fossil combustion CO2 defaults. The Commission confirms this explicitly in Q&A 10.5. [FuelEU legal text, Article 10](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32023R1805#page=25), [Commission FuelEU Q&A](https://transport.ec.europa.eu/transport-modes/maritime/decarbonising-maritime-transport-fueleu-maritime/questions-and-answers-regulation-eu-20231805-use-renewable-and-low-carbon-fuels-maritime-transport_en). Maritime MRV guidance section 4.6, footnote 95, also explains the fossil CO2 restriction. [Commission MRV guidance](https://climate.ec.europa.eu/document/download/31875b4f-39b9-4cde-a4e2-fbb8f65ee703_en?filename=policy_transport_shipping_gd1_maritime_en.pdf#page=44).

**Correction:** enforce supported fossil defaults in engine validation and the UI, and derive complete WtW consistently. Allow any supported actual non-CO2 factors only with the required review/evidence. Resolve fossil oil grade or blend composition through supported pathways rather than arbitrary edits to known MGO defaults. Review saved cases that already contain overrides; preserve historical reports and flag affected inputs before rerunning.

### 2. Supplied production entrypoint can cause an HTTPS redirect loop

Locations: [Docker entrypoint](../Dockerfile#L15), [Django proxy setting](../maritime/settings.py#L62), [deployment instructions](DEPLOYMENT.md#L30).

The documented deployment sets `TRUST_PROXY_HTTPS=1`, so Django expects `X-Forwarded-Proto: https`. The pinned Waitress 3.0.2 configuration defaults to `trusted_proxy=None` and `clear_untrusted_proxy_headers=True`. The supplied `waitress-serve` command adds no proxy options.

An isolated Waitress/Django middleware reproduction sent an HTTP upstream request for `/health/`, with public host `carbon.example.com` and `X-Forwarded-Proto: https`. Waitress removed the header; Django saw HTTP and returned **301 to the same public HTTPS URL**. Explicitly trusting the proxy and `x-forwarded-proto` returned **200**. This establishes the integration defect; a live Docker deployment was not available here.

Waitress documents the required trusted proxy address/header configuration and an alternative fixed HTTPS URL scheme for an exclusively HTTPS upstream deployment. [Official Waitress proxy documentation](https://docs.pylonsproject.org/projects/waitress/en/latest/reverse-proxy.html).

**Correction:** provide an explicit production proxy/scheme configuration in the entrypoint and deployment instructions. Trust only the intended proxy and restrict direct application-port access. Verify a real HTTPS request, login and health endpoint through the selected proxy before launch.

### 3. Conditional RFNBO stress-test quantities depend on the wrong allocation

Locations: [RFNBO numerator](../portal/engine/calculator.py#L204), [fuel-energy denominator and shortfall](../portal/engine/calculator.py#L215).

The optional 2034+ subtarget calculation uses `allocated_energy_mj` from the allocation that minimizes GHG intensity. That allocation can discard RFNBO when another fuel has lower intensity, or replace an OPS allocation with negative-intensity biofuel. The shortfall consequently changes even though actual RFNBO consumption and physical OPS electricity are unchanged.

Two valid 2034 cases, using `assume_active` and assumed Pd of EUR 1,000 per 41,000 MJ, reproduced this:

| Case | Observed result | Expected under the documented physical accounting |
| --- | --- | --- |
| 975 t HVO at 5 g/MJ plus 25 t e-diesel at 20 g/MJ, all EU/non-EU sea | RFNBO 0 MJ; shortfall 439,675 MJ; charge EUR 10,723.78 | Even proportional RFNBO energy is 533,750 MJ, or 2.42793% of 21,983,750 covered fuel MJ. Shortfall and charge should be zero. |
| 1,000 t HVO at -10 g/MJ on EU/non-EU sea; 100 t EU-berth MGO fully replaced by OPS | Fuel denominator 23,797,894.74 MJ; charge EUR 11,608.73 | Physical fuel denominator is 22,000,000 MJ. Excluding the 1,797,894.74 OPS MJ gives EUR 10,731.71, an EUR 877.02 difference. |

These are planning assumptions used to expose the accounting defect, not certifications of the example pathways. Article 5(10) excludes OPS; Article 16(4)(d–e) records annual fuel and RFNBO energy separately. [FuelEU legal text, Articles 5 and 16 and Annex IV](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32023R1805).

**Correction:** derive subtarget quantities independently from physical scoped fuel/RFNBO consumption, or implement a separately justified subtarget attribution. Preserve the GHG-intensity allocation. Add independent examples where lower-intensity biofuel displaces RFNBO or OPS in that allocation. This affects the displayed potential shortfall in unresolved cases as well as costs in assumed-active cases; present-day GHG-intensity calculations are a separate calculation.

### 4. Supported imports can produce vessels that cannot be edited

Locations: [import group limit](../portal/row_imports.py#L81), [input schema](../portal/engine/schema.py#L204), [editor formset](../portal/forms.py#L143), [HTML row limit](../templates/portal/vessel_form.html#L3), [server add-row handling](../portal/views.py#L160).

Import/schema permit up to 100 voyage/fuel groups per ship. Each group can contain five operating categories. The editor expands these into individual leg rows but permits only 100 rows, with an absolute limit of 200.

Reproduction: import one fuel for 21 voyages, each with all five categories. The **21 groups / 105 rows** import and validate successfully. Submitting the unchanged editor fails with **“Please submit at most 100 forms.”** Users cannot save fuel compatibility, OPS or wind review without removing valid consumption. A full supported import can produce 500 editor rows.

**Correction:** align limits in the importer, engine, formset, HTML and add-row fallback. If raising the editor limit, account for Django's submitted-field limit and optimizer capacity. Validate the largest permitted import through editing and calculation.

### 5. A corrupt workbook can bypass friendly validation

Locations: [XLSX exception translation](../portal/row_imports.py#L127), [upload view](../portal/views.py#L210).

Reproduction: take the supplied XLSX template; in the Vessels worksheet XML replace A2 with `<c r="A2" t="s"><v>999999</v></c>`, an invalid shared-string reference. Parsing raises **`IndexError: list index out of range`** from openpyxl. The parser does not translate `IndexError`, and the view only catches `ValueError`, so the exception reaches the server as an HTTP 500.

**Correction:** translate appropriate malformed-workbook parser exceptions at the import boundary into the existing validation message. Verify both a corrupt shared-string reference and a normal workbook; preserve unexpected programming errors for investigation.

## What passed

The default regulatory calculations reviewed match the official sources for the supported ordinary-EU planning scope: target schedule, different GT boundaries, reporting-year ETS phase-in, separate GWPs, methane-slip combustion accounting, renewable CO2 treatment, RFNBO intensity reward, physical GHG balance, penalty uplift and wind reward thresholds. The Commission supports annual prioritized FuelEU attribution. [FuelEU guidance](https://transport.ec.europa.eu/document/download/d4426ccc-ef46-4292-8b6d-5bf7a620f5ba_en?filename=fueleu_guidance_document_for_shipping_companies.pdf), [Commission ETS FAQ](https://climate.ec.europa.eu/areas-action/transport-decarbonisation/reducing-emissions-shipping-sector/faq-maritime-transport-eu-emissions-trading-system-ets_en).

Tenant isolation, roles, subscription checks, revision-aware changes, saved snapshots, report deletion permissions, export escaping and separate fuel/technical evidence gates were reviewed. The optional GA retains a feasible incumbent, uses the existing simulator, and records search settings/results. Passing heuristic-search tests does not establish a global optimum.

| Verification performed in this review | Outcome |
| --- | --- |
| Full `manage.py test portal.tests --noinput` | 243 discovered: **233 passed**, 10 optional browser tests skipped; no application failures. |
| Optional headless Edge workflows, enabled separately | **All 10 passed** across targeted runs: desktop/mobile forms, disclosures, alternative fuels, wind, Excel import, deletion, five-case desktop report/export campaign and GA toggle/submissions. |
| `manage.py check` | No issues. |
| `manage.py makemigrations --check --dry-run` | No changes detected. |
| `manage.py check --deploy --fail-level WARNING`, DEBUG off and PostgreSQL-style URL | No issues; does not establish database connectivity or proxy correctness. |
| `python -m pip check` | No broken requirements. |
| `python -m pip_audit -r requirements-web.txt --progress-spinner off` | No known vulnerabilities found at review time. |
| `manage.py collectstatic --noinput` | Completed. |
| `git diff --check` | No whitespace errors; Git emitted normal LF/CRLF notices. |

The browser campaign's first invocation included an incorrect desktop test-class selector. Its actual workflows passed; the correct `DesktopReleaseTests` class was subsequently run successfully. That harness error is excluded from application findings. Tests used isolated databases and fictional inputs. Generated desktop/mobile screenshots were inspected.

## Regulatory and production boundaries

The current Commission implementation index was checked, including 2026 verification/enforcement guidance, the FuelEU database regulation and published exemptions. The July 2026 MRV/FuelEU amendment remains identified as a proposal in the source retrieved; it was not treated as enacted replacement calculation rules. [Commission implementation index](https://transport.ec.europa.eu/transport-modes/maritime/decarbonising-maritime-transport-fueleu-maritime_en), [COM(2026)620 proposal](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52026PC0620).

The application explicitly excludes or restricts bank-funded/subset pools, borrowing optimization, measured/mixed-engine slip, mandatory OPS port-call penalties, EEA timing differences, special-route exemptions and statutory reporting/database procedures. These limits can affect customer costs and strategy rankings. They are documented model boundaries, distinct from the five reproduced defects above. Fuel certificates, technical compatibility and voyage classification still require customer/verifier review.

No public deployment, live PostgreSQL connection/restore, real HTTPS proxy, Docker image build, load test or penetration test was available for this review. A direct request to an existing local server on port 8000 found no listener; browser tests supplied their own live servers. Remaining launch work in [DEPLOYMENT.md](DEPLOYMENT.md) includes deployment/restore tests, privileged-access protection, monitoring, realistic capacity benchmarks and customer contract/privacy/support arrangements. Source/settings checks alone do not close those requirements.

## Recommended order

1. Correct fossil-factor guardrails and assess existing fuel-library overrides.
2. Correct the container/proxy integration and verify the actual deployment.
3. Correct conditional RFNBO quantity accounting before using 2034+ shortfall forecasts.
4. Align import/editor limits and normalize corrupt-workbook validation.
5. Repeat the relevant regression/workflow checks, then complete the documented production launch checks.
