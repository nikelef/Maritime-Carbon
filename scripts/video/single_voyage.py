"""Owner-specified one-ship, one-voyage 2026 video case and narration."""
from pathlib import Path
from portal.engine.schema import ScenarioInput, Vessel

OUT = Path(__file__).resolve().parents[2] / "video-artifacts" / "single-voyage"
VOICE = "en-GB-RyanNeural"


def case_input():
    case = ScenarioInput(
        start_year=2026, end_year=2026, eua_price=85, pool_enabled=True, pool_price=190,
        pool_cap=100000, pool_reference="DEMO ONLY: assumed pooling offer; no live quotation.",
        scope_confirmed=True,
        scope_notes="One bulk carrier; Voyage 1; 2026 only. EU/non-EU and intra-EU sea legs. HSFO assumes approved sulphur-compliance arrangements.",
        vessels=[Vessel(name="Demo Atlas", ship_type="cargo", gt=25000, fuel="HSFO",
                  sea_t=0, berth_t=0, intra_share=0, extra_share=0, compatible=True,
                  alternative="HVO", max_blend=1, ops_ready=False, ops_fraction=0,
                  consumption=[{"voyage": 1, "fuel": "HSFO", "intra_t": 200, "extra_t": 1000},
                               {"voyage": 1, "fuel": "VLSFO", "intra_t": 50, "extra_t": 100},
                               {"voyage": 1, "fuel": "MGO", "intra_t": 50, "extra_t": 50,
                                "eu_berth_t": 30, "ops_share": 0}])],
    )
    hvo = next(f for f in case.fuels if f.code == "HVO")
    hvo.eligible = hvo.ets_eligible = True
    hvo.evidence = "DEMO ONLY: assumed eligible HVO pathway and separately confirmed ETS CO2 treatment. No real certificate."
    case.validate()
    return case


# Each shot has one stationary pointer target. Narration must finish before the
# next shot starts. The generous last-three-shot weights favour reading ledgers.
SHOTS = [
    ("year", "2026 only · One bulk carrier · Voyage 1", "Reporting year: twenty twenty-six only.", 3.5),
    ("vessel", "One bulk carrier: Demo Atlas", "One bulk carrier: Demo Atlas.", 3.5),
    ("eua", "EUA cost: €85/tCO₂e", "Allowance cost: eighty-five euros per tonne.", 3.5),
    ("pool", "Pooling cost: €190/tCO₂e of FuelEU balance", "Pooling: one hundred and ninety euros per tonne of compliance balance.", 4.5),
    ("voyage", "All consumption is assigned to Voyage 1", "Assign all consumption to Voyage one.", 3),
    ("extra_hsfo", "EU ↔ non-EU sea · HSFO: 1,000 t", "E U to non E U: one thousand tonnes of heavy fuel oil.", 4.5),
    ("extra_vlsfo", "EU ↔ non-EU sea · VLSFO: 100 t", "One hundred tonnes of very low sulphur fuel oil.", 3.5),
    ("extra_mgo", "EU ↔ non-EU sea · LSMGO: 50 t", "Fifty tonnes of low sulphur marine gas oil.", 3.5),
    ("intra_hsfo", "Intra-EU sea · HSFO: 200 t", "Intra E U: two hundred tonnes of heavy fuel oil.", 4),
    ("intra_vlsfo", "Intra-EU sea · VLSFO: 50 t", "Fifty tonnes of very low sulphur fuel oil.", 3.5),
    ("intra_mgo", "Intra-EU sea · LSMGO: 50 t", "Fifty tonnes of low sulphur marine gas oil.", 3.5),
    ("berth", "EU berth · LSMGO: 30 t · Shore power disabled", "At berth: thirty tonnes of low sulphur marine gas oil.", 4),
    ("hvo", "Alternative / replacement fuel: HVO", "H V O is the alternative replacement fuel.", 3.5),
    ("calculate", "Compare the available strategies", "Compare the available strategies.", 3.5),
    ("best", "Select the lowest evaluated cost: €1,001,422.09 for 2026", "Select the lowest evaluated cost strategy.", 4.5),
    ("operating", "03 / OPERATING CHOICE · Intra-EU: 26.252 t LSMGO → 25.476 t HVO", "Section three: replace gas oil with H V O on the intra E U leg.", 7),
    ("breakdown", "04 / COST BREAKDOWN · Fuel €764,436.56 + ETS €236,985.53", "Section four itemises the annual costs. No pooling or Fuel E U penalty remains.", 6.5),
    ("ledger", "SHIP-BY-SHIP LEDGER · Intensity, compliance balance and settlement", "Finally, the ship-by-ship ledger shows the intensity, compliance balance, and settlement.", 6.5),
]
