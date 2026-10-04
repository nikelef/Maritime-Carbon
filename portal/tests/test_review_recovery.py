"""Explicit legacy-factor repair and historical-report preservation."""
from copy import deepcopy
import csv
import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.engine.calculator import compare
from portal.engine.schema import ScenarioInput, Vessel, fossil_oil_defaults
from portal.models import AnalysisRun, AuditEvent, Company, Membership, Scenario


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class LegacyFactorRecoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Default recovery", status="active",
            access_until=timezone.localdate() + timedelta(days=30))
        cls.analyst = get_user_model().objects.create_user("factor_recovery_analyst")
        cls.viewer = get_user_model().objects.create_user("factor_recovery_viewer")
        for user, role in ((cls.analyst, "analyst"), (cls.viewer, "viewer")):
            Membership.objects.create(company=cls.company, user=user, role=role)
        other = Company.objects.create(name="Other recovery", status="active",
            access_until=timezone.localdate() + timedelta(days=30))
        cls.outsider = get_user_model().objects.create_user("factor_recovery_outsider")
        Membership.objects.create(company=other, user=cls.outsider, role="analyst")
        data = ScenarioInput(start_year=2026, end_year=2026, scope_confirmed=True,
            vessels=[Vessel(name="Recovery vessel", fuel="MGO", sea_t=100,
                            berth_t=0, intra_share=1, extra_share=0, max_blend=0)])
        cls.original = data.to_dict()
        # A historical snapshot can contain old editable factors. Its saved
        # output is retained; this test verifies recovery, not old-engine math.
        results = compare(data)
        legacy = deepcopy(cls.original)
        for fuel in legacy["fuels"]:
            if fuel["code"] == "MGO":
                fuel.update(co2=1, wtw=40, wtt=None, price=901,
                            supply_t=123, evidence="Recorded commercial quote")
            elif fuel["code"] == "HSFO":
                fuel.update(wtw=77, wtt=0)
        cls.case = Scenario.objects.create(company=cls.company, created_by=cls.analyst,
                                          name="Legacy factors", inputs=legacy)
        cls.saved_run = AnalysisRun.objects.create(company=cls.company, created_by=cls.analyst,
            scenario=cls.case, scenario_name=cls.case.name, scenario_revision=1,
            inputs=legacy, results=results, input_digest="legacy-record",
            engine_version="6.8.1", ruleset_version="EU-2026-10-01-review")

    def setUp(self):
        self.client.force_login(self.analyst)

    def restore_url(self):
        return reverse("fossil_defaults_restore", args=[self.case.pk])

    def test_multiple_overrides_restore_together_without_rewriting_reports(self):
        before_inputs, before_results = deepcopy(self.saved_run.inputs), deepcopy(self.saved_run.results)
        response = self.client.get(reverse("scenario", args=[self.case.pk]))
        self.assertContains(response, "Restore fossil fuel defaults")
        self.assertTrue(response.context["ready_errors"])
        self.assertEqual(self.client.post(self.restore_url(), {"revision": 1}).status_code, 302)
        self.case.refresh_from_db()
        self.assertEqual(self.case.revision, 2)
        corrected = ScenarioInput.from_dict(self.case.inputs)
        corrected.validate()
        for fuel in corrected.fuels:
            defaults = fossil_oil_defaults(fuel.code)
            if defaults:
                for field, expected in defaults.items():
                    self.assertEqual(getattr(fuel, field), expected)
        mgo = next(f for f in corrected.fuels if f.code == "MGO")
        self.assertEqual((mgo.price, mgo.supply_t, mgo.evidence),
                         (901, 123, "Recorded commercial quote"))
        self.assertEqual(self.case.inputs["vessels"], before_inputs["vessels"])
        self.assertEqual(next(f for f in self.case.inputs["fuels"] if f["code"] == "HVO"),
                         next(f for f in before_inputs["fuels"] if f["code"] == "HVO"))
        self.saved_run.refresh_from_db()
        self.assertEqual(self.saved_run.inputs, before_inputs)
        self.assertEqual(self.saved_run.results, before_results)
        self.assertContains(self.client.get(reverse("report", args=[self.saved_run.pk])),
                            "saved fossil oil factors differ")
        self.assertTrue(AuditEvent.objects.filter(company=self.company,
                                                  action="scenario.updated").exists())

    def test_invalid_saved_factors_block_new_comparison(self):
        count = AnalysisRun.objects.count()
        self.client.post(reverse("run_analysis", args=[self.case.pk]), {"revision": 1})
        self.assertEqual(AnalysisRun.objects.count(), count)

    def test_repair_requires_current_revision_and_is_idempotent(self):
        before = deepcopy(self.case.inputs)
        self.client.post(self.restore_url(), {"revision": 0})
        self.case.refresh_from_db()
        self.assertEqual(self.case.inputs, before)
        self.assertEqual(self.case.revision, 1)
        self.client.post(self.restore_url(), {"revision": 1})
        self.client.post(self.restore_url(), {"revision": 2})
        self.case.refresh_from_db()
        self.assertEqual(self.case.revision, 2)

    def test_restore_enforces_role_tenant_method_and_csrf(self):
        self.assertEqual(self.client.get(self.restore_url()).status_code, 405)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(self.restore_url(), {"revision": 1}).status_code, 403)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(self.restore_url(), {"revision": 1}).status_code, 404)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.analyst)
        self.assertEqual(protected.post(self.restore_url(), {"revision": 1}).status_code, 403)

    def test_historical_rfnbo_quantities_are_disclosed_without_recalculation(self):
        data = ScenarioInput.from_dict(self.original)
        data.start_year = data.end_year = 2034
        results = compare(data)
        results.pop("rfnbo_subtarget_accounting_method")
        for strategy in results["strategies"]:
            for row in strategy["rows"]:
                row.pop("rfnbo_subtarget_accounting_method")
                row.pop("allocated_fuel_energy_mj")
                row.pop("allocated_rfnbo_energy_mj")
        run = AnalysisRun.objects.create(company=self.company, created_by=self.analyst,
            scenario=self.case, scenario_name="Historical RFNBO", scenario_revision=1,
            inputs=data.to_dict(), results=results, input_digest="old-subtarget-record",
            engine_version="6.8.1", ruleset_version="EU-2026-10-01-review")
        self.assertContains(self.client.get(reverse("report", args=[run.pk])),
                            "New comparisons use independently scoped physical fuel energy")
        self.assertEqual(self.client.get(reverse("export_run", args=[run.pk, "json"])).json()["results"], results)
        csv_response = self.client.get(reverse("export_run", args=[run.pk, "csv"]))
        rows = list(csv.DictReader(io.StringIO(csv_response.content.decode("utf-8-sig"))))
        self.assertTrue(all(row["physical_fuel_energy_MJ"] == "" for row in rows))
        run.refresh_from_db()
        self.assertEqual(run.results, results)
