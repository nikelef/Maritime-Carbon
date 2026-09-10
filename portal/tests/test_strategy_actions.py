"""Report actual shore-power/pooling actions instead of policy permissions."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from portal.engine.calculator import compare, simulate, strategy_actions, strategy_names
from portal.engine.schema import Vessel
from portal.tests.test_fuel_eligibility import high_carbon_price_case
from portal.views import report_context, same_strategy_outcome


def shore_power_case():
    data = high_carbon_price_case(True, True)
    data.eua_price, data.pool_price = 85, 190
    data.vessels[0].ops_ready = True
    return data


class StrategyActionTests(SimpleTestCase):
    def test_matching_pooling_outcomes_are_one_option_and_old_links_select_it(self):
        data = shore_power_case()
        data.vessels[0].ops_ready = False
        data.vessels[0].fuel_capex = 2000  # Pooling wins even with leg-specific switching.
        result = compare(data)
        original = deepcopy(result)
        run = SimpleNamespace(results=result, inputs=data.to_dict(), scenario_name="Matching outcomes",
                              engine_version="6.4.1", ruleset_version="test", scenario_revision=1)
        for key in ("combined", "pool"):
            context = report_context(run, RequestFactory().get(f"/demo/?strategy={key}"))
            context["demo"] = True
            selected = context["selected"]
            self.assertEqual({s["key"] for s in selected["evaluations"]}, {"combined", "pool"})
            self.assertEqual(len(context["strategies"]), 3)
            self.assertEqual(len(context["chart_data"]["strategies"]), 3)
            self.assertEqual(selected["key"], context["strategies"][0]["key"])
            self.assertEqual(context["result"]["best_key"], selected["key"])
            self.assertTrue(selected["is_lowest"])
            self.assertEqual(selected["actions"]["name"], "Current sea fuels + external pooling")
            html = render_to_string("portal/report.html", context)
            self.assertIn("<strong>Current sea fuels + external pooling</strong>", html)
            self.assertEqual(html.count('<strong>Current sea fuels + external pooling</strong>'), 1)
            self.assertEqual(html.count('class="strategy-option '), 3)
            self.assertEqual(html.count('aria-current="true"'), 1)
            self.assertIn("2 evaluations selected this outcome", html)
            self.assertNotIn("Lowest · tied", html)
            self.assertNotIn("<strong>Fuel choices · pooling allowed</strong>", html)
            if key == "combined":
                self.assertIn("Fuel switching was evaluated; keeping the current sea fuels", html)
        distinct = report_context(run, RequestFactory().get("/demo/?strategy=fuel"))
        self.assertEqual(len(distinct["selected"]["evaluations"]), 1)
        self.assertFalse(distinct["selected"]["is_lowest"])
        self.assertEqual(result, original)

    def test_equal_cost_or_title_alone_does_not_make_outcomes_identical(self):
        data = shore_power_case()
        left = simulate(data, [(0, False)], True)
        for part in ("decisions", "annual", "rows"):
            with self.subTest(part=part):
                right = deepcopy(left)
                if part == "decisions":
                    right[part][0]["ops"] = True
                else:
                    right[part][0]["electricity_cost"] += 1
                self.assertFalse(same_strategy_outcome(left, right))

    def test_fuel_policies_stay_separate_if_operating_choice_or_any_cost_differs(self):
        data = shore_power_case()
        data.vessels[0].ops_ready = False
        original = compare(data)
        fuel = next(s for s in original["strategies"] if s["key"] == "fuel")
        combined = next(s for s in original["strategies"] if s["key"] == "combined")
        # Build an exactly identical outcome before varying one field. Separate
        # continuous searches may differ by floating-point rounding at a root.
        for field in ("decisions", "annual", "rows", "npv", "total"):
            combined[field] = deepcopy(fuel[field])
        self.assertTrue(same_strategy_outcome(fuel, combined))
        for difference in ("operating_choice", "leg", "breakdown", "npv", "total", "first_step"):
            with self.subTest(difference=difference):
                result = deepcopy(original)
                changed = next(s for s in result["strategies"] if s["key"] == "combined")
                if difference == "operating_choice":
                    changed["decisions"][0]["ops"] = True
                elif difference == "leg":
                    changed["decisions"][0]["leg_replacements"][0]["voyage"] = 2
                elif difference == "first_step":
                    changed["decisions"][0]["first_step_comparison"][0]["first_step_npv"] += 1
                elif difference == "breakdown":
                    # Equal totals do not imply an equal cost breakdown.
                    changed["annual"][0]["fuel_cost"] += 1
                    changed["annual"][0]["ets_cost"] -= 1
                else:
                    # Even a difference hidden by display rounding stays separate.
                    changed[difference] += .000001
                run = SimpleNamespace(results=result, inputs=data.to_dict())
                for key in ("fuel", "combined"):
                    context = report_context(run, RequestFactory().get(f"/demo/?strategy={key}"))
                    self.assertEqual(context["selected"]["key"], key)
                    self.assertEqual([s["key"] for s in context["selected"]["evaluations"]], [key])
                    self.assertEqual(len(context["strategies"]), 4)

    def test_disabled_shore_power_has_no_electricity_or_shore_power_policy_titles(self):
        data = shore_power_case()
        data.vessels[0].ops_ready = False
        result = compare(data)
        names = {s["key"]: s["name"] for s in result["strategies"]}
        self.assertEqual(names["fuel"], "Fuel choices")
        self.assertEqual(names["combined"], "Fuel choices · pooling allowed")
        for strategy in result["strategies"]:
            self.assertNotIn("shore-power", strategy["name"])
            self.assertFalse(any(d["ops"] for d in strategy["decisions"]))
            for row in strategy["annual"]:
                self.assertEqual(row["electricity_mwh"], 0)
                self.assertEqual(row["electricity_cost"], 0)
        for item in result["sensitivities"]:
            self.assertNotIn("shore-power", item["winner"])

    def test_mixed_fleet_keeps_shore_power_choices_for_enabled_ship(self):
        data = shore_power_case()
        data.vessels.insert(0, replace(data.vessels[0], name="Disabled ship", ops_ready=False))
        self.assertEqual(strategy_names(data)["fuel"], "Fuel & shore-power choices")
        result = compare(data)
        for strategy in result["strategies"]:
            self.assertFalse(strategy["decisions"][0]["ops"])
        self.assertTrue(any(s["decisions"][1]["ops"] for s in result["strategies"]))

    def test_saved_disabled_report_corrects_titles_and_sensitivities_without_mutation(self):
        data = shore_power_case()
        data.vessels[0].ops_ready = False
        result = compare(data)
        for strategy in result["strategies"]:
            if strategy["key"] in ("fuel", "combined"):
                strategy["name"] = strategy["name"].replace("Fuel choices", "Fuel & shore-power choices")
        result["sensitivities"][0]["winner"] = "Fuel & shore-power choices"
        original = deepcopy(result)
        run = SimpleNamespace(results=result, inputs=data.to_dict(), scenario_name="Disabled OPS case",
                              engine_version="6.4.1", ruleset_version="test", scenario_revision=1)
        context = report_context(run, RequestFactory().get("/demo/"))
        context["demo"] = True
        html = render_to_string("portal/report.html", context)
        self.assertNotIn("shore-power choices", html)
        self.assertEqual(context["result"]["sensitivities"][0]["winner"], next(s for s in context["strategies"] if s["key"] == "fuel")["display_name"])
        self.assertTrue(all("shore-power" not in s["name"] for s in context["chart_data"]["strategies"]))
        self.assertEqual(result, original)

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
        self.assertAlmostEqual(row["bank_close_t"], 17.51053482365166)
        self.assertAlmostEqual(fuel["npv"], 812083.053874269)

    def test_actual_external_pooling_remains_visible_without_shore_power(self):
        data = shore_power_case()
        result = simulate(data, [(0, False)], True)
        actions = strategy_actions(result)
        self.assertEqual(actions["name"], "Current sea fuels + external pooling")
        self.assertTrue(actions["pooling_used"])
        self.assertAlmostEqual(result["pool_cost"], actions["external_pool_t"] * 190)
        self.assertEqual(actions["electricity_mwh"], 0)
        self.assertAlmostEqual(result["npv"], 834421.0734035062)

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
        result = compare(data)
        self.assertEqual(result["best_key"], "baseline")
        original = deepcopy(result)
        run = SimpleNamespace(results=result, inputs=data.to_dict())
        for key in ("baseline", "pool", "fuel", "combined", "unknown"):
            context = report_context(run, RequestFactory().get(f"/demo/?strategy={key}"))
            self.assertEqual(len(context["strategies"]), 1)
            self.assertEqual(context["selected"]["key"], "baseline")
            self.assertEqual(len(context["selected"]["evaluations"]), 4)
            self.assertEqual(context["baseline"]["annual"], context["selected"]["annual"])
        self.assertEqual(result, original)

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
