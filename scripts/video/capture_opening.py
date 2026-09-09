"""Film the full-width welcome and overview pages using an isolated demo company."""
import json
import os
import secrets
from datetime import timedelta
from time import perf_counter
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright, expect
from portal.models import Company, Membership, Scenario
from scripts.video.capture import POINTER
from scripts.video.single_voyage import OUT, case_input


@override_settings(STORAGES={"default":{"BACKEND":"django.core.files.storage.FileSystemStorage"},
                            "staticfiles":{"BACKEND":"django.contrib.staticfiles.storage.StaticFilesStorage"}})
class OpeningCapture(StaticLiveServerTestCase):
    def test_capture(self):
        out = OUT / "opening"
        plan = {s["key"]:s for s in json.loads((out / "plan.json").read_text())}
        company = Company.objects.create(name="Illustrative bulk carrier", status="active",
                    access_until=timezone.localdate()+timedelta(days=365))
        password = secrets.token_urlsafe(24)
        user = get_user_model().objects.create_user("demo_analyst", password=password)
        Membership.objects.create(company=company, user=user, role="analyst")
        data = case_input().to_dict()
        self.assertEqual(data, json.loads((OUT / "demo-inputs.json").read_text()))
        Scenario.objects.create(company=company, created_by=user, inputs=data, name="2026 · Demo Atlas · Voyage 1")
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True, channel=os.environ.get("PLAYWRIGHT_CHANNEL", "msedge"))
            auth = browser.new_context()
            page = auth.new_page()
            page.goto(self.live_server_url+reverse("login"))
            page.get_by_label("Username").fill(user.username)
            page.locator("#id_password").fill(password)
            page.get_by_role("button", name="Sign in securely").click()
            expect(page.locator(".metric > strong").first).to_have_text("1")
            state = auth.storage_state()
            auth.close()
            context = browser.new_context(viewport={"width":1600,"height":800},
                        record_video_dir=str(out), record_video_size={"width":1600,"height":800})
            context.add_init_script(POINTER)
            origin = perf_counter()
            page = context.new_page()
            errors, scenes = [], []
            page.on("pageerror", lambda error:errors.append(str(error)))
            for key, route in (("welcome","login"),("overview","dashboard")):
                if key=="overview":
                    context.add_cookies(state["cookies"])
                page.goto(self.live_server_url+reverse(route))
                expect(page.locator("h1")).to_be_visible()
                page.mouse.move(1480,740,steps=20)
                page.wait_for_timeout(350)
                start = perf_counter()-origin
                page.wait_for_timeout(plan[key]["duration"]*1000)
                scenes.append(dict(key=key,start=start,end=perf_counter()-origin))
                page.screenshot(path=str(out / f"{key}.png"))
            expect(page.locator(".metric > strong").first).to_have_text("1")
            page.wait_for_timeout(300)
            duration = perf_counter()-origin
            video = page.video
            context.close()
            video.save_as(str(out / "walkthrough.webm"))
            browser.close()
        self.assertEqual(errors, [])
        (out / "capture.json").write_text(json.dumps(dict(recording_wall_seconds=duration,scenes=scenes),indent=2))
