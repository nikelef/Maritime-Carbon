"""GA switch keyboard/mobile checks and real form submissions in an isolated DB."""
from datetime import timedelta
import os
from pathlib import Path
import re
import secrets
from unittest import skipUnless

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from portal.models import AnalysisRun, Company, Membership, Scenario
from portal.tests.test_ga_optimizer import joint_equipment_case


@skipUnless(os.environ.get("RUN_BROWSER_TESTS") == "1", "Enable RUN_BROWSER_TESTS=1 for browser checks.")
@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                           "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class GeneticToggleBrowserTests(StaticLiveServerTestCase):
    def test_ga_toggle_default_keyboard_mobile_and_saved_reports(self):
        from playwright.sync_api import sync_playwright, expect
        password = secrets.token_urlsafe(20)
        company = Company.objects.create(name="GA browser fixture", status="active",
            access_until=timezone.localdate() + timedelta(days=30))
        user = get_user_model().objects.create_user("ga_browser", password=password)
        Membership.objects.create(company=company, user=user, role="analyst")
        case = Scenario.objects.create(company=company, created_by=user, name="GA joint fleet test",
                                       inputs=joint_equipment_case().to_dict())
        case_url = self.live_server_url + reverse("scenario", args=[case.pk])
        artifacts = Path(settings.BASE_DIR) / "test-artifacts" / "ga-toggle"
        artifacts.mkdir(parents=True, exist_ok=True)
        errors = []
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True, channel=os.environ.get("PLAYWRIGHT_CHANNEL") or None)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + reverse("login"))
            page.get_by_label("Username").fill(user.username)
            page.get_by_label("Password").fill(password)
            page.get_by_role("button", name="Sign in securely").click()
            page.goto(case_url)
            toggle = page.get_by_role("switch", name="GA On/Off")
            compare_button = page.get_by_role("button", name="Compare strategies")
            for width in (1440, 390):
                page.set_viewport_size({"width": width, "height": 1000})
                if width == 390:
                    expect(page.locator(".sidebar")).to_have_css("transform", "matrix(1, 0, 0, 1, -230, 0)")
                expect(toggle).not_to_be_checked()
                button_box = compare_button.bounding_box()
                switch_box = page.locator(".ga-toggle-track").bounding_box()
                self.assertGreaterEqual(switch_box["y"], button_box["y"] + button_box["height"])
                toggle.focus()
                page.keyboard.press("Space")
                expect(toggle).to_be_checked()
                expect(page.locator(".ga-on")).to_be_visible()
                page.screenshot(path=str(artifacts / f"ga-on-{width}.png"), animations="disabled")
                page.get_by_text("GA On/Off", exact=True).click()
                expect(toggle).not_to_be_checked()
                expect(page.locator(".ga-off")).to_be_visible()
                self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.screenshot(path=str(artifacts / "ga-off-desktop.png"), animations="disabled")
            compare_button.click()
            expect(page).to_have_url(re.compile(r"/reports/[^/]+/$"))
            off_pk = page.url.rstrip("/").rsplit("/", 1)[-1]
            page.goto(case_url)
            expect(toggle).not_to_be_checked()
            page.get_by_text("GA On/Off", exact=True).click()
            compare_button.click()
            expect(page).to_have_url(re.compile(r"/reports/[^/]+/$"))
            on_pk = page.url.rstrip("/").rsplit("/", 1)[-1]
            page.screenshot(path=str(artifacts / "ga-report.png"), full_page=True)
            # Returning to a case starts with the default Off; this is a per-run option.
            page.goto(case_url)
            expect(toggle).not_to_be_checked()
            browser.close()
        off, on = AnalysisRun.objects.get(pk=off_pk), AnalysisRun.objects.get(pk=on_pk)
        self.assertNotEqual(off.pk, on.pk)
        self.assertFalse(any("ga_search" in s for s in off.results["strategies"]))
        self.assertTrue(any("ga_search" in s for s in on.results["strategies"]))
        self.assertLess(on.results["strategies"][0]["npv"], off.results["strategies"][0]["npv"])
        self.assertEqual(on.inputs, off.inputs)
        self.assertEqual(errors, [])
