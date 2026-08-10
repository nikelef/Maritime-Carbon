import unittest

from streamlit.testing.v1 import AppTest


class StrategySelectionUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = AppTest.from_file("app.py", default_timeout=120)
        cls.app.session_state["_authenticated"] = True
        cls.app.session_state["subscriber_name"] = "test"
        cls.app.session_state["subscription_plan"] = "test"
        cls.app.run(timeout=120)

    def _select_strategy(self, name: str) -> None:
        selector = next(widget for widget in self.app.selectbox if widget.label == "Strategy detail")
        selector.select(name)
        self.app.run(timeout=120)

    def _metric_value(self, label: str) -> str:
        metric = next(item for item in self.app.metric if item.label == label)
        return metric.value

    @staticmethod
    def _click_run_analysis(app: AppTest) -> None:
        next(button for button in app.button if button.label == "▶ Run analysis").click()
        app.run(timeout=120)

    def test_selected_strategy_controls_cockpit_and_pooling_values(self) -> None:
        self._select_strategy("Pay as-is")
        pay_as_is_npv = self._metric_value("Selected strategy NPV")
        pay_as_is_pool_need = self._metric_value("Pool buy need")

        self._select_strategy("Pool compliance")
        pool_compliance_npv = self._metric_value("Selected strategy NPV")
        pool_compliance_pool_need = self._metric_value("Pool buy need")

        self.assertNotEqual(pay_as_is_npv, pool_compliance_npv)
        self.assertEqual(pay_as_is_pool_need, "0 tCO2e")
        self.assertNotEqual(pool_compliance_pool_need, "0 tCO2e")

    def test_pooling_status_explains_noop_and_updates_when_deficit_exists(self) -> None:
        payload = {
            "fuels": [
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
            ],
            "segments": [
                {
                    "Segment": "Surplus case",
                    "Route scope": "Intra EU/EEA voyage",
                    "Annual trips": 1.0,
                    "Low-carbon first": False,
                    "OPS_MWh_trip": 0.0,
                    "HSFO_t_trip": 0.0,
                    "HVO_t_trip": 100.0,
                }
            ],
            "assumptions": {
                "start_year": 2026,
                "end_year": 2026,
                "discount_rate": 0.0,
                "eua_price": 82.0,
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
            },
            "settings": {
                "objective": "Total cost including fuel",
                "start_year": 2026,
                "end_year": 2026,
                "reduce_fuel": "HSFO",
                "candidate_alts": ["HVO"],
                "max_replace": 0.0,
                "replace_step": 0.15,
                "mix_step": 0.5,
                "include_ops": False,
            },
        }
        payload["settings"].update(payload["assumptions"])

        app = AppTest.from_file("app.py", default_timeout=120)
        app.session_state["_authenticated"] = True
        app.session_state["subscriber_name"] = "test"
        app.session_state["subscription_plan"] = "test"
        app.session_state["_pending_scenario_restore"] = payload
        app.run(timeout=120)

        strategy_table = next(
            item.value
            for item in app.dataframe
            if "Strategy" in item.value.columns and "Total_NPV_EUR" in item.value.columns
        ).set_index("Strategy")
        original_total = strategy_table.loc["Pay as-is", "Total_NPV_EUR"]
        self.assertEqual(strategy_table.loc["Pool compliance", "Pooling_Status"], "Not needed")
        self.assertEqual(strategy_table.loc["Pool compliance", "Pool_Bought_tCO2e"], 0.0)
        self.assertEqual(
            strategy_table.loc["Pay as-is", "Total_NPV_EUR"],
            strategy_table.loc["Pool compliance", "Total_NPV_EUR"],
        )
        self.assertTrue(
            any("same NPV because this horizon requires no pool purchase" in item.value for item in app.info)
        )

        app.session_state["segment_editor"] = {
            "edited_rows": {0: {"HSFO_t_trip": 100.0, "HVO_t_trip": 0.0}},
            "added_rows": [],
            "deleted_rows": [],
        }
        app.run(timeout=120)

        pending_strategy_table = next(
            item.value
            for item in app.dataframe
            if "Strategy" in item.value.columns and "Total_NPV_EUR" in item.value.columns
        ).set_index("Strategy")
        self.assertEqual(pending_strategy_table.loc["Pay as-is", "Total_NPV_EUR"], original_total)
        self.assertEqual(pending_strategy_table.loc["Pool compliance", "Pooling_Status"], "Not needed")
        self.assertTrue(any("Inputs have changed" in item.value for item in app.info))

        self._click_run_analysis(app)

        strategy_table = next(
            item.value
            for item in app.dataframe
            if "Strategy" in item.value.columns and "Total_NPV_EUR" in item.value.columns
        ).set_index("Strategy")
        self.assertEqual(strategy_table.loc["Pool compliance", "Pooling_Status"], "Used")
        self.assertGreater(strategy_table.loc["Pool compliance", "Pool_Bought_tCO2e"], 0.0)
        self.assertNotEqual(
            strategy_table.loc["Pay as-is", "Total_NPV_EUR"],
            strategy_table.loc["Pool compliance", "Total_NPV_EUR"],
        )
        self.assertFalse(
            any("same NPV because this horizon requires no pool purchase" in item.value for item in app.info)
        )

        deficit_total = strategy_table.loc["Pay as-is", "Total_NPV_EUR"]
        next(item for item in app.number_input if item.label == "EUA price [€/tCO2e]").set_value(200.0)
        app.run(timeout=120)

        pending_sidebar_table = next(
            item.value
            for item in app.dataframe
            if "Strategy" in item.value.columns and "Total_NPV_EUR" in item.value.columns
        ).set_index("Strategy")
        self.assertEqual(pending_sidebar_table.loc["Pay as-is", "Total_NPV_EUR"], deficit_total)
        self.assertTrue(any("Inputs have changed" in item.value for item in app.info))

        self._click_run_analysis(app)
        updated_sidebar_table = next(
            item.value
            for item in app.dataframe
            if "Strategy" in item.value.columns and "Total_NPV_EUR" in item.value.columns
        ).set_index("Strategy")
        self.assertNotEqual(updated_sidebar_table.loc["Pay as-is", "Total_NPV_EUR"], deficit_total)


if __name__ == "__main__":
    unittest.main()
