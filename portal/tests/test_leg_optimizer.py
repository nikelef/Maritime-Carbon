"""Voyage-leg accounting and continuous quantity regression checks."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

from django.test import SimpleTestCase, RequestFactory
from django.template.loader import render_to_string

from portal.engine.calculator import compare, leg_demands, profile, saved_decision, simulate, optimize, share_grid, options
from portal.engine.leg_optimizer import leg_decision
from portal.tests.test_fuel_eligibility import high_carbon_price_case
from portal.views import report_context


def leg_case():
    data = high_carbon_price_case(True, True)
    data.eua_price, data.pool_price = 85, 190
    return data


class LegOptimizerTests(SimpleTestCase):
    def test_two_percent_grid_preserves_exact_vessel_limit(self):
        data = leg_case()
        data.vessels[0].max_blend = .075
        self.assertEqual(share_grid(.075), [0, .02, .04, .06, .075])
        self.assertEqual([d[0] for d in options(data.vessels[0], data)], [0, .02, .04, .06, .075])

    def test_targeted_deficit_closure_beats_pooling_and_is_reported(self):
        data = leg_case()
        result = compare(data)
        best = result["strategies"][0]
        output = best["decisions"][0]
        used = [d for d in output["leg_replacements"] if d["fraction"] > 0]
        self.assertEqual(len(used), 1)
        leg = used[0]
        self.assertEqual((leg["voyage"], leg["fuel"], leg["leg"]), (1, "MGO", "intra_t"))
        self.assertAlmostEqual(leg["replaced_t"], 21.875942678666977, places=6)
        self.assertAlmostEqual(leg["alternative_t"], 21.229608008615454, places=6)
        self.assertAlmostEqual(best["npv"], 833155.1155676048, places=5)
        self.assertLess(output["blend"], .05)
        self.assertEqual(best["pool_cost"], 0)
        self.assertEqual(best["penalty_cost"], 0)
        self.assertAlmostEqual(leg["replaced_t"]*42700, leg["alternative_t"]*44000)
        # Independent final-fuel inventory, with no optimizer decision applied.
        check = deepcopy(data)
        mgo = next(r for r in check.vessels[0].consumption if r["fuel"] == "MGO")
        mgo["intra_t"] -= leg["replaced_t"]
        check.vessels[0].consumption.append({"voyage": 1, "fuel": "HVO", "intra_t": leg["alternative_t"]})
        independent = simulate(check, [(0, False)], True)
        self.assertAlmostEqual(best["npv"], independent["npv"], places=5)
        run = SimpleNamespace(results=result, inputs=data.to_dict(), scenario_name="Leg regression",
                              engine_version="6.5.0", ruleset_version="test", scenario_revision=1)
        context = report_context(run, RequestFactory().get("/demo/")); context["demo"] = True
        html = render_to_string("portal/report.html", context)
        self.assertIn("Voyage 1 · Intra-EU sea: replace 21.876", html)
        self.assertIn("21.230 t/year of HVO", html)
        self.assertIn("data-leg-remarks", html)
        self.assertEqual(result["search_grid_percent"], 2)
        self.assertIn("Initial grid: 2% of total sea energy; leg-search grid: 2%", html)
        self.assertNotIn("leg selection is not optimized", html)
        self.assertEqual(len(context["strategies"]), 4)  # Section-03 first-step costs differ.

    def test_leg_energy_pilot_and_scope_preserved_with_different_efficiency(self):
        data = leg_case(); v = data.vessels[0]
        v.alternative_energy_ratio, v.alternative_pilot_share = .8, .02
        v.consumption = [{"voyage": 1, "fuel": "MGO", "intra_t": 80, "eu_berth_t": 50},
                         {"voyage": 2, "fuel": "MGO", "extra_t": 20, "outside_t": 10}]
        ds = leg_demands(v, data)
        choice = leg_decision(ds, {"2:MGO:extra_t": .5}, False)
        row = profile(v, data, 2026, *choice)
        selected = next(d for d in row["leg_replacements"] if d["fraction"])
        self.assertEqual(selected["replaced_t"], 10)
        self.assertAlmostEqual(selected["alternative_t"]*44000 + selected["pilot_t"]*42700, 10*42700*.8)
        self.assertAlmostEqual(row["energy_mj"], (80+50+10*.5)*42700 + 10*.5*42700*.8)
        self.assertEqual(row["berth_t"], 50)
        self.assertEqual(next(d for d in row["leg_replacements"] if d["key"] == "1:MGO:intra_t")["remaining_t"], 80)
        self.assertEqual(next(d for d in row["leg_replacements"] if d["key"] == "2:MGO:outside_t")["remaining_t"], 10)

    def test_fractional_supply_boundary_is_shared_across_ships(self):
        data = leg_case()
        data.vessels.append(replace(data.vessels[0], name="Second", consumption=deepcopy(data.vessels[0].consumption)))
        next(f for f in data.fuels if f.code == "HVO").supply_t = 7.123456
        result = optimize(data, True)
        self.assertAlmostEqual(sum(r["alternative_t"] for r in result["rows"]), 7.123456, places=5)
        self.assertLessEqual(sum(r["alternative_t"] for r in result["rows"]), 7.123456+1e-7)
        self.assertTrue(all(d["blend"] <= v.max_blend+1e-10 for d,v in zip(result["decisions"],data.vessels)))

    def test_full_ship_cap_can_be_concentrated_on_one_leg(self):
        data = leg_case(); data.vessels[0].max_blend = .01
        result = optimize(data, True)
        output = result["decisions"][0]
        self.assertAlmostEqual(output["blend"], .01)
        used = [d for d in output["leg_replacements"] if d["fraction"] > 1e-8]
        self.assertEqual([d["key"] for d in used], ["1:MGO:intra_t"])

    def test_sensitivity_reprices_saved_leg_allocation_over_horizon(self):
        data = leg_case(); data.end_year = 2028
        result = compare(data)
        changed = replace(data, fuels=[replace(f, price=f.price*1.2) if f.code == "HVO" else f for f in data.fuels])
        expected = min((simulate(changed, [saved_decision(d) for d in s["decisions"]], s["use_pool"])["npv"], s["name"])
                       for s in result["strategies"])
        actual = next(s for s in result["sensitivities"] if s["assumption"] == "Alternative fuel +20%")
        self.assertEqual((actual["npv"], actual["winner"]), expected)

    def test_unknown_leg_nonfinite_and_mismatched_energy_are_rejected(self):
        data = leg_case(); v = data.vessels[0]
        for blend, shares in ((0, {"9:MGO:intra_t": .1}), (0, {"1:MGO:intra_t": float("nan")}),
                              (0, {"1:MGO:intra_t": True}), (0, {"1:MGO:intra_t": 2}),
                              (.5, {"1:MGO:intra_t": .1})):
            with self.subTest(shares=shares), self.assertRaises(ValueError):
                profile(v, data, 2026, blend, False, None, shares)
