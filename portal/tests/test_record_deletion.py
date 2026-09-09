"""Deletion permissions, confirmation, audit retention and desktop contrast."""
import os
from datetime import timedelta
from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.engine.calculator import compare
from portal.engine.schema import ScenarioInput, Vessel
from portal.models import AnalysisRun, AuditEvent, Company, Membership, Scenario


def records(user, company):
    data = ScenarioInput(start_year=2026, end_year=2026, scope_confirmed=True,
                         vessels=[Vessel(name="Deletion test vessel")])
    case = Scenario.objects.create(company=company, created_by=user, name="Review case", inputs=data.to_dict())
    result = compare(data)
    runs = [AnalysisRun.objects.create(company=company, created_by=user, scenario=case,
            scenario_name=case.name, scenario_revision=1, inputs=data.to_dict(), results=result,
            input_digest="test-digest", engine_version="test", ruleset_version="test") for _ in range(2)]
    return case, runs


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RecordDeletionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Deletion fixture", status="active",
                         access_until=timezone.localdate() + timedelta(days=30))
        cls.analyst = get_user_model().objects.create_user("delete_analyst")
        Membership.objects.create(user=cls.analyst, company=cls.company, role="analyst")
        cls.case, cls.runs = records(cls.analyst, cls.company)

    def setUp(self):
        self.client.force_login(self.analyst)

    def test_confirmation_is_read_only_and_identifies_consequences(self):
        for name, pk in (("scenario_delete", self.case.pk), ("report_delete", self.runs[0].pk)):
            response = self.client.get(reverse(name, args=[pk]))
            self.assertContains(response, "This cannot be undone")
            self.assertContains(response, "Cancel")
            self.assertEqual(self.client.put(reverse(name, args=[pk])).status_code, 405)
        self.assertEqual(AnalysisRun.objects.count(), 2)
        self.assertTrue(Scenario.objects.filter(pk=self.case.pk).exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_delete_one_report_retains_case_other_report_and_audit(self):
        run = self.runs[0]
        response = self.client.post(reverse("report_delete", args=[run.pk]))
        self.assertRedirects(response, reverse("reports"))
        self.assertFalse(AnalysisRun.objects.filter(pk=run.pk).exists())
        self.assertTrue(AnalysisRun.objects.filter(pk=self.runs[1].pk).exists())
        self.assertTrue(Scenario.objects.filter(pk=self.case.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(action="analysis.deleted", object_id=run.pk,
                        company=self.company, actor=self.analyst).exists())
        self.assertEqual(self.client.get(reverse("report", args=[run.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("export_run", args=[run.pk, "json"])).status_code, 404)

    def test_delete_case_removes_associated_reports_and_retains_audit(self):
        # Company administrators have the same deletion capability as analysts.
        Membership.objects.filter(user=self.analyst).update(role="admin")
        response = self.client.post(reverse("scenario_delete", args=[self.case.pk]), {"revision": 1, "run_count": 2})
        self.assertRedirects(response, reverse("dashboard"))
        self.assertFalse(Scenario.objects.exists())
        self.assertFalse(AnalysisRun.objects.exists())
        self.assertEqual(AuditEvent.objects.filter(action="analysis.deleted").count(), 2)
        self.assertTrue(AuditEvent.objects.filter(action="scenario.deleted", object_id=self.case.pk).exists())

    def test_changed_case_or_report_count_requires_new_confirmation(self):
        url = reverse("scenario_delete", args=[self.case.pk])
        for payload in ({}, {"revision": 0, "run_count": 2}, {"revision": 1, "run_count": 1}):
            self.assertContains(self.client.post(url, payload), "changed since you opened", status_code=409)
        self.assertTrue(Scenario.objects.filter(pk=self.case.pk).exists())
        self.assertEqual(AnalysisRun.objects.count(), 2)

    def test_viewers_other_companies_and_anonymous_users_cannot_delete(self):
        urls = [reverse("scenario_delete", args=[self.case.pk]), reverse("report_delete", args=[self.runs[0].pk])]
        Membership.objects.filter(user=self.analyst).update(role="viewer")
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url).status_code, 403)
        self.assertNotContains(self.client.get(reverse("dashboard")), urls[0])
        self.assertNotContains(self.client.get(reverse("scenario", args=[self.case.pk])), urls[0])
        self.assertNotContains(self.client.get(reverse("reports")), urls[1])
        self.assertNotContains(self.client.get(reverse("report", args=[self.runs[0].pk])), urls[1])
        other = Company.objects.create(name="Other company", status="active", access_until=self.company.access_until)
        Membership.objects.filter(user=self.analyst).update(role="analyst", company=other)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url).status_code, 404)
        self.client.logout()
        for url in urls:
            self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(AnalysisRun.objects.count(), 2)
        self.assertTrue(Scenario.objects.filter(pk=self.case.pk).exists())

    def test_csrf_is_required_and_expired_access_is_blocked(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.analyst)
        for name, pk in (("scenario_delete", self.case.pk), ("report_delete", self.runs[0].pk)):
            self.assertEqual(client.post(reverse(name, args=[pk])).status_code, 403)
        self.company.access_until = timezone.localdate() - timedelta(days=1)
        self.company.save()
        for name, pk in (("scenario_delete", self.case.pk), ("report_delete", self.runs[0].pk)):
            self.assertEqual(self.client.post(reverse(name, args=[pk])).status_code, 403)
        self.assertEqual(AnalysisRun.objects.count(), 2)


@skipUnless(os.environ.get("RUN_BROWSER_TESTS") == "1", "Enable RUN_BROWSER_TESTS=1 for desktop checks.")
@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class DesktopRecordTests(StaticLiveServerTestCase):
    def test_dashboard_contrast_and_delete_workflows(self):
        from playwright.sync_api import sync_playwright, expect
        company = Company.objects.create(name="Desktop records", status="active",
                    access_until=timezone.localdate() + timedelta(days=30))
        user = get_user_model().objects.create_user("desktop_records", password="fixture-password-only")
        Membership.objects.create(user=user, company=company, role="analyst")
        case, runs = records(user, company)
        artifacts = Path(settings.BASE_DIR) / "test-artifacts" / "desktop-records"
        artifacts.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True, channel=os.environ.get("PLAYWRIGHT_CHANNEL") or None)
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.goto(self.live_server_url + reverse("login"))
            page.get_by_label("Username").fill(user.username)
            page.locator("#id_password").fill("fixture-password-only")
            page.get_by_role("button", name="Sign in securely").click()
            expect(page.locator(".metric > strong")).to_have_text(["1", "2", company.access_until.strftime("%d %b %Y")])
            # The banner's white foreground must never be inherited by the cards or case list.
            expect(page.locator(".overview-banner .metric, .overview-banner #cases")).to_have_count(0)
            for locator in (page.locator(".metric > strong"), page.locator("#cases h2")):
                for element in locator.all():
                    expect(element).to_have_css("color", "rgb(21, 47, 52)")
            page.screenshot(path=str(artifacts / "dashboard.png"), full_page=True)
            # Check visible white text against its actual white background across the main screens.
            for route, args in (("dashboard", []), ("scenario", [case.pk]), ("reports", []),
                                ("report", [runs[0].pk]), ("scenario_delete", [case.pk]),
                                ("report_delete", [runs[0].pk])):
                page.goto(self.live_server_url + reverse(route, args=args))
                invisible = page.locator("main").evaluate("""root => {
                    const pale = color => { const c = color.match(/[\\d.]+/g).map(Number);
                        return c.slice(0, 3).every(n => n > 235) && (c.length < 4 || c[3] > .9); };
                    return [...root.querySelectorAll('*')].filter(el => {
                        if (!el.getClientRects().length || ![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) return false;
                        if (!pale(getComputedStyle(el).color)) return false;
                        let bg = el;
                        while (bg && getComputedStyle(bg).backgroundColor === 'rgba(0, 0, 0, 0)') bg = bg.parentElement;
                        return bg && pale(getComputedStyle(bg).backgroundColor);
                    }).map(el => el.textContent.trim().slice(0, 100));
                }""")
                self.assertEqual(invisible, [], route)
            page.goto(self.live_server_url + reverse("reports"))
            page.get_by_role("link", name="Delete report for Review case").first.click()
            page.get_by_role("link", name="Cancel", exact=True).click()
            expect(page.get_by_role("heading", name="The cost of your next move.")).to_be_visible()
            page.get_by_role("link", name="Delete report", exact=True).click()
            page.get_by_role("button", name="Delete saved report", exact=True).click()
            expect(page.locator(".saved-report-item")).to_have_count(1)
            page.goto(self.live_server_url + reverse("dashboard"))
            expect(page.locator(".metric > strong").nth(1)).to_have_text("1")
            page.get_by_role("link", name="Delete Review case", exact=True).click()
            expect(page.get_by_text("Revision 1 · 1 saved report", exact=True)).to_be_visible()
            page.screenshot(path=str(artifacts / "confirm-case-deletion.png"), full_page=True)
            page.get_by_role("link", name="Cancel", exact=True).click()
            page.get_by_role("link", name="Delete case", exact=True).click()
            page.get_by_role("button", name="Delete case and reports", exact=True).click()
            expect(page.locator(".metric > strong").nth(0)).to_have_text("0")
            expect(page.locator(".metric > strong").nth(1)).to_have_text("0")
            browser.close()
        self.assertFalse(Scenario.objects.filter(pk=case.pk).exists())
        self.assertFalse(AnalysisRun.objects.filter(company=company).exists())
