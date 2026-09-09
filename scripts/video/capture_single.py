"""Record one stationary mouse-over per completed narration in an isolated DB."""
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

from portal.engine.calculator import compare
from portal.models import AnalysisRun, Company, Membership, Scenario
from scripts.video.capture import POINTER
from scripts.video.single_voyage import OUT, case_input


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class SingleVoyageCapture(StaticLiveServerTestCase):
    def test_record(self):
        plan = {s["key"]: s for s in json.loads((OUT / "shot-plan.json").read_text(encoding="utf-8"))}
        data = case_input()
        expected = compare(data)
        self.assertEqual(len(data.vessels), 1)
        self.assertFalse(data.vessels[0].ops_ready)
        company = Company.objects.create(name="Illustrative bulk carrier", status="active",
                    access_until=timezone.localdate()+timedelta(days=365))
        password = secrets.token_urlsafe(24)
        user = get_user_model().objects.create_user("demo_analyst", password=password)
        Membership.objects.create(company=company, user=user, role="analyst")
        case = Scenario.objects.create(company=company, created_by=user, inputs=data.to_dict(),
                    name="2026 · Demo Atlas · Voyage 1")
        (OUT / "demo-inputs.json").write_text(json.dumps(data.to_dict(), indent=2), encoding="utf-8")
        scenes, errors = [], []
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
            context = browser.new_context(storage_state=state, viewport={"width":1600,"height":800},
                        record_video_dir=str(OUT / "raw"), record_video_size={"width":1600,"height":800})
            context.add_init_script(POINTER)
            context.add_init_script("document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent='[data-video-focus]{outline:2px solid #087f72!important;outline-offset:4px!important}';document.head.appendChild(s)});")
            origin = perf_counter()
            page = context.new_page()
            page.set_default_timeout(30000)
            page.on("pageerror", lambda error: errors.append(str(error)))

            def goto(name, *args):
                page.goto(self.live_server_url+reverse(name, args=args))
                page.wait_for_timeout(250)

            def scroll(locator, offset=60):
                top = locator.evaluate("el=>el.getBoundingClientRect().top+window.scrollY")
                page.evaluate("top=>window.scrollTo({top,behavior:'smooth'})", max(0,top-offset))
                page.wait_for_timeout(750)

            def point(locator):
                locator.scroll_into_view_if_needed()
                page.locator("[data-video-focus]").evaluate_all("els=>els.forEach(el=>el.removeAttribute('data-video-focus'))")
                locator.evaluate("el=>el.setAttribute('data-video-focus','')")
                box = locator.bounding_box()
                page.mouse.move(box["x"]+box["width"]*.6, box["y"]+box["height"]*.5, steps=20)
                return box

            def shot(key, locator, zoom=1.22, focus=None, action=None, after_speech=None):
                box = point(locator)
                s = dict(plan[key])
                s.update(start=perf_counter()-origin, zoom=zoom,
                         focus=focus or [800,max(330,min(470,box["y"]+box["height"]/2))])
                if action:
                    action()
                elapsed = perf_counter()-origin-s["start"]
                # Any click/navigation has settled before the narration starts.
                assert elapsed < s["lead"], (key, elapsed, s["lead"])
                if after_speech:
                    page.wait_for_timeout(max(0, s["lead"]+s["speech_seconds"]+.1-elapsed)*1000)
                    after_speech()
                    elapsed = perf_counter()-origin-s["start"]
                page.wait_for_timeout(max(0,s["duration"]-elapsed)*1000)
                s["end"] = perf_counter()-origin
                assert s["end"]-s["start"] >= s["lead"]+s["speech_seconds"]+.3
                scenes.append(s)
                page.screenshot(path=str(OUT / "raw" / f"{key}.png"))
                print(f"HOVER {key}: {s['duration']:.2f}s; narration finished before next target", flush=True)

            goto("scenario_edit", case.pk)
            shot("year", page.locator("#id_start_year"), focus=[800,350])
            goto("vessel_edit", case.pk, 0)
            shot("vessel", page.locator("#id_ship_type"), focus=[800,390])
            goto("scenario_edit", case.pk)
            scroll(page.get_by_role("heading", name="Budget & price assumptions"))
            shot("eua", page.locator("#id_eua_price"), focus=[800,330])
            scroll(page.get_by_role("heading", name="External pooling", exact=True))
            shot("pool", page.locator("#id_pool_price"), focus=[800,330])
            goto("vessel_edit", case.pk, 0)
            scroll(page.get_by_role("heading", name="Consumption & voyage mix"))
            shot("voyage", page.locator("#id_consumption-0-voyage"))
            for key, row, tonnes in (("extra_hsfo",1,"1000"), ("extra_vlsfo",3,"100"),
                     ("extra_mgo",5,"50"), ("intra_hsfo",0,"200"), ("intra_vlsfo",2,"50"),
                     ("intra_mgo",4,"50"), ("berth",6,"30")):
                field = page.locator(f"#id_consumption-{row}-tonnes")
                self.assertEqual(float(field.input_value()), float(tonnes))
                shot(key, field)
            scroll(page.get_by_role("heading", name="Fuel switching boundaries"))
            expect(page.locator("#id_alternative")).to_have_value("HVO")
            shot("hvo", page.locator("#id_alternative"), focus=[800,330])
            goto("scenario", case.pk)
            button = page.get_by_role("button", name="Compare strategies")
            def calculate():
                button.click()
                expect(page.get_by_role("heading", name="The cost of your next move.")).to_be_visible()
                point(page.locator(".recommendation h2"))
            # Explain the button first, then click. Trim only the subsequent
            # server wait, retaining the click and the full spoken explanation.
            shot("calculate", button, zoom=1, focus=[800,400], after_speech=calculate)
            scroll(page.locator(".strategy-list"), offset=80)
            best = page.locator(".strategy-option").filter(has=page.locator(".badge.good"))
            expect(best).to_have_count(1)
            def choose_best():
                best.click()
                target = page.locator(".strategy-option[aria-current='true']")
                target.scroll_into_view_if_needed()
                point(target)
            shot("best", best, zoom=1.16, focus=[900,350], action=choose_best)
            selected = page.locator(".strategy-option[aria-current='true']")
            expect(selected).to_contain_text("Lowest")
            operating = page.get_by_role("heading", name="What changes on each ship?")
            scroll(operating)
            shot("operating", operating, zoom=1.16, focus=[925,340])
            breakdown = page.get_by_role("heading", name="Annual costs, component by component")
            scroll(breakdown)
            shot("breakdown", breakdown, zoom=1.16, focus=[925,300])
            ledger = page.get_by_text("Ship-by-ship annual calculation ledger", exact=True)
            scroll(ledger, offset=80)
            shot("ledger", ledger, zoom=1.16, focus=[925,300], action=lambda:ledger.click())
            expect(ledger.locator("..")).to_have_attribute("open", "")
            with page.expect_download() as download:
                page.get_by_role("link", name="Audit file").click()
            download.value.save_as(str(OUT / "demo-audit.json"))
            # A final non-delivered pause anchors the recorded clock.
            page.wait_for_timeout(300)
            duration = perf_counter()-origin
            video = page.video
            context.close()
            video.save_as(str(OUT / "raw" / "walkthrough.webm"))
            browser.close()
        audit = json.loads((OUT / "demo-audit.json").read_text())
        self.assertEqual(audit["inputs"], data.to_dict())
        self.assertEqual(audit["results"], expected)
        self.assertEqual(audit["results"], AnalysisRun.objects.get(scenario=case).results)
        best = expected["strategies"][0]
        self.assertAlmostEqual(best["npv"], 1001422.0863258129, places=5)
        for strategy in expected["strategies"]:
            self.assertEqual(strategy["annual"][0]["electricity_cost"], 0)
            self.assertEqual(strategy["annual"][0]["electricity_mwh"], 0)
        self.assertEqual(errors, [])
        (OUT / "capture.json").write_text(json.dumps({"recording_wall_seconds":duration,"scenes":scenes},indent=2,ensure_ascii=False),encoding="utf-8")
        print("Verified one ship, one voyage, exact owner inputs, no OPS, and all saved results.", flush=True)
