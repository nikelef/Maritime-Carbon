"""Versioned planning rules. See docs/REGULATORY_BASIS.md for applicability."""
ENGINE_VERSION = "6.4.1"
RULESET_VERSION = "EU-2026-09-07"
CHECKED_ON = "2026-09-07"
REFERENCE_G = 91.16
REDUCTIONS = {2025: .02, 2030: .06, 2035: .145, 2040: .31, 2045: .62, 2050: .80}
GWP_CH4 = 28.0
GWP_N2O = 265.0
# Annex II FuelEU / Annex I MRV: fraction of fuel supplied, not of combusted fuel.
LNG_CONSUMERS = {
    "otto_medium": ("Otto dual-fuel · medium speed · 3.1% slip", .031),
    "otto_slow": ("Otto dual-fuel · slow speed · 1.7% slip", .017),
    "diesel_slow": ("Diesel dual-fuel · slow speed · 0.2% slip", .002),
    "lbsi": ("Lean-burn spark-ignited · 2.6% slip", .026),
}
SOURCES = [
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


def penalty(deficit_t, attained_g, consecutive=1):
    if deficit_t <= 1e-9:
        return 0.0
    if attained_g <= 0 or consecutive < 1:
        raise ValueError("A deficit requires a positive attained intensity and penalty count.")
    return deficit_t * 1_000_000 / (attained_g * 41_000) * 2400 * (1 + (consecutive - 1) / 10)


def borrowing_limit(energy_mj, year):
    """Article 20(2), tonnes CO2e; borrowing is disclosed but not optimized."""
    return .02 * target(year) * energy_mj / 1_000_000
