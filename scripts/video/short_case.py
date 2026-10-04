"""Fictional, reproducible FAME and shore-power example for the one-minute film."""
from pathlib import Path

from portal.engine.schema import ScenarioInput, Vessel

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "video-artifacts" / "one-minute"


def short_case():
    data = ScenarioInput(
        start_year=2026, end_year=2026, eua_price=90,
        electricity_price=140, pool_enabled=True, pool_price=250, pool_cap=1000,
        pool_reference="FICTIONAL DEMO: assumed external surplus at EUR 250/tCO2e of compliance balance.",
        scope_confirmed=True,
        scope_notes="FICTIONAL DEMO: ordinary EU scope; annual consumption grouped in Voyage 1. Prices are illustrative.",
        vessels=[Vessel(
            name="Demo Aurora", ship_type="cargo", gt=30000,
            sea_t=0, berth_t=0, intra_share=0, extra_share=0,
            consumption=[
                {"voyage": 1, "fuel": "VLSFO", "intra_t": 400, "extra_t": 1000},
                {"voyage": 1, "fuel": "MGO", "intra_t": 50, "extra_t": 50,
                 "eu_berth_t": 40, "ops_share": .75},
            ],
            alternative="FAME", compatible=True, max_blend=.2,
            ops_ready=True, ops_fraction=.75, generator_efficiency=.4,
            ops_efficiency=.95, ops_capex=0, ops_annual=2000,
            technical_reference="FICTIONAL DEMO: FAME compatibility assumed reviewed; shore-power connection already installed, with no new capital cost.",
        )],
    )
    fame = next(fuel for fuel in data.fuels if fuel.code == "FAME")
    fame.price = 1050
    fame.wtw = 25
    fame.eligible = fame.ets_eligible = True
    fame.evidence = "FICTIONAL DEMO: assumed eligible non-food/feed FAME pathway and separate ETS zero-rating. No real certificate."
    data.validate()
    return data


if __name__ == "__main__":
    import json
    from portal.engine.calculator import compare
    from portal.engine.rules import ENGINE_VERSION, RULESET_VERSION
    data = short_case()
    result = compare(data)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "prepared-case.json").write_text(json.dumps(dict(
        engine_version=ENGINE_VERSION, ruleset_version=RULESET_VERSION,
        inputs=data.to_dict(), results=result), indent=2), encoding="utf-8")
    for option in result["strategies"]:
        row = option["rows"][0]
        print(json.dumps({"key": option["key"], "npv": option["npv"],
            "actions": option["actions"], "fame_t": row["alternative_t"],
            "electricity_mwh": row["electricity_mwh"], "penalty": row["penalty_cost"],
            "attained": row["attained_g"], "legs": row["leg_replacements"]}))
