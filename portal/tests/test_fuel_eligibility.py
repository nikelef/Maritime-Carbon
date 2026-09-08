"""Regression for a low-WtW alternative excluded despite high carbon prices."""
from copy import deepcopy
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.engine.calculator import compare, fuel_choice_notices
from portal.engine.schema import ScenarioInput, Vessel
from portal.models import AnalysisRun, Company, Membership, Scenario


def high_carbon_price_case(eligible=False, ets_eligible=False):
    data = ScenarioInput(start_year=2026, end_year=2026, scope_confirmed=True,
                         eua_price=400, pool_enabled=True, pool_price=400,
                         pool_cap=100000, pool_reference="TEST pooling assumption",
                         vessels=[Vessel(name="Eligibility regression", compatible=True, max_blend=1,
                                         consumption=[{"fuel": "HSFO", "intra_t": 200, "extra_t": 800},
                                                      {"fuel": "MGO", "intra_t": 80, "extra_t": 20, "eu_berth_t": 50},
                                                      {"fuel": "VLSFO", "intra_t": 10, "extra_t": 50}])])
    hvo = next(f for f in data.fuels if f.code == "HVO")
    hvo.eligible, hvo.ets_eligible = eligible, ets_eligible
    hvo.evidence = "TEST assumed supplier eligibility" if eligible or ets_eligible else ""
    data.validate()
    return data


class FuelEligibilityRegressionTests(SimpleTestCase):
    def test_low_wtw_and_extreme_prices_do_not_silently_enable_eligibility(self):
        data = high_carbon_price_case()
        data.eua_price = data.pool_price = 50000
        next(f for f in data.fuels if f.code == "HVO").wtw = 1
        original = deepcopy(data.to_dict())
        result = compare(data)
        self.assertTrue(all(s["decisions"][0]["blend"] == 0 for s in result["strategies"]))
        notice = result["fuel_choice_notices"][0]
        self.assertTrue(notice["excluded"])
        self.assertEqual(notice["fuel"], "HVO")
        self.assertIn("FuelEU pathway eligibility is not enabled", notice["reasons"][0])
        self.assertEqual(data.to_dict(), original)

    def test_eligible_hvo_with_ets_credit_replaces_mgo_and_costs_reconcile(self):
        data = high_carbon_price_case(True, True)
        result = compare(data)
        best = result["strategies"][0]
        self.assertEqual(best["decisions"][0]["replacements"], {"HSFO": 0, "MGO": 1, "VLSFO": 0})
        alternative_t = 100 * 42700 / 44000
        self.assertAlmostEqual(best["decisions"][0]["alternative_t"], alternative_t)
        oil_factor = 3.114 + .00005 * 28 + .00018 * 265
        mgo_factor = 3.206 + .00005 * 28 + .00018 * 265
        hvo_factor = .00005 * 28 + .00018 * 265
        # The replaced MGO has 90% coverage; 50 t EU berth MGO is retained.
        baseline_ets = 635 * oil_factor + 140 * mgo_factor
        selected_ets = 635 * oil_factor + 50 * mgo_factor + alternative_t * .9 * hvo_factor
        selected_fuel = 1000 * 470 + 60 * 575 + 50 * 720 + alternative_t * 1550
        row = best["annual"][0]
        self.assertAlmostEqual(row["fuel_cost"], selected_fuel)
        self.assertAlmostEqual(row["ets_cost"], selected_ets * 400)
        self.assertEqual(row["penalty_cost"], 0)
        self.assertEqual(row["pool_cost"], 0)
        self.assertAlmostEqual(best["npv"], selected_fuel + selected_ets * 400)
        baseline = next(s for s in result["strategies"] if s["key"] == "baseline")
        self.assertAlmostEqual(baseline["annual"][0]["ets_cost"], baseline_ets * 400)
        self.assertEqual(result["fuel_choice_notices"], [])

    def test_higher_eua_prices_expand_replacement_when_hvo_is_enabled(self):
        data = high_carbon_price_case(True, True)
        data.eua_price = 50000
        decision = compare(data)["strategies"][0]["decisions"][0]
        self.assertAlmostEqual(decision["blend"], 1)
        self.assertEqual(decision["replacements"], {"HSFO": 1, "MGO": 1, "VLSFO": 1})

    def test_fueleu_eligibility_alone_does_not_zero_rate_ets(self):
        result = compare(high_carbon_price_case(True, False))
        best = result["strategies"][0]
        self.assertEqual(best["decisions"][0]["blend"], 0)
        notice = result["fuel_choice_notices"][0]
        self.assertFalse(notice["excluded"])
        self.assertIn("ETS CO2 zero-rating is not enabled", notice["reasons"][0])
        # The separate no-pooling policy can still benefit from low FuelEU WtW.
        fuel_only = next(s for s in result["strategies"] if s["key"] == "fuel")
        self.assertGreater(fuel_only["decisions"][0]["blend"], 0)

    def test_notices_also_explain_vessel_and_supply_limits(self):
        data = high_carbon_price_case(True, True)
        data.vessels[0].compatible = False
        data.vessels[0].max_blend = 0
        next(f for f in data.fuels if f.code == "HVO").supply_t = 0
        notice = fuel_choice_notices(data)[0]
        self.assertTrue(notice["excluded"])
        self.assertEqual(len(notice["reasons"]), 3)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class FuelEligibilityNoticeTests(TestCase):
    def setUp(self):
        company = Company.objects.create(name="Eligibility notice tests", status="active", access_until=timezone.localdate()+timedelta(days=30))
        self.user = get_user_model().objects.create_user("eligibility_analyst")
        Membership.objects.create(company=company, user=self.user, role="analyst")
        self.client.force_login(self.user)
        self.scenario = Scenario.objects.create(company=company, name="High prices", created_by=self.user,
                                                inputs=high_carbon_price_case().to_dict())

    def test_case_report_and_export_explain_exclusion_without_changing_inputs(self):
        original = deepcopy(self.scenario.inputs)
        case_page = self.client.get(reverse("scenario", args=[self.scenario.pk]))
        self.assertContains(case_page, "HVO excluded from fuel comparison")
        self.assertContains(case_page, reverse("fuel_edit", args=[self.scenario.pk, "HVO"]))
        self.assertEqual(self.client.post(reverse("run_analysis", args=[self.scenario.pk]), {"revision": 1}).status_code, 302)
        run = AnalysisRun.objects.get(scenario=self.scenario)
        report = self.client.get(reverse("report", args=[run.pk]))
        self.assertContains(report, "HVO excluded from fuel comparison")
        self.assertContains(report, "does not establish that they are cheaper than HVO")
        payload = self.client.get(reverse("export_run", args=[run.pk, "json"])).json()
        self.assertTrue(payload["results"]["fuel_choice_notices"][0]["excluded"])
        self.scenario.refresh_from_db()
        self.assertEqual(self.scenario.inputs, original)
        self.assertEqual(run.inputs, original)

    def test_old_report_uses_snapshot_eligibility_after_current_case_changes(self):
        data = high_carbon_price_case()
        result = compare(data)
        result.pop("fuel_choice_notices")
        run = AnalysisRun.objects.create(company=self.scenario.company, scenario=self.scenario,
                                         scenario_name=self.scenario.name, scenario_revision=1,
                                         inputs=data.to_dict(), results=result, input_digest="test",
                                         engine_version="6.4.0", ruleset_version="test", created_by=self.user)
        self.scenario.inputs = high_carbon_price_case(True, True).to_dict()
        self.scenario.revision = 2
        self.scenario.save()
        report = self.client.get(reverse("report", args=[run.pk]))
        self.assertContains(report, "HVO excluded from fuel comparison")
        self.assertContains(report, "inputs saved with this report")
        run.refresh_from_db()
        self.assertEqual(run.results, result)
        self.assertNotContains(self.client.get(reverse("scenario", args=[self.scenario.pk])), "HVO excluded from fuel comparison")

    def test_enabled_fuel_without_ets_credit_has_distinct_notice(self):
        self.scenario.inputs = high_carbon_price_case(True, False).to_dict()
        self.scenario.save()
        response = self.client.get(reverse("scenario", args=[self.scenario.pk]))
        self.assertContains(response, "HVO evaluated without ETS CO₂ zero-rating")
        self.assertNotContains(response, "HVO excluded from fuel comparison")
