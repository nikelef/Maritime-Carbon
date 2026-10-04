"""Versioned planning rules. See docs/REGULATORY_BASIS.md for applicability."""
ENGINE_VERSION = "6.9.0"
RULESET_VERSION = "EU-2026-10-04-review"
CHECKED_ON = "2026-10-04"
REFERENCE_G = 91.16
REDUCTIONS = {2025: .02, 2030: .06, 2035: .145, 2040: .31, 2045: .62, 2050: .80}
# FuelEU Annex I refers to RED Annex V C(4); MRV/ETS uses different GWP100.
FUELEU_GWP_CH4 = 25.0
FUELEU_GWP_N2O = 298.0
ETS_GWP_CH4 = 28.0
ETS_GWP_N2O = 265.0
# Annex II FuelEU / Annex I MRV: fraction of fuel supplied, not of combusted fuel.
LNG_CONSUMERS = {
    "otto_medium": ("Otto dual-fuel · medium speed · 3.1% slip", .031),
    "otto_slow": ("Otto dual-fuel · slow speed · 1.7% slip", .017),
    "diesel_slow": ("Diesel dual-fuel · slow speed · 0.2% slip", .002),
    "lbsi": ("Lean-burn spark-ignited · 2.6% slip", .026),
}
SOURCES = [
    {"title": "European Commission · FuelEU banking and pooling guidance", "url": "https://transport.ec.europa.eu/document/download/d4426ccc-ef46-4292-8b6d-5bf7a620f5ba_en?filename=fueleu_guidance_document_for_shipping_companies.pdf#page=116", "detail": "Sections 11.2–11.3: banked surplus may be offered through a pool. This app restricts banks to their originating ship and settles only a fully covered modelled fleet; these are modelling limits."},
    {"title": "European Commission · ETS and MRV general guidance", "url": "https://climate.ec.europa.eu/document/download/31875b4f-39b9-4cde-a4e2-fbb8f65ee703_en?filename=policy_transport_shipping_gd1_maritime_en.pdf", "detail": "18 November 2025 revision: scope, LNG slip, separate CO2 zero-rating conditions and retained non-CO2 gases; sections 4.1, 4.7 and 5.2, Annex III."},
    {"title": "European Commission · FuelEU verification guidance", "url": "https://transport.ec.europa.eu/document/download/3b32fff7-c4c0-482c-8882-1ff8bf43648d_en?filename=Guidance_on_verification_for_the_FuelEU_Maritime_Regulation.pdf", "detail": "25 June 2026: verifier responsibilities, compliance balances and flexibility mechanisms. App evidence assertions do not replace verification or FuelEU database formalities."},
    {"title": "European Commission · FuelEU enforcement guidance", "url": "https://transport.ec.europa.eu/document/download/8522a7d4-3e8d-4e74-85e8-282f0050bd17_en?filename=Guidance_for_Member_State_enforcement_of_the_FuelEU_Maritime_Regulation.pdf", "detail": "25 June 2026: additional checks, penalties and documents of compliance. Enforcement and statutory filings remain outside this planning application."},
    {"title": "European Commission · Actual methane-slip guidelines", "url": "https://transport.ec.europa.eu/document/download/9573f03b-a821-46ee-8131-312832b4ca32_en?filename=guidelines_for_reporting_and_verification_actual_methane_cslip_ef.pdf", "detail": "Guidance for reporting and verification of measured tank-to-wake methane slip. The app implements selected default engine factors only; actual-factor assessment is separate."},
    {"title": "European Commission · FuelEU wind-assisted propulsion", "url": "https://transport.ec.europa.eu/document/download/d4426ccc-ef46-4292-8b6d-5bf7a620f5ba_en?filename=fueleu_guidance_document_for_shipping_companies.pdf#page=53", "detail": "Section 4.5, Table 4.12 and Annex I of Regulation 2023/1805: discrete wind intensity factors, separate from physical fuel savings; reviewed EEDI/EEXI Pwind and Pprop."},
    {"title": "European Commission · FuelEU GWP and RFNBO calculations", "url": "https://transport.ec.europa.eu/document/download/d4426ccc-ef46-4292-8b6d-5bf7a620f5ba_en?filename=fueleu_guidance_document_for_shipping_companies.pdf#page=38", "detail": "Sections 4.3.3 and 4.3.6: FuelEU CH4=25, N2O=298; RFNBO denominator reward through 2033. ETS retains CH4=28, N2O=265."},
    {"title": "European Commission · FuelEU annual prioritized allocation", "url": "https://transport.ec.europa.eu/document/download/d4426ccc-ef46-4292-8b6d-5bf7a620f5ba_en?filename=fueleu_guidance_document_for_shipping_companies.pdf#page=51", "detail": "8 October 2025 guidance, section 4.4, pages 51–52: optional annual attribution of MRV-eligible energy, including conventional fuels, to the Article 2 energy scope. The app minimizes attained intensity including the elected RFNBO reward; ETS remains separate."},
    {"title": "FuelEU Maritime · Regulation (EU) 2023/1805", "url": "https://eur-lex.europa.eu/eli/reg/2023/1805/oj/eng", "detail": "Articles 2, 4, 5, 6, 10, 20, 21, 23; Annexes I, II and IV."},
    {"title": "European Commission · FuelEU implementation guidance", "url": "https://transport.ec.europa.eu/transport-modes/maritime/decarbonising-maritime-transport-fueleu-maritime/questions-and-answers-regulation-eu-20231805-use-renewable-and-low-carbon-fuels-maritime-transport_en", "detail": "Scope, fuel evidence, ship-specific banking and pooling."},
    {"title": "European Commission · Maritime ETS FAQ", "url": "https://climate.ec.europa.eu/areas-action/transport-decarbonisation/reducing-emissions-shipping-sector/faq-maritime-transport-eu-emissions-trading-system-ets_en", "detail": "Reporting-year phase-in, greenhouse gases and proportional extra-EU scope."},
    {"title": "MRV emissions methods · Delegated Regulation (EU) 2023/2776", "url": "https://eur-lex.europa.eu/eli/reg_del/2023/2776/oj/eng", "detail": "CO2, methane, nitrous oxide and CO2-equivalent accounting."},
    {"title": "RFNBO renewable-electricity criteria · Regulation (EU) 2023/1184", "url": "https://eur-lex.europa.eu/eli/reg_del/2023/1184/oj/eng", "detail": "Production evidence, including applicable additionality and temporal/geographical correlation criteria."},
    {"title": "RFNBO lifecycle methodology · Regulation (EU) 2023/1185", "url": "https://eur-lex.europa.eu/eli/reg_del/2023/1185/oj/eng", "detail": "GHG-saving methodology and lifecycle carbon accounting; certificates must be reviewed outside this application."},
    {"title": "ETS alternative-fuel monitoring rules · Regulation (EU) 2024/2493", "url": "https://eur-lex.europa.eu/eli/reg_impl/2024/2493/oj/eng", "detail": "Separate qualifying conditions for RFNBO CO2 zero-rating under the ETS monitoring rules."},
    {"title": "EMSA · FuelEU technical introduction", "url": "https://www.emsa.europa.eu/we-do/sustainability/environment/reducing-emissions/download/7853/5238/23.html", "detail": "Regulatory treatment of onshore electricity and compliance technologies."},
]


def target(year):
    if isinstance(year, bool) or not isinstance(year, int) or not 2025 <= year <= 2050:
        raise ValueError("Reporting year must be between 2025 and 2050.")
    return REFERENCE_G * (1 - REDUCTIONS[max(y for y in REDUCTIONS if y <= year)])


def ets_phase(year):
    target(year)
    return .7 if year == 2025 else 1.0


def rfnbo_reward(year):
    target(year)
    return 2.0 if year <= 2033 else 1.0


def wind_factor(power_kw, propulsion_kw):
    """Annex I / Commission guidance Table 4.12; no rounding/interpolation."""
    from math import isfinite
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not isfinite(x)
           for x in (power_kw, propulsion_kw)) or power_kw < 0 or propulsion_kw <= 0:
        raise ValueError("Wind power must be nonnegative and propulsion power positive and finite.")
    ratio = power_kw / propulsion_kw
    return .95 if ratio >= .15 else .97 if ratio >= .10 else .99 if ratio >= .05 else 1.0


def penalty(deficit_t, attained_g, consecutive=1):
    if deficit_t <= 1e-9:
        return 0.0
    if attained_g <= 0 or consecutive < 1:
        raise ValueError("A deficit requires a positive attained intensity and penalty count.")
    return deficit_t * 1_000_000 / (attained_g * 41_000) * 2400 * (1 + (consecutive - 1) / 10)


def borrowing_limit(energy_mj, year):
    """Article 20(2), tonnes CO2e; borrowing is disclosed but not optimized."""
    return .02 * target(year) * energy_mj / 1_000_000
