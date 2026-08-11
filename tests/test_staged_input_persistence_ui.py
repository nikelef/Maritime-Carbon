import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest


def minimal_fuels() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Code": "HSFO",
                "Fuel": "HSFO",
                "Family": "Fossil oil",
                "LCV_MJ_t": 40_200.0,
                "WtW_gCO2e_MJ": 93.3,
                "ETS_CO2_t_t": 3.114,
                "ETS_CH4_t_t": 0.00005,
                "ETS_N2O_t_t": 0.00018,
                "Price_EUR_t": 470.0,
                "Supply_cap_t": 0.0,
                "RFNBO": False,
                "ETS_zero_if_certified": False,
                "Color": "#1f2937",
            },
            {
                "Code": "HVO",
                "Fuel": "HVO renewable diesel",
                "Family": "Certified biofuel",
                "LCV_MJ_t": 37_000.0,
                "WtW_gCO2e_MJ": 14.0,
                "ETS_CO2_t_t": 0.0,
                "ETS_CH4_t_t": 0.0,
                "ETS_N2O_t_t": 0.0,
                "Price_EUR_t": 1_580.0,
                "Supply_cap_t": 6_000.0,
                "RFNBO": False,
                "ETS_zero_if_certified": True,
                "Color": "#16a34a",
            },
        ]
    )


def minimal_segments() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Segment": "Persistence probe",
                "Route scope": "Intra EU/EEA voyage",
                "Annual trips": 1.0,
                "Low-carbon first": False,
                "OPS_MWh_trip": 0.0,
                "HSFO_t_trip": 100.0,
                "HVO_t_trip": 0.0,
            }
        ]
    )


class StagedInputPersistenceUITests(unittest.TestCase):
    def make_app(self) -> AppTest:
        app = AppTest.from_file("app.py", default_timeout=120)
        state = app.session_state
        state["_authenticated"] = True
        state["subscriber_name"] = "test"
        state["subscription_plan"] = "test"
        state["_fuel_library_version"] = "expanded-biofuels-v1"
        state["_hsfo_option_version"] = "plain-hsfo-v2"
        state["_fuel_editor_revision"] = 0
        state["fuels_df"] = minimal_fuels()
        state["segments_df"] = minimal_segments()
        state["objective"] = "Total cost including fuel"
        state["start_year_v2"] = 2026
        state["end_year_v2"] = 2026
        state["reduce_fuel"] = "HSFO"
        state["candidate_alts_raw"] = ["HVO"]
        state["max_replace"] = 0.0
        state["replace_step"] = 0.15
        state["mix_step"] = 0.5
        state["include_ops"] = False
        app.run(timeout=120)
        self.assertFalse(app.exception)
        return app

    @staticmethod
    def click_run_analysis(app: AppTest) -> None:
        next(button for button in app.button if button.label == "▶ Run analysis").click()
        app.run(timeout=120)

    def test_first_edits_remain_draft_until_run_analysis(self) -> None:
        app = self.make_app()
        initial_editor_ids = [element.proto.id for element in app.dataframe[:2]]
        applied = app.session_state["_analysis_snapshot"]
        self.assertEqual(float(applied["segments_df"].loc[0, "Annual trips"]), 1.0)
        self.assertEqual(float(applied["fuels_df"].loc[0, "Price_EUR_t"]), 470.0)
        self.assertEqual(float(applied["settings"]["eua_price"]), 82.0)

        app.session_state["segment_editor"] = {
            "edited_rows": {0: {"Annual trips": 77.0}},
            "added_rows": [],
            "deleted_rows": [],
        }
        app.run(timeout=120)
        self.assertEqual([element.proto.id for element in app.dataframe[:2]], initial_editor_ids)
        self.assertEqual(float(app.session_state["segments_df"].loc[0, "Annual trips"]), 77.0)
        self.assertEqual(
            float(app.session_state["_analysis_snapshot"]["segments_df"].loc[0, "Annual trips"]),
            1.0,
        )

        next(
            widget for widget in app.number_input if widget.label == "EUA price [€/tCO2e]"
        ).set_value(123.0)
        app.run(timeout=120)
        self.assertEqual([element.proto.id for element in app.dataframe[:2]], initial_editor_ids)
        self.assertEqual(float(app.session_state["eua_price"]), 123.0)
        self.assertEqual(float(app.session_state["segments_df"].loc[0, "Annual trips"]), 77.0)
        self.assertEqual(float(app.session_state["_analysis_snapshot"]["settings"]["eua_price"]), 82.0)

        app.session_state["fuel_editor_plain_hsfo_0"] = {
            "edited_rows": {0: {"Price_EUR_t": 555.0}},
            "added_rows": [],
            "deleted_rows": [],
        }
        app.run(timeout=120)
        self.assertEqual([element.proto.id for element in app.dataframe[:2]], initial_editor_ids)
        self.assertEqual(float(app.session_state["fuels_df"].loc[0, "Price_EUR_t"]), 555.0)
        self.assertEqual(
            float(app.session_state["_analysis_snapshot"]["fuels_df"].loc[0, "Price_EUR_t"]),
            470.0,
        )

        app.run(timeout=120)
        self.assertEqual([element.proto.id for element in app.dataframe[:2]], initial_editor_ids)
        self.assertEqual(float(app.session_state["sidebar_price_HSFO"]), 555.0)
        self.assertEqual(float(app.session_state["fuels_df"].loc[0, "Price_EUR_t"]), 555.0)

        app.session_state["fuel_editor_plain_hsfo_0"] = {
            "edited_rows": {0: {"Price_EUR_t": 580.0}},
            "added_rows": [],
            "deleted_rows": [],
        }
        app.run(timeout=120)
        self.assertEqual([element.proto.id for element in app.dataframe[:2]], initial_editor_ids)
        self.assertEqual(float(app.session_state["fuels_df"].loc[0, "Price_EUR_t"]), 580.0)

        next(
            widget for widget in app.number_input if widget.label == "HSFO price [€/t]"
        ).set_value(610.0)
        app.run(timeout=120)
        rebased_editor_ids = [element.proto.id for element in app.dataframe[:2]]
        self.assertNotEqual(rebased_editor_ids[0], initial_editor_ids[0])
        self.assertEqual(rebased_editor_ids[1], initial_editor_ids[1])
        self.assertEqual(float(app.session_state["fuels_df"].loc[0, "Price_EUR_t"]), 610.0)
        self.assertEqual(int(app.session_state["_fuel_editor_revision"]), 1)
        self.assertEqual(
            float(app.session_state["_analysis_snapshot"]["fuels_df"].loc[0, "Price_EUR_t"]),
            470.0,
        )
        self.assertTrue(any("Inputs have changed" in item.value for item in app.info))

        self.click_run_analysis(app)
        self.assertEqual([element.proto.id for element in app.dataframe[:2]], rebased_editor_ids)
        applied = app.session_state["_analysis_snapshot"]
        self.assertEqual(float(applied["segments_df"].loc[0, "Annual trips"]), 77.0)
        self.assertEqual(float(applied["fuels_df"].loc[0, "Price_EUR_t"]), 610.0)
        self.assertEqual(float(applied["settings"]["eua_price"]), 123.0)
        self.assertFalse(any("Inputs have changed" in item.value for item in app.info))


if __name__ == "__main__":
    unittest.main()
