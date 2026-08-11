import base64
import json
import unittest

import numpy as np
from streamlit.testing.v1 import AppTest


def _decoded_array(value):
    if isinstance(value, dict) and "bdata" in value and "dtype" in value:
        return np.frombuffer(
            base64.b64decode(value["bdata"]),
            dtype=np.dtype(value["dtype"]),
        ).tolist()
    return value


def _exact_case_payload():
    fuels = [
        {
            "Code": "HSFO",
            "Fuel": "HSFO",
            "Family": "Fossil oil",
            "LCV_MJ_t": 40_200.0,
            "WtW_gCO2e_MJ": 91.6,
            "ETS_CO2_t_t": 3.114,
            "ETS_CH4_t_t": 0.00005,
            "ETS_N2O_t_t": 0.00018,
            "Price_EUR_t": 676.0,
            "Supply_cap_t": 0.0,
            "RFNBO": False,
            "ETS_zero_if_certified": False,
            "Color": "#1f2937",
        },
        {
            "Code": "MGO",
            "Fuel": "Marine gas oil",
            "Family": "Fossil oil",
            "LCV_MJ_t": 42_700.0,
            "WtW_gCO2e_MJ": 90.6,
            "ETS_CO2_t_t": 3.206,
            "ETS_CH4_t_t": 0.00005,
            "ETS_N2O_t_t": 0.00018,
            "Price_EUR_t": 1_200.0,
            "Supply_cap_t": 0.0,
            "RFNBO": False,
            "ETS_zero_if_certified": False,
            "Color": "#64748b",
        },
        {
            "Code": "FAME",
            "Fuel": "FAME HSFO BLEND",
            "Family": "NaN",
            "LCV_MJ_t": 41_855.0,
            "WtW_gCO2e_MJ": 47.0,
            "ETS_CO2_t_t": 2.24,
            "ETS_CH4_t_t": 0.00005,
            "ETS_N2O_t_t": 0.00018,
            "Price_EUR_t": 890.0,
            "Supply_cap_t": 5_000.0,
            "RFNBO": False,
            "ETS_zero_if_certified": True,
            "Color": "#65a30d",
        },
    ]
    segment_values = [
        ("1", "non-EU to EU voyage", 1_890.0, 5.0, 200.0),
        ("2", "EU berth / port stay", 0.0, 10.0, 0.0),
        ("3", "Intra EU/EEA voyage", 20.0, 5.0, 0.0),
        ("4", "EU berth / port stay", 0.0, 10.0, 0.0),
        ("5", "EU to non-EU voyage", 234.0, 0.0, 0.0),
    ]
    segments = [
        {
            "Segment": name,
            "Route scope": route_scope,
            "Annual trips": 1.0,
            "Low-carbon first": True,
            "OPS_MWh_trip": 0.0,
            "HSFO_t_trip": hsfo,
            "MGO_t_trip": mgo,
            "FAME_t_trip": fame,
        }
        for name, route_scope, hsfo, mgo, fame in segment_values
    ]
    assumptions = {
        "start_year": 2026,
        "end_year": 2026,
        "discount_rate": 0.0,
        "eua_price": 78.0,
        "eua_escalation": 0.0,
        "fuel_escalation": 0.0,
        "fueleu_penalty_vlsfo": 2_400.0,
        "pool_buy_price": 150.0,
        "pool_sell_price": 100.0,
        "pool_price_escalation": 0.0,
        "pool_cap_tco2e": 0.0,
        "gwp_ch4": 28.0,
        "gwp_n2o": 265.0,
        "ops_wtw_g_mj": 0.0,
        "ops_start_year": 2030,
        "ops_fraction": 0.85,
    }
    settings = {
        **assumptions,
        "objective": "Total cost including fuel",
        "reduce_fuel": "HSFO",
        "candidate_alts": ["FAME"],
        "max_replace": 1.0,
        "replace_step": 0.05,
        "mix_step": 0.1,
        "include_ops": False,
    }
    return {
        "fuels": fuels,
        "segments": segments,
        "assumptions": assumptions,
        "settings": settings,
    }


class CurrentTotalCostChartUITests(unittest.TestCase):
    def test_exact_export_surplus_reaches_regulatory_trace(self) -> None:
        app = AppTest.from_file("app.py", default_timeout=120)
        app.session_state["_authenticated"] = True
        app.session_state["subscriber_name"] = "test"
        app.session_state["subscription_plan"] = "test"
        app.session_state["_pending_scenario_restore"] = _exact_case_payload()
        app.run(timeout=120)

        self.assertEqual(list(app.exception), [])
        regulatory_table = next(
            item.value
            for item in app.dataframe
            if "Total Regulatory Cost EUR" in item.value.columns
        )
        total_row = regulatory_table.loc[regulatory_table["Segment"] == "TOTAL"].iloc[0]

        chart_spec = next(
            json.loads(chart.proto.spec)
            for chart in app.get("plotly_chart")
            if "Current Total Cost by Year" in json.loads(chart.proto.spec)["layout"]["title"]["text"]
        )
        regulatory_trace = next(
            trace for trace in chart_spec["data"] if trace.get("name") == "Regulatory cost"
        )
        rendered_value = float(_decoded_array(regulatory_trace["y"])[0])

        self.assertLess(float(total_row["FuelEU Cost EUR"]), 0.0)
        self.assertAlmostEqual(float(total_row["EU ETS Cost EUR"]), 273_935.1771, places=4)
        self.assertAlmostEqual(float(total_row["Total Regulatory Cost EUR"]), 86_246.112895, places=4)
        self.assertAlmostEqual(rendered_value, float(total_row["Total Regulatory Cost EUR"]), places=6)
        self.assertNotAlmostEqual(rendered_value, float(total_row["EU ETS Cost EUR"]), places=2)


if __name__ == "__main__":
    unittest.main()
