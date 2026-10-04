"""Optional GA routing, physical feasibility, non-regression and exact small oracle."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from itertools import product
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.engine.calculator import compare, optimize, saved_decision, simulate
from portal.engine.ga_optimizer import GASettings, _FleetSearch, optimize_hybrid
from portal.engine.leg_optimizer import optimize_legs
from portal.engine.schema import ScenarioInput, Vessel
from portal.models import AnalysisRun, Company, Membership, Scenario
from portal.tests.test_alternative_fuels import reviewed_case
from portal.tests.test_fuel_eligibility import high_carbon_price_case
from portal.tests.test_wind import wind_case


def joint_equipment_case():
    """A pooling threshold where the old coordinate search misses two OPS choices."""
    return ScenarioInput(start_year=2030, end_year=2030, scope_confirmed=True,
        pool_enabled=True, pool_price=100, pool_cap=416.55, pool_reference="TEST",
        electricity_price=250, vessels=[
            Vessel(name=f"Ship {i+1}", ops_ready=True, ops_capex=capex,
                   consumption=[dict(fuel="MGO", intra_t=sea, eu_berth_t=berth)])
            for i, (capex, sea, berth) in enumerate([
                (58000, 1280, 198), (91100, 1198, 21), (68900, 497, 124), (56400, 252, 112)])])


class GeneticOptimizerTests(SimpleTestCase):
    def test_off_uses_only_original_search_and_has_identical_results(self):
        data = joint_equipment_case()
        original = deepcopy(data.to_dict())
        with patch("portal.engine.ga_optimizer.optimize_hybrid", side_effect=AssertionError("GA called while off")):
            default = compare(data)
            explicit_off = compare(data, ga_enabled=False)
        self.assertEqual(default, explicit_off)
        self.assertFalse(any("ga_search" in s for s in default["strategies"]))
        self.assertEqual(data.to_dict(), original)

    def test_joint_ga_improvement_matches_exhaustive_equipment_oracle(self):
        data = joint_equipment_case()
        data.validate()
        old = optimize(data, True)
        # This case has exactly four binary decisions: independently enumerate all 16.
        oracle_cost, oracle_ops = min(
            (simulate(data, [(0, ops) for ops in bits], True)["npv"], bits)
            for bits in product((False, True), repeat=4))
        result = optimize_hybrid(data, True)
        self.assertGreater(old["npv"] - result["npv"], 6000)
        self.assertAlmostEqual(result["npv"], oracle_cost, places=6)
        self.assertEqual(tuple(d["ops"] for d in result["decisions"]), oracle_ops)
        self.assertEqual(result["ga_search"]["incumbent_npv"], old["npv"])
        self.assertEqual(result["ga_search"]["improvement_npv"], old["npv"] - result["npv"])
        self.assertTrue(all("leg_remarks" in d and "replacement_priority" in d for d in result["decisions"]))
        replay = simulate(data, [saved_decision(d) for d in result["decisions"]], True)
        self.assertEqual(result["rows"], replay["rows"])
        self.assertEqual(result["annual"], replay["annual"])

    def test_on_keeps_policy_layout_baselines_and_never_worsens_any_strategy(self):
        data = joint_equipment_case()
        off = {s["key"]: s for s in compare(data)["strategies"]}
        on = compare(data, ga_enabled=True)
        self.assertEqual(set(off), {s["key"] for s in on["strategies"]})
        for strategy in on["strategies"]:
            key = strategy["key"]
            self.assertLessEqual(strategy["npv"], off[key]["npv"])
            if key in ("baseline", "pool"):
                self.assertEqual(strategy, off[key])
            else:
                self.assertEqual(set(strategy) - set(off[key]), {"ga_search"})
        self.assertTrue(any(w.startswith("GA On:") for w in on["warnings"]))

    def test_supply_repair_respects_shared_caps_pilot_and_original_blend_weights(self):
        data = high_carbon_price_case(True, True)
        v = data.vessels[0]
        v.max_blend, v.alternative_energy_ratio, v.alternative_pilot_share = .075, .8, .02
        v.fuel_systems_confirmed, v.technical_reference = True, "TEST"
        data.vessels.append(deepcopy(v))
        data.vessels[1].name = "Second ship"
        alternative = next(f for f in data.fuels if f.code == "HVO")
        alternative.supply_t = 7.123456
        data.validate()
        original = deepcopy(data.to_dict())
        search = _FleetSearch(data, True, GASettings())
        raw = tuple(search.choice(i, {k: 1 for k in keys}) for i, keys in enumerate(search.keys))
        self.assertIsNone(simulate(data, raw, True))
        score, repaired = search.evaluate(raw)
        result = simulate(data, repaired, True)
        self.assertEqual(score, result["npv"])
        self.assertAlmostEqual(sum(r["fuel_tonnes"].get("HVO", 0) for r in result["rows"]), alternative.supply_t, places=6)
        self.assertTrue(all(d[0] <= .075 + 1e-10 for d in repaired))
        for row in result["rows"]:
            for leg in row["leg_replacements"]:
                self.assertAlmostEqual(leg["alternative_t"] * alternative.lcv + leg["pilot_t"] * 42700,
                                       leg["replaced_energy_mj"] * .8, places=6)
        self.assertEqual(data.to_dict(), original)
        alternative.supply_t = 0
        zero = _FleetSearch(data, True, GASettings()).evaluate(raw)[1]
        self.assertTrue(all(d[0] == 0 for d in zero))

    def test_all_generated_choices_respect_eligibility_readiness_and_wind(self):
        data = high_carbon_price_case(False, False)
        blocked = data.vessels[0]
        data.vessels.extend([replace(blocked, name="Incompatible", compatible=False),
                             replace(blocked, name="No blend", max_blend=0)])
        search = _FleetSearch(data, False, GASettings())
        for _ in range(20):
            left, right = search.random_plan(), search.random_plan()
            plan = search.offspring(left, right)
            self.assertTrue(all(d[0] == 0 and not d[1] and not (len(d) > 4 and d[4]) for d in plan))
            self.assertIsNotNone(simulate(data, plan))
        # Eligible fuel still cannot bypass either vessel compatibility or a zero cap.
        hvo = next(f for f in data.fuels if f.code == "HVO")
        hvo.eligible, hvo.evidence = True, "TEST"
        search = _FleetSearch(data, False, GASettings())
        for i in (1, 2):
            self.assertEqual(search.choice(i, {k: 1 for k in search.demands[i]}, True, True)[0], 0)

    def test_wind_and_ops_candidates_use_original_calculator_and_caps(self):
        data = wind_case()
        data.end_year = 2031
        v = data.vessels[0]
        v.compatible, v.ops_ready = True, True
        hvo = next(f for f in data.fuels if f.code == "HVO")
        hvo.eligible, hvo.evidence, hvo.supply_t = True, "TEST", 12.5
        data.validate()
        original = deepcopy(data.to_dict())
        old, result = optimize(data, True), optimize_hybrid(data, True)
        self.assertLessEqual(result["npv"], old["npv"])
        replay = simulate(data, [saved_decision(d) for d in result["decisions"]], True)
        self.assertEqual(result["rows"], replay["rows"])
        self.assertTrue(result["decisions"][0]["wind_selected"])
        self.assertTrue(all(r["fuel_tonnes"].get("HVO", 0) <= 12.5 + 1e-7 for r in result["rows"]))
        self.assertEqual(data.to_dict(), original)

    def test_rfnbo_reward_change_banks_and_streaks_are_replayed_over_full_horizon(self):
        data = reviewed_case("E_DIESEL")
        data.start_year, data.end_year = 2033, 2034
        data.rfnbo_subtarget, data.rfnbo_penalty_pd, data.rfnbo_reference = "assume_active", 2000, "TEST"
        data.vessels[0].opening_bank, data.vessels[0].prior_penalties = 15, 2
        next(f for f in data.fuels if f.code == "E_DIESEL").supply_t = 20
        data.validate()
        old = optimize(data, True)
        result = optimize_hybrid(data, True)
        self.assertLessEqual(result["npv"], old["npv"])
        replay = simulate(data, [saved_decision(d) for d in result["decisions"]], True)
        self.assertEqual(result["npv"], replay["npv"])
        self.assertEqual(result["rows"], replay["rows"])
        self.assertEqual([a["year"] for a in result["annual"]], [2033, 2034])

    def test_seeded_refinement_keeps_precise_leg_allocation_and_does_not_repeat_coarse_search(self):
        data = high_carbon_price_case(True, True)
        seed = optimize(data, True)
        with patch("portal.engine.leg_optimizer.optimize_fuels", side_effect=AssertionError("Coarse search repeated")):
            refined = optimize_legs(data, True, initial_result=seed)
        self.assertLessEqual(refined["npv"], seed["npv"] + 1e-6)
        self.assertEqual(refined["decisions"], seed["decisions"])

    def test_fixed_seed_reproduces_search_and_zero_budget_retains_incumbent(self):
        data = joint_equipment_case()
        settings = GASettings(population_size=24, generations=8, time_limit_s=60)
        first = optimize_hybrid(data, True, settings=settings)
        self.assertEqual(first, optimize_hybrid(data, True, settings=settings))
        fallback = optimize_hybrid(data, True, settings=replace(settings, time_limit_s=0))
        old = optimize(data, True)
        self.assertEqual(fallback["decisions"], old["decisions"])
        self.assertEqual(fallback["npv"], old["npv"])
        self.assertEqual(fallback["ga_search"]["evaluations"], 0)
        self.assertTrue(fallback["ga_search"]["time_limited"])


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class GeneticTogglePortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="GA test", status="active",
            access_until=timezone.localdate() + timedelta(days=30))
        cls.user = get_user_model().objects.create_user("ga_analyst")
        Membership.objects.create(company=cls.company, user=cls.user, role="analyst")
        cls.case = Scenario.objects.create(company=cls.company, created_by=cls.user,
            name="GA test case", inputs=joint_equipment_case().to_dict())

    def setUp(self):
        self.client.force_login(self.user)

    def test_only_explicit_on_post_enables_ga_and_exports_keep_existing_format(self):
        original = deepcopy(self.case.inputs)
        for value in (None, "off", "true", "on"):
            with self.subTest(value=value):
                payload = {"revision": self.case.revision}
                if value is not None:
                    payload["ga_enabled"] = value
                with patch("portal.views.compare", wraps=compare) as call:
                    response = self.client.post(reverse("run_analysis", args=[self.case.pk]), payload)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(call.call_args.kwargs, {"ga_enabled": True} if value == "on" else {})
                run = AnalysisRun.objects.latest("created_at")
                self.assertEqual(run.inputs, original)
                self.assertEqual(any("ga_search" in s for s in run.results["strategies"]), value == "on")
        self.assertContains(self.client.get(reverse("report", args=[run.pk])), "GA On:")
        exported = self.client.get(reverse("export_run", args=[run.pk, "json"]))
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(json.loads(exported.content)["results"], run.results)
        self.assertEqual(self.client.get(reverse("export_run", args=[run.pk, "csv"])).status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(self.case.inputs, original)

    def test_stale_revision_and_viewer_cannot_start_ga(self):
        with patch("portal.views.compare") as call:
            self.client.post(reverse("run_analysis", args=[self.case.pk]), {"revision": 0, "ga_enabled": "on"})
            Membership.objects.filter(user=self.user).update(role="viewer")
            response = self.client.post(reverse("run_analysis", args=[self.case.pk]),
                                        {"revision": self.case.revision, "ga_enabled": "on"})
        self.assertEqual(response.status_code, 403)
        call.assert_not_called()
        self.assertFalse(AnalysisRun.objects.exists())
