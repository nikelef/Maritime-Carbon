"""Record the four real strategy cards, ranked best first, in an isolated database."""
import json
import os
from datetime import timedelta
from time import perf_counter
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright, expect
from portal.models import AnalysisRun, Company, Membership, Scenario
from scripts.video.capture import POINTER
from scripts.video.single_voyage import OUT, case_input


@override_settings(STORAGES={"default":{"BACKEND":"django.core.files.storage.FileSystemStorage"},
                            "staticfiles":{"BACKEND":"django.contrib.staticfiles.storage.StaticFilesStorage"}})
class StrategyCapture(StaticLiveServerTestCase):
    def test_capture(self):
        out = OUT / "closing-revision"
        plan = {s["key"]:s for s in json.loads((out/"plan.json").read_text(encoding="utf-8"))}
        audit = json.loads((OUT/"demo-audit.json").read_text())
        data = case_input().to_dict()
        self.assertEqual(data,audit["inputs"])
        company = Company.objects.create(name="Illustrative bulk carrier",status="active",
                    access_until=timezone.localdate()+timedelta(days=365))
        user = get_user_model().objects.create_user("demo_analyst")
        Membership.objects.create(company=company,user=user,role="analyst")
        case = Scenario.objects.create(company=company,created_by=user,inputs=data,name="2026 · Demo Atlas · Voyage 1")
        self.client.force_login(user)
        response = self.client.post(reverse("run_analysis",args=[case.pk]),{"revision":case.revision})
        self.assertEqual(response.status_code,302)
        report = AnalysisRun.objects.get(scenario=case)
        self.assertEqual(report.results,audit["results"])
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True,channel=os.environ.get("PLAYWRIGHT_CHANNEL","msedge"))
            context = browser.new_context(viewport={"width":1600,"height":800},
                        record_video_dir=str(out),record_video_size={"width":1600,"height":800})
            context.add_cookies([dict(name=settings.SESSION_COOKIE_NAME,
                value=self.client.cookies[settings.SESSION_COOKIE_NAME].value,url=self.live_server_url)])
            context.add_init_script(POINTER)
            context.add_init_script("document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent='[data-video-focus]{outline:3px solid #087f72!important;outline-offset:4px!important}';document.head.appendChild(s)});")
            origin = perf_counter()
            page = context.new_page()
            errors, scenes, cards = [], [], []
            page.on("pageerror",lambda error:errors.append(str(error)))
            page.goto(self.live_server_url+reverse("report",args=[report.pk]))
            choices = page.locator(".strategy-option")
            expect(choices).to_have_count(4)
            heading = page.get_by_role("heading",name="Which strategy costs less?")
            top = heading.evaluate("el=>el.getBoundingClientRect().top+window.scrollY")
            page.evaluate("top=>window.scrollTo(0,top-50)",top)
            page.wait_for_timeout(600)
            for index in range(4):
                key = f"rank_{index+1}"
                option = choices.nth(index)
                expected_cost = f"€{report.results['strategies'][index]['npv']:,.0f}"
                expect(option).to_contain_text(expected_cost)
                option.scroll_into_view_if_needed()
                page.locator("[data-video-focus]").evaluate_all("els=>els.forEach(el=>el.removeAttribute('data-video-focus'))")
                option.evaluate("el=>el.setAttribute('data-video-focus','')")
                box = option.bounding_box()
                page.mouse.move(box["x"]+box["width"]*.75,box["y"]+box["height"]*.5,steps=20)
                page.wait_for_timeout(150)
                start = perf_counter()-origin
                page.wait_for_timeout(plan[key]["duration"]*1000)
                scenes.append(dict(key=key,start=start,end=perf_counter()-origin))
                cards.append(option.inner_text())
                page.screenshot(path=str(out/f"{key}.png"))
            page.wait_for_timeout(300)
            duration = perf_counter()-origin
            video = page.video
            context.close()
            video.save_as(str(out/"walkthrough.webm"))
            browser.close()
        self.assertEqual(errors,[])
        (out/"capture.json").write_text(json.dumps(dict(recording_wall_seconds=duration,scenes=scenes,cards=cards),indent=2),encoding="utf-8")
        print("Verified all four ranked card costs against the saved audit; no browser errors.",flush=True)
