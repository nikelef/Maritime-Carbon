"""Independent physical, regulatory, optimization and saved-input checks for WAPS."""
from copy import deepcopy
import csv
import io
import json
from datetime import timedelta
from dataclasses import replace
from math import nextafter
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase, RequestFactory, TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from portal.engine.calculator import compare, profile, simulate, leg_demands, saved_decision, optimize
from portal.engine.leg_optimizer import leg_decision
from portal.engine.rules import wind_factor, target
from portal.engine.schema import ScenarioInput, Vessel
from portal.forms import VesselForm
from portal.views import report_context
from portal.models import Company, Membership, Scenario, AnalysisRun


def wind_case():
    vessel = Vessel(name="Wing candidate", wind_mode="retrofit", wind_confirmed=True,
        wind_reference="TEST route, propulsion/auxiliary demand and installation assessment",
        wind_capex=1000, wind_annual=100, wind_reward=True, wind_power_kw=1000,
        wind_propulsion_kw=10000, wind_reward_reference="TEST EEXI technical file",
        consumption=[dict(voyage=1, fuel="MGO", intra_t=1000, eu_berth_t=40,
            wind={"intra_t": {"propulsion_share": .8, "net_saving": .1}})])
    return ScenarioInput(start_year=2030, end_year=2030, scope_confirmed=True, vessels=[vessel])


class WindPhysicsTests(SimpleTestCase):
    def test_reward_thresholds_without_rounding_or_interpolation(self):
        for ratio, expected in [(0, 1), (nextafter(.05, 0), 1), (.05, .99),
                                (nextafter(.1, 0), .99), (.1, .97),
                                (nextafter(.15, 0), .97), (.15, .95), (.8, .95)]:
            with self.subTest(ratio=ratio):
                self.assertEqual(wind_factor(ratio, 1), expected)
        for p, prop in [(1, 0), (-1, 1), (True, 1), (1, float("inf")), (float("nan"), 1)]:
            with self.assertRaises(ValueError):
                wind_factor(p, prop)

    def test_physical_savings_then_reward_with_no_ets_double_credit(self):
        data = wind_case(); vessel = data.vessels[0]
        original = deepcopy(data.to_dict())
        base = profile(vessel, data, 2030)
        row = profile(vessel, data, 2030, wind=True)
        factor = 3.206 + .00005*28 + .00018*265
        self.assertAlmostEqual(row["fuel_tonnes"]["MGO"], 960)  # 1000 - 80 + 40 berth
        self.assertAlmostEqual(row["wind_saved_t"], 80)
        self.assertAlmostEqual(row["energy_mj"], 960*42700)
        self.assertAlmostEqual(row["ets_t"], 960*factor)
        self.assertAlmostEqual(base["ets_cost"]-row["ets_cost"], 80*factor*data.eua_price)
        self.assertAlmostEqual(row["attained_g"], base["attained_g"]*.97)
        self.assertAlmostEqual(row["balance_t"], (target(2030)-row["attained_g"])*960*42700/1e6)
        self.assertEqual(row["berth_t"], 40)
        self.assertEqual(row["wind_cost"], 1100)
        self.assertEqual(data.to_dict(), original)

    def test_each_voyage_leg_keeps_its_savings_and_scope(self):
        data = wind_case(); v = data.vessels[0]
        v.wind_reward = False
        v.consumption = [dict(voyage=1, fuel="MGO", intra_t=100, extra_t=200, outside_t=300,
            eu_berth_t=40, non_eu_berth_t=50, wind={
                "intra_t": dict(propulsion_share=.8, net_saving=.1),
                "extra_t": dict(propulsion_share=.5, net_saving=.2),
                "outside_t": dict(propulsion_share=1, net_saving=.3)}),
            dict(voyage=2, fuel="MGO", intra_t=10, wind={"intra_t": dict(propulsion_share=0, net_saving=0)})]
        row = profile(v, data, 2030, wind=True)
        self.assertAlmostEqual(row["fuel_tonnes"]["MGO"], 92+180+210+40+50+10)
        self.assertAlmostEqual(row["energy_mj"], (92+90+40+10)*42700)
        self.assertAlmostEqual(row["wind_saved_t"], 118)
        self.assertEqual(row["wind_factor"], 1)
        self.assertEqual(row["non_eu_berth_t"], 50)
        self.assertEqual(next(d for d in row["leg_replacements"] if d["voyage"] == 2)["after_wind_t"], 10)

    def test_wind_and_substitution_preserve_remaining_service_and_pilot(self):
        data = wind_case(); v = data.vessels[0]
        v.compatible, v.max_blend = True, 1
        hvo = next(f for f in data.fuels if f.code == "HVO")
        hvo.eligible, hvo.evidence = True, "TEST proof"
        v.alternative_energy_ratio, v.alternative_pilot_share = .8, .05
        ds = leg_demands(v, data)
        decision = leg_decision(ds, {key: .5 for key in ds}, False, True)
        row = profile(v, data, 2030, *decision)
        leg = row["leg_replacements"][0]
        self.assertAlmostEqual(leg["original_t"], leg["wind_saved_t"]+leg["replaced_t"]+leg["remaining_t"])
        self.assertAlmostEqual(leg["replaced_t"], 460)
        self.assertAlmostEqual(row["alternative_t"]*44000+row["pilot_t"]*42700, 460*42700*.8)
        self.assertAlmostEqual(row["energy_mj"], (460+40)*42700 + 460*42700*.8)
        self.assertAlmostEqual(row["fuel_replacements"][0]["replaced_t"], leg["replaced_t"])

    def test_existing_wind_is_in_reference_without_second_saving_or_capex(self):
        data = wind_case(); v = data.vessels[0]
        v.wind_mode, v.wind_capex = "existing", 0
        v.consumption[0]["intra_t"] = 920
        v.consumption[0].pop("wind")
        data.end_year = 2031
        result = simulate(data, [(0, False)])
        for row in result["rows"]:
            self.assertEqual(row["fuel_tonnes"]["MGO"], 960)
            self.assertEqual(row["wind_saved_t"], 0)
            self.assertEqual(row["wind_cost"], 100)
            self.assertEqual(row["wind_factor"], .97)
        self.assertFalse(result["decisions"][0]["wind_selected"])

    def test_capex_once_and_annual_cost_discounted(self):
        data = wind_case(); data.end_year = 2032
        d = leg_decision(leg_demands(data.vessels[0], data), {}, False, True)
        result = simulate(data, [d])
        self.assertEqual([r["wind_cost"] for r in result["annual"]], [1100, 100, 100])
        self.assertAlmostEqual(result["npv"], sum(r["total_cost"]/(1+data.discount_rate)**i for i,r in enumerate(result["annual"])))

    def test_reward_does_not_change_physical_energy_or_rfnbo_denominator(self):
        # Use an ordinary eligible RFNBO fuel-cell pathway with no measured-factor ambiguity.
        data = wind_case(); v = data.vessels[0]
        data.start_year = data.end_year = 2033
        fuel = next(f for f in data.fuels if f.code == "E_HYDROGEN")
        fuel.eligible, fuel.wtt, fuel.evidence = True, 10, "TEST RFNBO proof"
        v.alternative, v.compatible, v.max_blend = fuel.code, True, 1
        v.fuel_systems_confirmed, v.technical_reference = True, "TEST fuel cell"
        on = profile(v, data, 2033, .5, wind=True)
        off = profile(replace(v, wind_reward=False), data, 2033, .5, wind=True)
        for key in ("energy_mj", "rewarded_energy_mj", "rfnbo_energy_mj", "ets_t", "fuel_cost"):
            self.assertEqual(on[key], off[key])
        self.assertAlmostEqual(on["attained_g"], off["attained_g"]*.97)

    def test_small_vessel_gets_physical_savings_without_fueleu_reward(self):
        data = wind_case(); v = data.vessels[0]; v.gt = 4999
        row = profile(v, data, 2030, wind=True)
        self.assertEqual((row["wind_factor"], row["energy_mj"], row["ets_t"]), (1, 0, 0))
        self.assertAlmostEqual(row["wind_saved_t"], 80)


class WindValidationTests(SimpleTestCase):
    def test_invalid_or_unevidenced_wind_is_rejected(self):
        changes = [{"wind_confirmed": False}, {"wind_reference": ""},
                   {"wind_reward_reference": ""}, {"wind_propulsion_kw": 0},
                   {"wind_mode": "invalid"}, {"wind_capex": -1},
                   {"wind_mode": "existing", "wind_capex": 0}, {"wind_mode": "none"}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                data = wind_case(); data.vessels[0] = replace(data.vessels[0], **change); data.validate()
        for item in ({}, {"intra_t": dict(propulsion_share=float("nan"), net_saving=.1)},
                     {"eu_berth_t": dict(propulsion_share=1, net_saving=.1)},
                     {"intra_t": dict(propulsion_share=1, net_saving=1)}):
            with self.subTest(item=item), self.assertRaises(ValueError):
                data = wind_case(); data.vessels[0].consumption[0]["wind"] = item; data.validate()

    def test_legacy_inputs_default_to_no_wind_and_form_round_trip_keeps_rows(self):
        data = wind_case(); v = data.vessels[0]
        values = VesselForm.initial_for(v, 3)
        form = VesselForm(values, initial=values, fuels=data.fuels)
        self.assertTrue(form.is_valid(), (form.errors, form.input_formset.errors))
        saved = form.vessel(); saved.validate({f.code: f for f in data.fuels})
        self.assertEqual(saved.consumption, v.consumption)
        self.assertEqual(saved.wind_power_kw, 1000)
        raw = data.to_dict()
        raw["vessels"][0] = {k:v for k,v in raw["vessels"][0].items() if not k.startswith("wind_")}
        self.assertEqual(ScenarioInput.from_dict(raw).vessels[0].wind_mode, "none")


class WindOptimizationTests(SimpleTestCase):
    def test_shared_alternative_supply_and_each_ship_cap_with_wind(self):
        data = wind_case(); v = data.vessels[0]
        v.compatible, v.max_blend = True, .02
        data.vessels.append(replace(v, name="Second wing candidate", consumption=deepcopy(v.consumption)))
        hvo = next(f for f in data.fuels if f.code == "HVO")
        hvo.price, hvo.eligible, hvo.evidence, hvo.supply_t = 1, True, "TEST proof", 10.123
        result = optimize(data, False)
        self.assertLessEqual(sum(r["alternative_t"] for r in result["rows"]), hvo.supply_t+1e-7)
        self.assertAlmostEqual(sum(r["alternative_t"] for r in result["rows"]), hvo.supply_t, places=5)
        self.assertTrue(all(d["blend"] <= .02+1e-10 for d in result["decisions"]))
        self.assertTrue(all(d["wind_selected"] for d in result["decisions"]))

    def test_economics_select_or_reject_wings_and_snapshot_replays(self):
        data = wind_case()
        result = compare(data)
        best = result["strategies"][0]
        self.assertTrue(best["decisions"][0]["wind_selected"])
        replay = simulate(data, [saved_decision(d) for d in best["decisions"]], best["use_pool"])
        self.assertEqual(replay["npv"], best["npv"])
        self.assertAlmostEqual(sum(best["package_comparison"].values()), best["savings"])
        data.vessels[0].wind_capex = 100_000_000
        self.assertFalse(optimize(data, False)["decisions"][0]["wind_selected"])

    def test_wind_combines_with_fuel_switching_and_pooling(self):
        data = wind_case(); v = data.vessels[0]
        v.compatible, v.max_blend, v.wind_reward = True, .01, False
        hvo = next(f for f in data.fuels if f.code == "HVO")
        hvo.price, hvo.eligible, hvo.ets_eligible, hvo.evidence = 1, True, True, "TEST proof"
        data.pool_enabled, data.pool_cap, data.pool_price, data.pool_reference = True, 10000, 100, "TEST pool quote"
        best = compare(data)["strategies"][0]
        self.assertTrue(best["decisions"][0]["wind_selected"])
        self.assertGreater(best["decisions"][0]["blend"], 0)
        self.assertGreater(best["pool_cost"], 0)
        self.assertEqual(best["residual_deficit_t"], 0)

    def test_wind_reduces_alternative_needed_to_close_deficit(self):
        data = wind_case(); v = data.vessels[0]
        v.compatible, v.max_blend = True, 1
        hvo = next(f for f in data.fuels if f.code == "HVO")
        hvo.eligible, hvo.ets_eligible, hvo.evidence = True, True, "TEST proof"
        with_wings = optimize(data, False)
        without = deepcopy(data); without.vessels[0].wind_mode = "none"
        without.vessels[0].wind_reward = False
        without.vessels[0].wind_capex = without.vessels[0].wind_annual = 0
        without_wings = optimize(without, False)
        self.assertTrue(with_wings["decisions"][0]["wind_selected"])
        self.assertLess(with_wings["decisions"][0]["alternative_t"], without_wings["decisions"][0]["alternative_t"])

    def test_report_explains_package_and_preserves_saved_results(self):
        data = wind_case(); result = compare(data); original = deepcopy(result)
        run = SimpleNamespace(inputs=data.to_dict(), results=result, engine_version="6.8.0",
            ruleset_version="test", scenario_revision=1, scenario_name="Wind case")
        context = report_context(run, RequestFactory().get("/demo/")); context["demo"] = True
        html = render_to_string("portal/report.html", context)
        self.assertIn("What the package changes", html)
        self.assertIn("Install wind assistance", html)
        self.assertIn("0.97", html)
        self.assertEqual(result, original)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class WindPortalTests(TestCase):
    def setUp(self):
        company = Company.objects.create(name="Wind test company", status="active",
            access_until=timezone.localdate()+timedelta(days=30))
        user = get_user_model().objects.create_user("wind_test", password="test-only-password")
        Membership.objects.create(company=company, user=user, role="analyst")
        self.data = wind_case()
        self.case = Scenario.objects.create(company=company, created_by=user, name="Wind comparison", inputs=self.data.to_dict())
        self.client.force_login(user)

    def test_edit_run_and_exports_keep_wind_evidence_and_reconcile_costs(self):
        initial = VesselForm.initial_for(self.data.vessels[0], 1)
        payload = {key:value for key,value in initial.items() if value is not None and not isinstance(value, (list,dict))}
        response = self.client.post(reverse("vessel_edit", args=[self.case.pk, 0]), payload)
        self.assertEqual(response.status_code, 302)
        self.case.refresh_from_db()
        self.assertEqual(self.case.inputs["vessels"][0]["consumption"], self.data.vessels[0].consumption)
        response = self.client.post(reverse("run_analysis", args=[self.case.pk]), {"revision": 2})
        self.assertEqual(response.status_code, 302)
        run = AnalysisRun.objects.get(scenario=self.case)
        self.assertContains(self.client.get(reverse("report", args=[run.pk])), "What the package changes")
        exported = self.client.get(reverse("export_run", args=[run.pk, "json"])).json()
        self.assertEqual(exported["inputs"]["vessels"][0]["wind_reward_reference"], "TEST EEXI technical file")
        rows = list(csv.DictReader(io.StringIO(self.client.get(reverse("export_run", args=[run.pk, "csv"])).content.decode("utf-8-sig"))))
        wind_rows = [r for r in rows if r["wind_selected"] == "True"]
        self.assertTrue(wind_rows)
        self.assertTrue(all(float(r["FuelEU_wind_factor"]) == .97 for r in wind_rows))
        leg = json.loads(wind_rows[0]["sea_leg_replacements_json"])[0]
        self.assertAlmostEqual(leg["wind_saved_t"], 80)
        for strategy in run.results["strategies"]:
            self.assertAlmostEqual(sum(float(r["NPV_EUR"]) for r in rows if r["strategy"] == strategy["name"]), strategy["npv"])
        saved = deepcopy(run.results)
        self.case.inputs["vessels"][0]["wind_capex"] = 999999
        self.case.save()
        run.refresh_from_db()
        self.assertEqual(run.results, saved)

    def test_missing_propulsion_inputs_block_save_and_keep_draft(self):
        initial = VesselForm.initial_for(self.data.vessels[0], 1)
        payload = {key:value for key,value in initial.items() if value is not None and not isinstance(value, (list,dict))}
        payload.pop("consumption-0-propulsion_share")
        payload.pop("consumption-0-net_saving")
        response = self.client.post(reverse("vessel_edit", args=[self.case.pk, 0]), payload)
        self.assertContains(response, "enter propulsion share and net wind saving")
        self.case.refresh_from_db()
        self.assertEqual(self.case.revision, 1)

    def test_existing_excel_import_contract_defaults_to_no_wind(self):
        from portal.row_imports import parse_excel
        from portal.tests.test_excel_import import example_book
        book = example_book(); stream = io.BytesIO(); book.save(stream); book.close()
        vessels = parse_excel(stream.getvalue())
        self.assertEqual(vessels[0].wind_mode, "none")
        self.assertFalse(vessels[0].wind_reward)
