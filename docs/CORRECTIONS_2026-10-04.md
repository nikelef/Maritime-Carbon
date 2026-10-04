# Corrections to the application review — 4 October 2026

Engine **6.9.0** · Ruleset **EU-2026-10-04-review**.

The two high-priority findings and the RFNBO accounting finding from the
[application review](APP_REVIEW_2026-10-04.md) are corrected. Statutory coefficients
are unchanged; the release enforces the supported fossil pathways and separates
physical RFNBO subtarget quantities from GHG source allocation.

## Fossil fuel defaults

The HSFO, VLSFO residual-oil assumption and MGO pathways now enforce their
supported default LCV, CO2, WtT, CH4 and N2O values in the input schema. Complete
FuelEU WtW is derived from those factors. The fuel editor displays locked factors
and ignores attempts to override them. Renewable supplier-pathway fields remain
editable under their existing evidence requirements.

FuelEU Article 10(4–5) restricts fossil WtT and combustion CO2 substitutions.
Actual fossil oil non-CO2 factors and other VLSFO compositions are outside the
supported default-only pathways of this release. [Commission Q&A, section 10.5](https://transport.ec.europa.eu/transport-modes/maritime/decarbonising-maritime-transport-fueleu-maritime/questions-and-answers-regulation-eu-20231805-use-renewable-and-low-carbon-fuels-maritime-transport_en).

New comparisons reject invalid older overrides. Cases with affected fuels show
**Restore fossil fuel defaults**, an explicit, revision-checked action that can
repair several fuel entries together. It retains prices, supply limits, evidence,
vessel consumption and previous reports. A normal fuel Save can also restore one
affected fuel when the other entries are valid. Valid legacy factors with an
absent explicit WtT field are still accepted if their complete WtW is correct.

Historical reports retain their saved inputs/results. The report page warns when
their fossil factors differ from supported defaults; no old report is recalculated.

## HTTPS proxy handling

The container now starts `python -m maritime.serve`. For TLS termination at the
reverse proxy, configure:

```text
TRUST_PROXY_HTTPS=1
WAITRESS_TRUSTED_PROXY=10.0.0.10
```

Replace the example address with the immediate proxy's actual peer IP. Startup
rejects missing/invalid addresses, hostnames, networks and wildcard trust. Only
`x-forwarded-proto` is trusted; other forwarded headers are cleared. The peer IP
continues to identify application login throttle buckets.

Django relies on the scheme validated by Waitress, rather than interpreting raw
forwarded headers itself. Tests verify HTTPS health/login responses, secure CSRF
login, rejection of an untrusted peer's HTTPS assertion, direct-peer throttling,
and ordinary local HTTP behavior. This follows the [official Waitress proxy
configuration](https://docs.pylonsproject.org/projects/waitress/en/latest/reverse-proxy.html).
See [deployment instructions](DEPLOYMENT.md) for the full configuration.

## RFNBO physical quantity accounting

Fuel/RFNBO subtarget energy is independently summed from physical consumption
after fuel switching, MGO pilot demand, wind savings and OPS replacement. Scope
is 100% intra-EU sea/EU berth, 50% EU/non-EU sea, and 0% other sea/non-EU berth.
Actual shore electricity is excluded. The optional GHG-intensity allocation and
RFNBO denominator reward do not change these quantities.

| Review example | Corrected result |
| --- | --- |
| 975 t HVO plus 25 t e-diesel on EU/non-EU sea | Physical RFNBO energy 533,750 MJ; share 2.42793%; potential shortfall and assumed charge both zero. |
| Negative-intensity HVO with EU-berth fuel replaced by OPS | Physical fuel denominator 22,000,000 MJ; actual OPS excluded; assumed Pd=1,000 charge EUR 10,731.71. |

These are test assumptions, not certifications of the example fuel pathways.
Conditional activation, assumed Pd, omitted RFNBO flexibility and equivalent-fuel
exemptions remain explicit planning limitations. [FuelEU Regulation, Articles 5
and 16 and Annex IV](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32023R1805).

JSON rows and annual totals now distinguish `fuel_energy_mj` /
`rfnbo_energy_mj` from `allocated_fuel_energy_mj` /
`allocated_rfnbo_energy_mj`. New reports carry the
`rfnbo_subtarget_accounting_method="physical_scoped"` marker. CSV retains existing
columns and appends physical fuel energy, allocated GHG fuel/RFNBO energy, and
the method marker. The newly named physical-fuel column is blank for historical
rows that used the old allocation-derived quantity.

Historical post-2033 reports show a correction notice while retaining their
recorded results. Run a new comparison to obtain corrected quantities and costs.

## Verification

New regressions cover prohibited fossil edits and form tampering; repair and
preservation of old cases/reports; trusted and untrusted HTTPS proxy requests;
both RFNBO review examples; mixed scope, pilot, wind, berth, reward expiry,
fees/streaks, unresolved costs and export reconciliation.

The independent equal-LCV allocation fixture now uses explicitly synthetic fuel
codes. It retains its independent arithmetic while the actual MGO pilot reference
keeps its supported regulatory defaults.

| Check | Result |
| --- | --- |
| Full application suite with `RUN_BROWSER_TESTS=1`, headless Edge | **277 tests passed**, including all 10 browser workflows; no skips or failures. |
| Final report/export/recovery regression checks | **42 tests passed** after the historical CSV field guard was added. |
| Django system check | No issues. |
| Migration check | No changes detected. |
| Production security check, DEBUG off and PostgreSQL-style configuration | No issues. |
| Waitress validated configuration | Accepts the configured peer and trusts only `x-forwarded-proto`. |
| Static asset collection | Completed. |
| `git diff --check` | Passed; only normal LF/CRLF notices. |

No production deployment or customer-data migration is performed. Docker and a
live external HTTPS proxy/PostgreSQL deployment were unavailable here. Configure
the actual immediate proxy IP and verify the production deployment before launch.

## Remaining findings

The two other medium-priority findings—import/editor row-limit alignment and
malformed-workbook exception handling—remain open, outside the requested fixes.
