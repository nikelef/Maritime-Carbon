import csv
import io
import json
from copy import deepcopy
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from portal.engine.schema import ScenarioInput, Vessel
from portal.forms import VesselForm
from portal.models import Company, Membership, Scenario, AnalysisRun
from .test_alternative_fuels import reviewed_case


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AlternativeFuelPortalTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Fuel transition tests", status="active", access_until=timezone.localdate() + timedelta(days=30))
        self.user = get_user_model().objects.create_user("fuel_analyst", password="test-only-password")
        Membership.objects.create(company=self.company, user=self.user, role="analyst")
        self.client.force_login(self.user)

    def new_case(self, data=None):
        return Scenario.objects.create(company=self.company, name="Transition case", inputs=(data or ScenarioInput()).to_dict(), created_by=self.user)

    def test_every_new_pathway_can_be_saved_run_rendered_and_exported(self):
        for code in ("LNG", "LBM", "E_LNG", "E_METHANOL", "E_AMMONIA", "E_HYDROGEN", "E_HYDROGEN_ICE", "E_DIESEL"):
            with self.subTest(code=code):
                data = reviewed_case(code)
                scenario = self.new_case(data)
                vessel = self.client.get(reverse("vessel_edit", args=[scenario.pk, 0]))
                self.assertContains(vessel, "Fuel system & transition economics", html=False)
                self.assertContains(vessel, code)
                payload = VesselForm.initial_for(data.vessels[0], 1)
                self.assertEqual(self.client.post(reverse("vessel_edit", args=[scenario.pk, 0]), payload).status_code, 302)
                self.assertEqual(self.client.post(reverse("run_analysis", args=[scenario.pk]), {"revision": 2}).status_code, 302)
                run = AnalysisRun.objects.get(scenario=scenario)
                self.assertContains(self.client.get(reverse("report", args=[run.pk])), "Fuel pathways, methane & RFNBO ledger", html=False)
                exported = json.loads(self.client.get(reverse("export_run", args=[run.pk, "json"])).content)
                self.assertEqual(exported["inputs"]["vessels"][0]["alternative"], code)
                csv_response = self.client.get(reverse("export_run", args=[run.pk, "csv"]))
                rows = list(csv.DictReader(io.StringIO(csv_response.content.decode("utf-8-sig"))))
                self.assertIn("RFNBO_energy_MJ", rows[0])
                self.assertIn("sea_MGO_pilot_t", rows[0])
                self.assertTrue(all(None not in row for row in rows))
                for strategy in run.results["strategies"]:
                    self.assertAlmostEqual(sum(float(row["NPV_EUR"]) for row in rows if row["strategy"] == strategy["name"]), strategy["npv"])

    def test_incomplete_rfnbo_evidence_does_not_enable_a_pathway(self):
        scenario = self.new_case()
        fuel = next(f for f in scenario.inputs["fuels"] if f["code"] == "E_AMMONIA")
        payload = {key: value if value is not None else "" for key, value in fuel.items()}
        payload.update(revision=1, eligible=True, wtt=10, evidence="test production evidence, no engine measurement")
        response = self.client.post(reverse("fuel_edit", args=[scenario.pk, "E_AMMONIA"]), payload)
        self.assertContains(response, "missing factors cannot be treated as zero")
        scenario.refresh_from_db()
        self.assertEqual(scenario.revision, 1)
        self.assertFalse(next(f for f in scenario.inputs["fuels"] if f["code"] == "E_AMMONIA")["eligible"])

    def test_rfnbo_form_keeps_fueleu_and_ets_eligibility_separate(self):
        scenario = self.new_case()
        fuel = next(f for f in scenario.inputs["fuels"] if f["code"] == "E_METHANOL")
        payload = {key: value if value is not None else "" for key, value in fuel.items()}
        payload.update(revision=1, eligible=True, ets_eligible=False, wtt=-50, ch4=0, n2o=.0001, factors_confirmed=True, evidence="TEST: RFNBO lifecycle and measured engine factors; ETS not asserted")
        response = self.client.post(reverse("fuel_edit", args=[scenario.pk, "E_METHANOL"]), payload)
        self.assertEqual(response.status_code, 302)
        scenario.refresh_from_db()
        saved = next(f for f in scenario.inputs["fuels"] if f["code"] == "E_METHANOL")
        self.assertTrue(saved["eligible"])
        self.assertFalse(saved["ets_eligible"])
        self.assertIsNone(saved["wtw"])  # Derived intensity, never a fabricated zero.
        self.assertEqual(saved["wtt"], -50)

    def test_lng_form_uses_locked_annex_factors_not_tampered_post_values(self):
        scenario = self.new_case()
        response = self.client.post(reverse("fuel_edit", args=[scenario.pk, "LNG"]), {"revision": 1, "price": 900, "wtt": -100, "co2": 0, "ch4": 0, "n2o": 0, "lcv": 1})
        self.assertEqual(response.status_code, 302)
        scenario.refresh_from_db()
        fuel = next(f for f in scenario.inputs["fuels"] if f["code"] == "LNG")
        self.assertEqual((fuel["wtt"], fuel["co2"], fuel["n2o"], fuel["lcv"]), (18.5, 2.75, .00011, 49100))
        self.assertEqual(fuel["price"], 900)

    def test_old_case_library_extension_is_explicit_and_preserves_reports(self):
        data = ScenarioInput(vessels=[Vessel()], scope_confirmed=True)
        data.fuels = data.fuels[:5]
        data.fuels[0].price = 1234
        scenario = self.new_case(data)
        self.client.post(reverse("run_analysis", args=[scenario.pk]), {"revision": 1})
        run = AnalysisRun.objects.get(scenario=scenario)
        saved = deepcopy(run.inputs)
        self.assertContains(self.client.get(reverse("scenario", args=[scenario.pk])), "Add available fuel pathways")
        self.assertEqual(self.client.get(reverse("fuel_library_extend", args=[scenario.pk])).status_code, 405)
        self.client.post(reverse("fuel_library_extend", args=[scenario.pk]), {"revision": 0})
        scenario.refresh_from_db()
        self.assertEqual(len(scenario.inputs["fuels"]), 5)
        self.client.post(reverse("fuel_library_extend", args=[scenario.pk]), {"revision": 1})
        scenario.refresh_from_db()
        run.refresh_from_db()
        self.assertEqual(len(scenario.inputs["fuels"]), 13)
        self.assertEqual(scenario.inputs["fuels"][0]["price"], 1234)
        self.assertEqual(scenario.revision, 2)
        self.assertEqual(run.inputs, saved)

    def test_extension_enforces_role_and_tenant_boundaries(self):
        scenario = self.new_case()
        member = self.user.membership
        member.role = "viewer"
        member.save()
        self.assertEqual(self.client.post(reverse("fuel_library_extend", args=[scenario.pk]), {"revision": 1}).status_code, 403)
        member.role = "analyst"
        member.save()
        other = Company.objects.create(name="Other company", access_until=timezone.localdate())
        scenario.company = other
        scenario.save()
        self.assertEqual(self.client.post(reverse("fuel_library_extend", args=[scenario.pk]), {"revision": 1}).status_code, 404)

    def test_v5_report_without_new_ledger_fields_still_renders_and_exports(self):
        scenario = self.new_case(ScenarioInput(vessels=[Vessel()], scope_confirmed=True))
        self.client.post(reverse("run_analysis", args=[scenario.pk]), {"revision": 1})
        run = AnalysisRun.objects.get(scenario=scenario)
        result = deepcopy(run.results)
        for strategy in result["strategies"]:
            for row in strategy["rows"]:
                for key in list(row):
                    if key.startswith("rfnbo_") or key in ("rewarded_energy_mj", "baseline_t", "pilot_t", "ghg_penalty_cost", "scoped_ch4_t"):
                        row.pop(key)
        AnalysisRun.objects.filter(pk=run.pk).update(results=result, engine_version="5.0.0")  # Emulate an existing historical snapshot.
        response = self.client.get(reverse("report", args=[run.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Fuel pathways, methane & RFNBO ledger")
        self.assertEqual(self.client.get(reverse("export_run", args=[run.pk, "csv"])).status_code, 200)
