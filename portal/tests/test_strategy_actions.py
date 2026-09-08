"""Report actual shore-power/pooling actions instead of policy permissions."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from portal.engine.calculator import compare, simulate, strategy_actions
from portal.engine.schema import Vessel
from portal.tests.test_fuel_eligibility import high_carbon_price_case
from portal.views import report_context


def shore_power_case():
    data = high_carbon_price_case(True, True)
    data.eua_price, data.pool_price = 85, 190
    data.vessels[0].ops_ready = True
    return data


class StrategyActionTests(SimpleTestCase):
    def test_shore_power_removes_pool_need_and_non_pooling_policy_wins_tie(self):
        data = shore_power_case()
        result = compare(data)
        fuel = next(s for s in result["strategies"] if s["key"] == "fuel")
        combined = next(s for s in result["strategies"] if s["key"] == "combined")
        self.assertEqual(result["best_key"], "fuel")
        self.assertEqual(fuel["npv"], combined["npv"])
        self.assertEqual(fuel["decisions"], combined["decisions"])
        self.assertEqual(fuel["actions"]["name"], "Current sea fuels + shore power")
        self.assertFalse(combined["actions"]["pooling_used"])
        self.assertIn("No pooling is needed", combined["actions"]["pooling_note"])
        # 50 t EU berth MGO -> electrical output, allowing connection losses.
        expected_mwh = 50 * 42700 * .4 / .95 / 3600
        row = fuel["annual"][0]
        self.assertAlmostEqual(row["electricity_mwh"], expected_mwh)
        self.assertAlmostEqual(row["electricity_cost"], expected_mwh * 160)
        self.assertAlmostEqual(row["fuel_cost"], 1000 * 470 + 100 * 720 + 60 * 575)
        self.assertEqual(row["pool_cost"], 0)
        self.assertEqual(row["pool_buy_t"], 0)
        self.assertFalse(row["pool_used"])
        self.assertAlmostEqual(row["bank_close_t"], 17.096607663157567)
        self.assertAlmostEqual(fuel["npv"], 812083.053874269)

    def test_actual_external_pooling_remains_visible_without_shore_power(self):
        data = shore_power_case()
        result = simulate(data, [(0, False)], True)
        actions = strategy_actions(result)
        self.assertEqual(actions["name"], "Current sea fuels + external pooling")
        self.assertTrue(actions["pooling_used"])
        self.assertAlmostEqual(result["pool_cost"], actions["external_pool_t"] * 190)
        self.assertEqual(actions["electricity_mwh"], 0)
        self.assertAlmostEqual(result["npv"], 834499.719564)

    def test_zero_price_external_pool_is_identified_by_quantity(self):
        data = shore_power_case()
        data.pool_price = 0
        result = simulate(data, [(0, False)], True)
        self.assertEqual(result["pool_cost"], 0)
        actions = strategy_actions(result)
        self.assertTrue(actions["pooling_used"])
        self.assertGreater(actions["external_pool_t"], 0)
        self.assertIn("external pooling", actions["name"])

    def test_internal_pooling_can_be_used_without_external_cost(self):
        data = shore_power_case()
        data.pool_enabled = False
        data.vessels.append(replace(data.vessels[0], name="Second ship"))
        result = simulate(data, [(.3, False), (0, False)], True)
        actions = strategy_actions(result)
        self.assertEqual(result["pool_cost"], 0)
        self.assertEqual(actions["external_pool_t"], 0)
        self.assertGreater(actions["internal_pool_t"], 0)
        self.assertEqual(actions["name"], "Alternative sea fuels + fleet pooling")
        self.assertIn("Internal fleet pooling is used", actions["pooling_note"])

    def test_combined_internal_and_external_transfers_are_both_named(self):
        data = shore_power_case()
        first = Vessel(name="Donor", sea_t=1000, berth_t=0, intra_share=1, extra_share=0, compatible=True)
        data.vessels = [first, replace(first, name="Recipient")]
        result = simulate(data, [(.05, False), (0, False)], True)
        actions = strategy_actions(result)
        self.assertGreater(actions["internal_pool_t"], 0)
        self.assertGreater(actions["external_pool_t"], 0)
        self.assertEqual(actions["name"], "Alternative sea fuels + fleet and external pooling")

    def test_unavailable_pool_reports_penalties_instead_of_pooling(self):
        data = shore_power_case()
        data.pool_cap = 0
        result = simulate(data, [(0, False)], True)
        actions = strategy_actions(result)
        self.assertFalse(actions["pooling_used"])
        self.assertIn("settled with penalties", actions["pooling_note"])
        self.assertGreater(result["penalty_cost"], 0)

    def test_identical_reference_cost_still_prefers_baseline(self):
        data = shore_power_case()
        data.pool_enabled = False
        data.vessels[0].compatible = data.vessels[0].ops_ready = False
        self.assertEqual(compare(data)["best_key"], "baseline")

    def test_older_saved_report_gets_actual_actions_without_mutation(self):
        data = shore_power_case()
        result = compare(data)
        # Recreate the old policy title and alphabetical tie-break, without
        # changing the old ledger or replacing the saved winner on page load.
        result["best_key"] = "combined"
        result["strategies"].sort(key=lambda s: (s["npv"], s["key"] != "baseline", s["key"]))
        for strategy in result["strategies"]:
            strategy.pop("actions")
            if strategy["key"] == "combined":
                strategy["name"] = "Fuel choices & pooling"
        original = deepcopy(result)
        run = SimpleNamespace(results=result, inputs=data.to_dict(), scenario_name="Historical OPS case",
                              engine_version="6.4.1", ruleset_version="test", scenario_revision=1)
        context = report_context(run, RequestFactory().get("/demo/"))
        context["demo"] = True
        html = render_to_string("portal/report.html", context)
        self.assertIn("<h2>Current sea fuels + shore power</h2>", html)
        self.assertNotIn("<h2>Fuel choices &amp; pooling</h2>", html)
        self.assertIn("No pooling is needed", html)
        self.assertIn("Electricity cost comes from shore power", html)
        self.assertIn("€39,953", html)
        self.assertEqual(context["selected"]["key"], "combined")
        self.assertEqual(result, original)
        # Selecting the genuine pooling policy changes the headline and ledger.
        other = report_context(run, RequestFactory().get("/demo/?strategy=pool"))
        self.assertEqual(other["selected"]["actions"]["name"], "Current sea fuels + external pooling")
        self.assertEqual(other["selected"]["annual"][0]["electricity_cost"], 0)
