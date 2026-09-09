"""Fictional, reproducible two-vessel pitch case; no customer data."""
from portal.engine.schema import ScenarioInput, Vessel


def pitch_case():
    case = ScenarioInput(
        start_year=2026, end_year=2026, eua_price=85, pool_enabled=True,
        pool_price=190, pool_cap=100000,
        pool_reference="DEMO ONLY: illustrative planning offer, not a live quotation.",
        scope_confirmed=True,
        scope_notes="Illustrative 2026 fleet. Ordinary EU voyage scope. HSFO assumes approved sulphur-compliance arrangements.",
        vessels=[
            Vessel(name="Demo Atlas", gt=25000, fuel="HSFO", sea_t=0, berth_t=0,
                   intra_share=0, extra_share=0, compatible=True, alternative="HVO", max_blend=.1,
                   consumption=[{"voyage": 1, "fuel": "HSFO", "intra_t": 200, "extra_t": 800},
                                {"voyage": 1, "fuel": "MGO", "intra_t": 80, "extra_t": 20, "eu_berth_t": 50},
                                {"voyage": 1, "fuel": "VLSFO", "intra_t": 10, "extra_t": 50}]),
            Vessel(name="Demo Boreas", gt=32000, sea_t=0, berth_t=0,
                   intra_share=0, extra_share=0, compatible=True, alternative="HVO", max_blend=.1,
                   consumption=[{"voyage": 2, "fuel": "VLSFO", "intra_t": 70, "extra_t": 300},
                                {"voyage": 2, "fuel": "MGO", "intra_t": 40, "extra_t": 20, "eu_berth_t": 50}]),
        ],
    )
    hvo = next(f for f in case.fuels if f.code == "HVO")
    hvo.eligible = hvo.ets_eligible = True
    hvo.evidence = "DEMO ONLY: assumed eligible supplier pathway and separate ETS evidence. No real certificate."
    case.validate()
    return case
