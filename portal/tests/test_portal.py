import csv
import hashlib
import io
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from portal.engine.schema import ScenarioInput, Vessel
from portal.forms import ScenarioForm, VesselForm
from portal.models import Company, Membership, Scenario, AnalysisRun, AuditEvent


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"], STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class PortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Company A", status="active", access_until=timezone.localdate() + timedelta(days=30))
        cls.other = Company.objects.create(name="Company B", status="active", access_until=timezone.localdate() + timedelta(days=30))
        cls.admin = get_user_model().objects.create_user("admin_a", password="unique-long-test-password", email="admin@example.test")
        cls.analyst = get_user_model().objects.create_user("analyst_a", password="unique-long-test-password")
        cls.viewer = get_user_model().objects.create_user("viewer_a", password="unique-long-test-password")
        cls.outsider = get_user_model().objects.create_user("analyst_b", password="unique-long-test-password")
        for user, company, role in ((cls.admin, cls.company, "admin"), (cls.analyst, cls.company, "analyst"), (cls.viewer, cls.company, "viewer"), (cls.outsider, cls.other, "analyst")):
            Membership.objects.create(user=user, company=company, role=role)
        data = ScenarioInput(vessels=[Vessel(name="Test ship")], scope_confirmed=True)
        cls.scenario = Scenario.objects.create(company=cls.company, name="Private plan A", inputs=data.to_dict(), created_by=cls.analyst)
        cls.foreign = Scenario.objects.create(company=cls.other, name="Private plan B", inputs=data.to_dict(), created_by=cls.outsider)

    def setUp(self):
        self.client.force_login(self.analyst)

    def run_case(self):
        response = self.client.post(reverse("run_analysis", args=[self.scenario.pk]), {"revision": 1})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AnalysisRun.objects.exists())
        return AnalysisRun.objects.latest("created_at")

    def test_private_routes_require_login(self):
        self.client.logout()
        for route in ("dashboard", "reports", "team", "scenario_create"):
            self.assertEqual(self.client.get(reverse(route)).status_code, 302)
        self.assertEqual(self.client.get(reverse("scenario", args=[self.scenario.pk])).status_code, 302)

    def test_all_case_endpoints_enforce_tenant_scope(self):
        for name, args in (("scenario", [self.foreign.pk]), ("scenario_edit", [self.foreign.pk]), ("vessel_add", [self.foreign.pk]), ("vessel_edit", [self.foreign.pk, 0]), ("fuel_edit", [self.foreign.pk, "HVO"])):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 404, name)
        for name, args in (("scenario_duplicate", [self.foreign.pk]), ("run_analysis", [self.foreign.pk]), ("vessel_remove", [self.foreign.pk, 0])):
            self.assertEqual(self.client.post(reverse(name, args=args), {"revision": 1}).status_code, 404, name)
        self.assertNotContains(self.client.get(reverse("dashboard")), "Private plan B")

    def test_report_and_exports_are_tenant_scoped(self):
        run = self.run_case()
        self.client.force_login(self.outsider)
        for name, args in (("report", [run.pk]), ("export_run", [run.pk, "json"]), ("export_run", [run.pk, "csv"])):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 404)

    def test_viewer_can_read_and_export_but_cannot_mutate(self):
        run = self.run_case()
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("report", args=[run.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("export_run", args=[run.pk, "json"])).status_code, 200)
        for name, args in (("scenario_edit", [self.scenario.pk]), ("scenario_duplicate", [self.scenario.pk]), ("run_analysis", [self.scenario.pk]), ("vessel_add", [self.scenario.pk]), ("vessel_remove", [self.scenario.pk, 0])):
            self.assertEqual(self.client.post(reverse(name, args=args)).status_code, 403)
        self.assertEqual(self.client.get(reverse("team")).status_code, 403)

    def test_expired_or_suspended_access_blocks_existing_session(self):
        self.company.access_until = timezone.localdate() - timedelta(days=1)
        self.company.save()
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)
        self.assertEqual(self.client.post(reverse("run_analysis", args=[self.scenario.pk]), {"revision": 1}).status_code, 403)
        self.company.access_until = timezone.localdate() + timedelta(days=1)
        self.company.status = "suspended"
        self.company.save()
        self.assertEqual(self.client.get(reverse("scenario", args=[self.scenario.pk])).status_code, 403)

    def test_snapshot_is_stable_and_fingerprint_reproducible(self):
        run = self.run_case()
        saved = json.loads(json.dumps(run.inputs))
        self.scenario.inputs["eua_price"] = 999
        self.scenario.save()
        run.refresh_from_db()
        self.assertEqual(run.inputs, saved)
        self.assertEqual(run.input_digest, hashlib.sha256(json.dumps(saved, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest())
        self.assertRaises(ValidationError, run.save)
        export = self.client.get(reverse("export_run", args=[run.pk, "json"]))
        self.assertEqual(json.loads(export.content)["inputs"], saved)
        self.assertTrue(AuditEvent.objects.filter(action="analysis.exported", company=self.company).exists())

    def test_stale_revision_cannot_overwrite_or_calculate(self):
        data = ScenarioInput.from_dict(self.scenario.inputs)
        payload = ScenarioForm.initial_for(self.scenario.name, data, 0)
        payload.pop("vessels")
        payload.pop("fuels")
        response = self.client.post(reverse("scenario_edit", args=[self.scenario.pk]), payload)
        self.assertContains(response, "changed in another session")
        self.scenario.refresh_from_db()
        self.assertEqual(self.scenario.revision, 1)
        self.client.post(reverse("run_analysis", args=[self.scenario.pk]), {"revision": 0})
        self.assertFalse(AnalysisRun.objects.exists())

    def test_csv_injection_is_escaped_and_totals_reconcile(self):
        self.scenario.inputs["vessels"][0]["name"] = '=HYPERLINK("bad")'
        self.scenario.inputs["other_annual_cost"] = 1234.56
        self.scenario.save()
        run = self.run_case()
        response = self.client.get(reverse("export_run", args=[run.pk, "csv"]))
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertTrue(rows[0]["vessel"].startswith("'="))
        for strategy in run.results["strategies"]:
            amount = sum(float(r["NPV_EUR"]) for r in rows if r["strategy"] == strategy["name"])
            self.assertAlmostEqual(amount, strategy["npv"])

    def test_report_escapes_user_content_and_selection_changes_display(self):
        self.scenario.name = '<script>alert("x")</script>'
        self.scenario.save()
        run = self.run_case()
        response = self.client.get(reverse("report", args=[run.pk]) + "?strategy=pool")
        selected = response.context["selected"]
        self.assertIn("pool", [item["key"] for item in selected["evaluations"]])
        saved_pool = next(s for s in run.results["strategies"] if s["key"] == "pool")
        self.assertEqual(selected["annual"], saved_pool["annual"])
        self.assertEqual(selected["rows"], saved_pool["rows"])
        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertContains(response, "&lt;script&gt;")

    def test_csrf_rejects_mutations_without_token(self):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.analyst)
        self.assertEqual(protected.post(reverse("run_analysis", args=[self.scenario.pk]), {"revision": 1}).status_code, 403)
        self.assertEqual(protected.post(reverse("logout")).status_code, 403)

    def test_get_cannot_run_duplicate_delete_or_logout(self):
        for name, args in (("run_analysis", [self.scenario.pk]), ("scenario_duplicate", [self.scenario.pk]), ("vessel_remove", [self.scenario.pk, 0]), ("logout", [])):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 405)

    def test_company_admin_can_create_scoped_user_and_seat_limit_is_enforced(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("team"), {"username": "colleague", "email": "colleague@example.test", "role": "viewer", "password": "a-special-passphrase-99", "company": self.other.pk, "is_staff": True})
        self.assertEqual(response.status_code, 302)
        created = Membership.objects.get(user__username="colleague")
        self.assertEqual(created.company, self.company)
        self.assertFalse(created.user.is_staff)
        self.company.max_users = 4
        self.company.save()
        response = self.client.post(reverse("team"), {"username": "excess", "email": "other@example.test", "role": "viewer", "password": "a-special-passphrase-99"})
        self.assertContains(response, "user limit")
        self.assertFalse(get_user_model().objects.filter(username="excess").exists())

    def test_cannot_deactivate_other_company_user_or_self(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse("deactivate_member", args=[self.outsider.membership.pk])).status_code, 404)
        self.client.post(reverse("deactivate_member", args=[self.admin.membership.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_deactivated_user_loses_an_existing_session(self):
        self.analyst.is_active = False
        self.analyst.save()
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_public_demo_uses_no_customer_data_or_writes(self):
        self.client.logout()
        for query, count in (("", 3), ("?fuels=transition", 2)):
            with self.subTest(demo=query or "standard"):
                response = self.client.get(reverse("demo") + query)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Illustrative example")
                self.assertNotContains(response, "Private plan")
                expected = [f"Vessel {index}" for index in range(1, count + 1)]
                run = response.context["run"]
                self.assertEqual([v["name"] for v in run.inputs["vessels"]], expected)
                self.assertTrue(all(not v["imo"] for v in run.inputs["vessels"]))
                for name in expected:
                    self.assertContains(response, name)
                for strategy in run.results["strategies"]:
                    self.assertEqual([d["vessel"] for d in strategy["decisions"]], expected)
                    self.assertEqual({row["vessel"] for row in strategy["rows"]}, set(expected))
        self.assertFalse(AnalysisRun.objects.exists())

    def test_login_throttle_and_generic_error(self):
        self.client.logout()
        for _ in range(5):
            response = self.client.post(reverse("login"), {"username": "admin_a", "password": "wrong"})
            self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse("login"), {"username": "admin_a", "password": "unique-long-test-password"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "900")

    def test_login_uses_safe_next_redirect(self):
        self.client.logout()
        response = self.client.post(reverse("login"), {"username": "admin_a", "password": "unique-long-test-password", "next": "https://attacker.example/"})
        self.assertEqual(response.url, "/")

    def test_security_headers_and_private_cache(self):
        response = self.client.get(reverse("dashboard"))
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("frame-ancestors 'none'", response["Content-Security-Policy"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")

    def test_create_vessel_edit_fuel_run_end_to_end(self):
        data = ScenarioInput()
        payload = ScenarioForm.initial_for("New customer case", data)
        for key in ("fuels", "vessels", "revision"):
            payload.pop(key)
        payload["scope_confirmed"] = True
        response = self.client.post(reverse("scenario_create"), payload)
        self.assertEqual(response.status_code, 302)
        created = Scenario.objects.get(name="New customer case")
        vessel_payload = VesselForm.initial_for(Vessel(name="New ship"), 1)
        response = self.client.post(reverse("vessel_add", args=[created.pk]), vessel_payload)
        self.assertEqual(response.status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.inputs["vessels"][0]["name"], "New ship")
        fuel_payload = next(f for f in created.inputs["fuels"] if f["code"] == "HVO").copy()
        fuel_payload.update(revision=2, eligible=True, evidence="Approved non-food/feed pathway reference", supply_t="")
        fuel_payload = {key: value if value is not None else "" for key, value in fuel_payload.items()}
        response = self.client.post(reverse("fuel_edit", args=[created.pk, "HVO"]), fuel_payload)
        self.assertEqual(response.status_code, 302)
        response = self.client.post(reverse("run_analysis", args=[created.pk]), {"revision": 3})
        self.assertEqual(response.status_code, 302)
        run = AnalysisRun.objects.get(scenario=created)
        self.assertEqual(run.scenario_revision, 3)
        self.assertEqual(self.client.get(response.url).status_code, 200)
