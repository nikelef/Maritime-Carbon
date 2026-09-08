"""Cost-driven source-fuel selection, accounting, and saved recommendations."""
import csv
import io
import json
from dataclasses import replace
from datetime import timedelta
from itertools import product

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.engine.calculator import (
    allocated_decision, allocation_options, compare, optimize, profile, sea_demands, simulate,
)
from portal.engine.schema import ScenarioInput, Vessel
from portal.models import AnalysisRun, Company, Membership, Scenario


def replacement_case():
    data = ScenarioInput(start_year=2026, end_year=2026, scope_confirmed=True,
                         vessels=[Vessel(name="Mixed source fuels", compatible=True, max_blend=.2,
                                         consumption=[{"fuel": "HSFO", "outside_t": 1000},
                                                      {"fuel": "MGO", "outside_t": 100}])])
    alternative = next(f for f in data.fuels if f.code == "HVO")
    alternative.eligible, alternative.evidence, alternative.price = True, "TEST pathway", 600
    data.validate()
    return data


class FuelReplacementTests(SimpleTestCase):
    def test_smaller_expensive_fuel_is_fully_replaced_within_ship_cap(self):
        data = replacement_case()
        result = optimize(data, False)
        decision = result["decisions"][0]
        self.assertEqual(decision["replacements"], {"HSFO": 0, "MGO": 1})
        self.assertAlmostEqual(decision["blend"], 100 * 42700 / (1000 * 40500 + 100 * 42700))
        self.assertLess(decision["blend"], .2)
        self.assertEqual(decision["replacement_priority"][0]["fuel"], "MGO")
        comparison = decision["first_step_comparison"]
        self.assertEqual([item["fuel"] for item in comparison], ["MGO", "HSFO"])
        self.assertGreater(comparison[0]["first_step_savings"], 0)
        self.assertLess(comparison[1]["first_step_savings"], 0)
        self.assertAlmostEqual(result["npv"], 1000 * 470 + 100 * 42700 / 44000 * 600)
        uniform = simulate(data, [(.2, False)])
        self.assertLess(result["npv"], uniform["npv"])

    def test_price_change_reverses_source_choice_and_fills_overall_cap(self):
        data = replacement_case()
        for fuel in data.fuels:
            if fuel.code in ("HSFO", "MGO"):
                fuel.price = {"HSFO": 900, "MGO": 450}[fuel.code]
        result = optimize(data, False)
        decision = result["decisions"][0]
        self.assertEqual(decision["replacements"]["MGO"], 0)
        self.assertAlmostEqual(decision["blend"], .2)
        self.assertAlmostEqual(decision["replacements"]["HSFO"], .2 * (1000 * 40500 + 100 * 42700) / (1000 * 40500))
        self.assertEqual(decision["replacement_priority"][0]["fuel"], "HSFO")

    def test_regulatory_cost_can_reverse_purchase_cost_priority(self):
        data = replacement_case()
        next(f for f in data.fuels if f.code == "HSFO").price = 900
        next(f for f in data.fuels if f.code == "MGO").price = 450
        self.assertEqual(optimize(data, False)["decisions"][0]["replacement_priority"][0]["fuel"], "HSFO")
        data.vessels[0].consumption[1] = {"fuel": "MGO", "intra_t": 100}
        data.eua_price = 1000
        decision = optimize(data, False)["decisions"][0]
        self.assertEqual(decision["replacements"]["MGO"], 1)
        self.assertEqual(decision["replacement_priority"][0]["fuel"], "MGO")

    def test_priority_compares_equal_energy_and_full_horizon_cost(self):
        data = replacement_case()
        data.end_year = 2028
        data.vessels[0].max_blend = 1
        data.vessels[0].fuel_capex = 1234
        next(f for f in data.fuels if f.code == "HVO").price = 100
        result = optimize(data, False)
        output = result["decisions"][0]
        self.assertEqual([item["fuel"] for item in output["replacement_priority"]], ["MGO", "HSFO"])
        energy = 1000 * 40500 + 100 * 42700
        for item in output["replacement_priority"]:
            lcv = {"MGO": 42700, "HSFO": 40500}[item["fuel"]]
            price = {"MGO": 720, "HSFO": 470}[item["fuel"]]
            annual_fuel = 1000 * 470 + 100 * 720 - energy * .05 / lcv * price + energy * .05 / 44000 * 100
            expected = sum((annual_fuel * (1 + data.fuel_escalation) ** year + (1234 if year == 0 else 0)) /
                           (1 + data.discount_rate) ** year for year in range(3))
            self.assertAlmostEqual(item["first_step_npv"], expected)

    def test_per_fuel_fraction_keeps_leg_mix_and_displaced_energy_scope(self):
        data = replacement_case()
        vessel = data.vessels[0]
        vessel.max_blend = 1
        vessel.alternative_energy_ratio, vessel.alternative_pilot_share = .8, .02
        vessel.consumption = [{"voyage": 1, "fuel": "HSFO", "intra_t": 100, "eu_berth_t": 30},
                              {"voyage": 2, "fuel": "HSFO", "extra_t": 200, "non_eu_berth_t": 40},
                              {"fuel": "MGO", "intra_t": 50, "outside_t": 50}]
        choice = allocated_decision(sea_demands(vessel, data), {"HSFO": .25, "MGO": 1}, False)
        row = profile(vessel, data, 2026, *choice)
        self.assertEqual([item["sea_t"] for item in row["baseline_fuels"]], [75, 150, 0])
        displaced = 75 * 40500 + 100 * 42700
        scoped_displaced = 50 * 40500 + 50 * 42700
        self.assertAlmostEqual(row["alternative_t"], displaced * .8 * .98 / 44000)
        self.assertAlmostEqual(row["pilot_t"], displaced * .8 * .02 / 42700)
        self.assertAlmostEqual(row["energy_mj"], (75 + 150 * .5 + 30) * 40500 + scoped_displaced * .8)
        self.assertEqual(row["berth_t"], 30)
        self.assertEqual(row["non_eu_berth_t"], 40)
        oil_factor = 3.114 + .00005 * 28 + .00018 * 265
        hvo_factor = .00005 * 28 + .00018 * 265
        mgo_factor = 3.206 + .00005 * 28 + .00018 * 265
        expected_ets = (75 + 150 * .5 + 30) * oil_factor
        expected_ets += scoped_displaced * .8 * (.98 / 44000 * hvo_factor + .02 / 42700 * mgo_factor)
        self.assertAlmostEqual(row["ets_t"], expected_ets)

    def test_legacy_pilot_and_table_pilot_are_counted_once(self):
        data = replacement_case()
        old = Vessel(sea_t=1000, pilot_t=25, berth_t=20, compatible=True, max_blend=1,
                     sea_fuels=[{"fuel": "MGO", "sea_t": 100}, {"fuel": "HSFO", "sea_t": 1000}])
        new = replace(old, consumption=old.consumption_entries())
        for vessel in (old, new):
            demand = sea_demands(vessel, data)
            self.assertEqual(demand["MGO"]["tonnes"], 125)
            choice = allocated_decision(demand, {"MGO": 1}, False)
            row = profile(vessel, data, 2026, *choice)
            self.assertEqual(row["fuel_tonnes"]["MGO"], 20)
            self.assertAlmostEqual(row["alternative_t"], 125 * 42700 / 44000)

    def test_pair_transfer_can_move_a_full_cap_to_the_cheaper_source(self):
        data = replacement_case()
        vessel = data.vessels[0]
        demands = sea_demands(vessel, data)
        choice = allocated_decision(demands, {"HSFO": .2 / demands["HSFO"]["weight"]}, False)
        candidates = allocation_options(vessel, data, choice)
        shifted = [d for d in candidates if abs(d[0] - .2) < 1e-9 and dict(d[2])["MGO"] == 1]
        self.assertTrue(shifted)
        self.assertLess(simulate(data, [shifted[0]])["npv"], simulate(data, [choice])["npv"])
        self.assertTrue(all(d[0] <= vessel.max_blend + 1e-10 for d in candidates))

    def test_two_fuel_result_matches_independent_exhaustive_grid(self):
        data = replacement_case()
        # Equal energy streams give a simple independent rectangular 5% grid.
        data.vessels[0].consumption = [{"fuel": "HSFO", "intra_t": 427}, {"fuel": "MGO", "extra_t": 405}]
        data.vessels[0].max_blend = .3
        data.end_year = 2028
        trials = []
        for a, b in product(range(7), repeat=2):
            if a + b <= 6:
                trials.append(simulate(data, [((a+b) / 20, False, (("HSFO", a/10), ("MGO", b/10)))])["npv"])
        best = optimize(data, False)
        self.assertAlmostEqual(best["npv"], min(trials))
        self.assertEqual(best, optimize(data, False))

    def test_supply_limit_is_shared_between_vessels(self):
        data = replacement_case()
        data.vessels.append(replace(data.vessels[0], name="Second ship"))
        fuel = next(f for f in data.fuels if f.code == "HVO")
        fuel.supply_t = 100 * 42700 / 44000
        result = optimize(data, False)
        self.assertLessEqual(sum(row["alternative_t"] for row in result["rows"]), fuel.supply_t + 1e-7)
        self.assertAlmostEqual(sum(d["replacements"]["MGO"] for d in result["decisions"]), 1)

    def test_no_switch_when_costlier_unavailable_or_no_sea_demand(self):
        for mode in ("expensive", "incompatible", "uncertified", "zero_supply", "berth_only"):
            with self.subTest(mode=mode):
                data = replacement_case()
                fuel = next(f for f in data.fuels if f.code == "HVO")
                if mode == "expensive":
                    fuel.price = 5000
                elif mode == "incompatible":
                    data.vessels[0].compatible = False
                elif mode == "uncertified":
                    fuel.eligible = False
                elif mode == "zero_supply":
                    fuel.supply_t = 0
                else:
                    data.vessels[0].consumption = [{"fuel": "MGO", "eu_berth_t": 100}]
                output = optimize(data, False)["decisions"][0]
                self.assertEqual(output["blend"], 0)
                self.assertEqual(output["replacement_priority"], [])

    def test_current_alternative_is_retained_without_replacing_itself(self):
        data = replacement_case()
        data.vessels[0].consumption.append({"fuel": "HVO", "outside_t": 50})
        output = optimize(data, False)["decisions"][0]
        self.assertEqual(output["replacements"]["HVO"], 0)
        self.assertEqual(output["replacements"]["MGO"], 1)

    def test_invalid_allocations_are_rejected(self):
        data = replacement_case()
        for blend, fractions in ((.1, {"MGO": 1}), (0, {"missing": 0}),
                                 (0, {"MGO": float("nan")}), (0, {"MGO": True}),
                                 (0, {"MGO": "1"}), (0, {"MGO": -1}), (float("nan"), {})):
            with self.subTest(blend=blend, fractions=fractions), self.assertRaises(ValueError):
                profile(data.vessels[0], data, 2026, blend, replacements=fractions)

    def test_sensitivities_reprice_the_selected_per_fuel_allocations(self):
        data = replacement_case()
        result = compare(data)
        changed = replace(data, fuels=[replace(f, price=f.price * 1.2) if f.code == "HVO" else f for f in data.fuels])
        repriced = []
        for strategy in result["strategies"]:
            choices = [(d["blend"], d["ops"], tuple(sorted(d["replacements"].items()))) for d in strategy["decisions"]]
            repriced.append((simulate(changed, choices, strategy["use_pool"])["npv"], strategy["name"]))
        sensitivity = next(item for item in result["sensitivities"] if item["assumption"] == "Alternative fuel +20%")
        self.assertEqual((sensitivity["npv"], sensitivity["winner"]), min(repriced))


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class FuelReplacementReportTests(TestCase):
    def setUp(self):
        company = Company.objects.create(name="Replacement tests", status="active", access_until=timezone.localdate()+timedelta(days=30))
        user = get_user_model().objects.create_user("replacement_analyst")
        Membership.objects.create(company=company, user=user, role="analyst")
        self.client.force_login(user)
        data = replacement_case()
        self.scenario = Scenario.objects.create(company=company, name="Fuel priority", created_by=user, inputs=data.to_dict())
        response = self.client.post(reverse("run_analysis", args=[self.scenario.pk]), {"revision": 1})
        self.assertEqual(response.status_code, 302)
        self.run = AnalysisRun.objects.get(scenario=self.scenario)

    def test_report_and_audit_exports_retain_cost_selected_quantities(self):
        response = self.client.get(reverse("report", args=[self.run.pk]), {"strategy": "fuel"})
        for text in ("Replace MGO first", "Replace 100% of MGO: 100.0 t/year", "Keep HSFO: 1,000.0 t/year",
                     "Add 97.0 t/year of HVO", "leg selection is not optimized",
                     "Compare first-step costs", "Lower fleet present cost is better"):
            self.assertContains(response, text)
        audit = json.loads(self.client.get(reverse("export_run", args=[self.run.pk, "json"])).content)
        strategy = next(s for s in audit["results"]["strategies"] if s["key"] == "fuel")
        self.assertEqual(strategy["decisions"][0]["replacement_priority"][0]["fuel"], "MGO")
        rows = list(csv.DictReader(io.StringIO(self.client.get(reverse("export_run", args=[self.run.pk, "csv"])).content.decode("utf-8-sig"))))
        row = next(row for row in rows if row["strategy"] == strategy["name"] and row["vessel"] == "Mixed source fuels")
        replacements = {item["fuel"]: item for item in json.loads(row["sea_fuel_replacements_json"])}
        self.assertEqual(replacements["MGO"]["replaced_t"], 100)
        self.assertEqual(replacements["HSFO"]["replaced_t"], 0)

    def test_saved_legacy_result_discloses_original_uniform_allocation(self):
        for strategy in self.run.results["strategies"]:
            for decision in strategy["decisions"]:
                for field in ("fuel_replacements", "replacement_priority", "replacements"):
                    decision.pop(field, None)
        legacy = AnalysisRun.objects.create(
            company=self.run.company, scenario=self.scenario, scenario_name=self.run.scenario_name,
            scenario_revision=1, inputs=self.run.inputs, results=self.run.results,
            input_digest=self.run.input_digest, engine_version="6.3.0", ruleset_version=self.run.ruleset_version,
            created_by=self.run.created_by)
        response = self.client.get(reverse("report", args=[legacy.pk]), {"strategy": "fuel"})
        self.assertContains(response, "of each current sea fuel (saved calculation)")
        self.assertNotContains(response, "Replace MGO first")
