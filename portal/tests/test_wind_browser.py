"""Optional browser acceptance of wind inputs, saving and the package report."""
import os
import secrets
from datetime import timedelta
from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.utils import timezone

from portal.models import Company, Membership, Scenario, AnalysisRun
from portal.tests.test_wind import wind_case


@skipUnless(os.environ.get("RUN_BROWSER_TESTS") == "1", "Enable RUN_BROWSER_TESTS=1 for browser acceptance checks.")
@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                           "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class WindBrowserTests(StaticLiveServerTestCase):
    def test_wind_form_save_report_and_mobile_layout(self):
        from playwright.sync_api import sync_playwright, expect
        password = secrets.token_urlsafe(20)
        company = Company.objects.create(name="Wind browser fixture", status="active",
            access_until=timezone.localdate()+timedelta(days=30))
        user = get_user_model().objects.create_user("wind_browser", password=password)
        Membership.objects.create(company=company, user=user, role="analyst")
        data = wind_case()
        data.vessels[0].wind_mode = "none"
        data.vessels[0].wind_capex = data.vessels[0].wind_annual = 0
        data.vessels[0].wind_reward = False
        data.vessels[0].consumption[0].pop("wind")
        case = Scenario.objects.create(company=company, created_by=user, name="Wing browser comparison", inputs=data.to_dict())
        artifacts = Path(settings.BASE_DIR)/"test-artifacts"
        artifacts.mkdir(exist_ok=True)
        errors = []
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True, channel=os.environ.get("PLAYWRIGHT_CHANNEL") or None)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.emulate_media(reduced_motion="reduce")
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(self.live_server_url+"/accounts/login/")
            page.get_by_label("Username").fill(user.username)
            page.get_by_label("Password").fill(password)
            page.get_by_role("button", name="Sign in securely").click()
            page.goto(f"{self.live_server_url}/cases/{case.pk}/vessels/0/")
            expect(page.locator("#id_consumption-0-propulsion_share")).to_be_hidden()
            page.locator("#id_wind_mode").select_option("retrofit")
            expect(page.locator("#id_consumption-0-propulsion_share")).to_be_visible()
            page.locator("#id_consumption-0-propulsion_share").fill("80")
            page.locator("#id_consumption-0-net_saving").fill("10")
            expect(page.locator("#id_consumption-1-propulsion_share")).to_be_disabled()
            page.get_by_label("Wind installation & downtime cost").fill("1000")
            page.get_by_label("Wind annual maintenance & operating cost").fill("100")
            page.get_by_label("Wind baseline, compatibility").check()
            page.get_by_label("Apply the separately reviewed FuelEU wind reward").check()
            page.locator(".consumption-table-scroll").screenshot(path=str(artifacts/"wind-consumption-desktop.png"))
            page.locator("#wind-assistance").screenshot(path=str(artifacts/"wind-settings-desktop.png"))
            page.set_viewport_size({"width": 390, "height": 844})
            self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
            page.locator("#wind-assistance").scroll_into_view_if_needed()
            page.screenshot(path=str(artifacts/"wind-settings-mobile.png"))
            page.get_by_role("button", name="Save vessel").click()
            expect(page.get_by_role("heading", name="Every ship keeps its own balance.")).to_be_visible()
            page.goto(f"{self.live_server_url}/cases/{case.pk}/vessels/0/")
            expect(page.locator("#id_consumption-0-propulsion_share")).to_have_value("80.0")
            expect(page.locator("#id_consumption-0-net_saving")).to_have_value("10.0")
            page.goto(f"{self.live_server_url}/cases/{case.pk}/")
            page.get_by_role("button", name="Compare strategies").click()
            expect(page.get_by_role("heading", name="What the package changes")).to_be_visible()
            self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.locator("#wind-package").screenshot(path=str(artifacts/"wind-package-desktop.png"))
            self.assertFalse(errors, errors)
            browser.close()
        case.refresh_from_db()
        self.assertEqual(case.inputs["vessels"][0]["wind_mode"], "retrofit")
        self.assertTrue(AnalysisRun.objects.get(scenario=case).results["strategies"][0]["decisions"][0]["wind_selected"])
