"""Record actual desktop app interactions in Django's isolated test database.

Run: DJANGO_DEBUG=1 PLAYWRIGHT_CHANNEL=msedge python manage.py test scripts.video.capture
The deliberate pauses are filming cues, not application performance tests.
"""
import json
import os
import secrets
from datetime import timedelta
from pathlib import Path
from time import perf_counter

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from portal.engine.calculator import compare
from portal.models import AnalysisRun, Company, Membership, Scenario
from scripts.video.fixture import pitch_case


POINTER = """(() => {
  document.addEventListener('DOMContentLoaded', () => {
    const pointer = document.createElement('div');
    pointer.style.cssText = 'position:fixed;left:-100px;top:-100px;width:24px;height:32px;pointer-events:none;z-index:2147483647;filter:drop-shadow(0 2px 2px #0005)';
    pointer.innerHTML = '<svg viewBox="0 0 24 32"><path d="M2 2L3 25L9 19L14 29L19 26L14 17L23 17Z" fill="white" stroke="#102e32" stroke-width="2"/></svg>';
    document.body.appendChild(pointer);
    document.addEventListener('mousemove', e => {pointer.style.left=e.clientX+'px';pointer.style.top=e.clientY+'px';});
    document.addEventListener('mousedown', e => {
      const ring = document.createElement('div');
      ring.style.cssText = `position:fixed;left:${e.clientX-22}px;top:${e.clientY-22}px;width:44px;height:44px;border:3px solid #087f72;border-radius:50%;background:#c8eea033;pointer-events:none;z-index:2147483646`;
      document.body.appendChild(ring);
      ring.animate([{transform:'scale(.4)',opacity:1},{transform:'scale(1.3)',opacity:0}],{duration:650}).onfinish=()=>ring.remove();
    });
  });
})();"""


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class PitchCapture(StaticLiveServerTestCase):
    def test_record_pitch(self):
        from playwright.sync_api import sync_playwright, expect
        out = Path(settings.BASE_DIR) / "video-artifacts"
        out.mkdir(exist_ok=True)
        (out / "raw").mkdir(exist_ok=True)
        password = secrets.token_urlsafe(24)
        company = Company.objects.create(name="Illustrative fleet", status="active",
                    access_until=timezone.localdate() + timedelta(days=365))
        user = get_user_model().objects.create_user("demo_analyst", password=password)
        Membership.objects.create(company=company, user=user, role="analyst")
        data = pitch_case()
        scenario = Scenario.objects.create(company=company, created_by=user,
                    name="2026 fleet planning — illustrative demo", inputs=data.to_dict())
        expected = compare(data)
        (out / "demo-inputs.json").write_text(json.dumps(data.to_dict(), indent=2), encoding="utf-8")
        scenes, errors = [], []
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True, channel=os.environ.get("PLAYWRIGHT_CHANNEL", "msedge"))
            login = browser.new_context()
            page = login.new_page()
            page.goto(self.live_server_url + reverse("login"))
            page.get_by_label("Username").fill(user.username)
            page.locator("#id_password").fill(password)
            page.get_by_role("button", name="Sign in securely").click()
            expect(page.locator(".metric > strong").first).to_have_text("1")
            state = login.storage_state()
            login.close()
            context = browser.new_context(storage_state=state, viewport={"width": 1600, "height": 800},
                       record_video_dir=str(out / "raw"), record_video_size={"width": 1600, "height": 800})
            context.add_init_script(POINTER)
            origin = perf_counter()
            page = context.new_page()
            page.set_default_timeout(30000)
            page.on("pageerror", lambda exc: errors.append(str(exc)))

            def hold(seconds):
                page.wait_for_timeout(seconds * 1000)

            def move(locator):
                box = locator.bounding_box()
                assert box
                page.mouse.move(box["x"]+box["width"]*.5, box["y"]+box["height"]*.5, steps=24)
                hold(.15)

            def click(locator):
                locator.scroll_into_view_if_needed()
                move(locator)
                locator.click()

            def scroll(locator, offset=55):
                top = locator.evaluate("el => el.getBoundingClientRect().top + window.scrollY")
                page.evaluate("top => window.scrollTo({top, behavior:'smooth'})", max(0, top-offset))
                hold(.8)

            def type_value(selector, value):
                locator = page.locator(selector)
                click(locator)
                locator.press("Control+A")
                locator.press_sequentially(str(value), delay=180)
                locator.evaluate("el => el.blur()")
                hold(.45)

            def start(key, caption, zoom=1.0, focus=(800, 400)):
                scenes.append(dict(key=key, start=perf_counter()-origin, caption=caption, zoom=zoom, focus=focus))

            def end():
                scenes[-1]["end"] = perf_counter()-origin
                page.screenshot(path=str(out / "raw" / (scenes[-1]["key"]+".png")))
                print("CAPTURE", scenes[-1]["key"], round(scenes[-1]["end"]-scenes[-1]["start"], 2), flush=True)

            page.goto(self.live_server_url + reverse("scenario", args=[scenario.pk]))
            hold(.5)
            start("fleet", "Two vessels. One consistent basis for comparing carbon costs.", 1.0)
            hold(3)
            click(page.get_by_role("link", name="Edit assumptions"))
            hold(.5)
            end()

            scroll(page.get_by_role("heading", name="Budget & price assumptions"))
            start("allowances", "Start with your planning assumptions: EUA price €85/tCO₂e.", 1.3, (790, 325))
            type_value("#id_eua_price", "85")
            hold(2)
            end()

            scroll(page.get_by_role("heading", name="External pooling", exact=True))
            start("pool_price", "External pooling offer: €190 per tonne of FuelEU balance.", 1.3, (790, 300))
            type_value("#id_pool_price", "190")
            hold(1.5)
            end()
            click(page.get_by_role("button", name="Save assumptions"))
            expect(page.get_by_role("heading", name="Every ship keeps its own balance.")).to_be_visible()
            click(page.get_by_role("row").filter(has_text="Demo Atlas").get_by_role("link", name="Edit", exact=True))
            hold(.4)
            start("atlas", "Demo Atlas: record annual consumption by voyage, leg and fuel.", 1.12, (800, 320))
            hold(2.5)
            end()

            scroll(page.get_by_role("heading", name="Consumption & voyage mix"))
            rows = page.locator(".consumption-row")
            mgo_intra = rows.filter(has=page.locator('select[id$="-fuel"] option[value="MGO"]:checked')).filter(
                has=page.locator('select[id$="-leg"] option[value="intra_t"]:checked'))
            mgo_extra = rows.filter(has=page.locator('select[id$="-fuel"] option[value="MGO"]:checked')).filter(
                has=page.locator('select[id$="-leg"] option[value="extra_t"]:checked'))
            start("atlas_legs", "Voyage 1: 80 t MGO intra-EU; 20 t MGO on the EU/non-EU leg.", 1.22, (805, 325))
            type_value("#"+mgo_intra.locator('input[id$="-tonnes"]').get_attribute("id"), "80")
            type_value("#"+mgo_extra.locator('input[id$="-tonnes"]').get_attribute("id"), "20")
            hold(3)
            end()

            scroll(page.get_by_role("heading", name="Fuel switching boundaries"))
            start("alternative", "Evaluate HVO within each vessel’s technical and energy limits.", 1.3, (790, 320))
            move(page.locator("#id_alternative"))
            page.locator("#id_alternative").select_option("HVO")
            hold(1)
            type_value("#id_max_blend", "10")
            hold(1.5)
            end()
            click(page.get_by_role("button", name="Save vessel"))
            click(page.get_by_role("row").filter(has_text="Demo Boreas").get_by_role("link", name="Edit", exact=True))
            hold(.5)
            start("boreas", "Demo Boreas keeps its own consumption profile and voyage allocation.", 1.1, (800, 330))
            hold(2.5)
            end()
            scroll(page.get_by_role("heading", name="Consumption & voyage mix"))
            start("boreas_legs", "Voyage 2 includes 300 t VLSFO on an EU/non-EU sea leg.", 1.22, (805, 320))
            type_value("#id_consumption-1-tonnes", "300")
            hold(2)
            end()
            click(page.get_by_role("button", name="Save vessel"))
            click(page.get_by_role("row").filter(has=page.locator("td > strong", has_text="HVO")).get_by_role("link", name="Review"))
            scroll(page.locator("#id_eligible").locator(".."), offset=130)
            start("evidence", "FuelEU eligibility and ETS CO₂ zero-rating are confirmed separately.", 1.3, (790, 320))
            move(page.locator("#id_ets_eligible"))
            hold(4)
            end()
            click(page.get_by_role("button", name="Save fuel assumptions"))
            page.evaluate("window.scrollTo(0,0)")
            hold(.4)
            start("calculate", "Save the inputs. Compare the fleet’s operating choices.", 1.0)
            hold(.6)
            click(page.get_by_role("button", name="Compare strategies"))
            expect(page.get_by_role("heading", name="The cost of your next move.")).to_be_visible()
            hold(1)
            end()
            report_url = page.url
            start("result", "The lowest evaluated option uses targeted HVO replacement.", 1.12, (930, 350))
            hold(5)
            end()

            scroll(page.locator(".strategy-list"), offset=70)
            start("policies", "Compare the alternatives against current fuels and pooling.", 1.16, (850, 330))
            hold(3)
            click(page.locator('.strategy-option[href="?strategy=pool"]'))
            hold(.8)
            end()
            start("pool_result", "Current fuels + external pooling: €1,218,152.18 for 2026.", 1.12, (930, 350))
            hold(3.5)
            end()
            scroll(page.locator(".strategy-list"), offset=70)
            click(page.locator('.strategy-option[href="?strategy=fuel"]'))
            hold(.5)
            start("best_result", "Targeted HVO: €1,216,283.69 — €1,868.49 less than pooling.", 1.12, (930, 350))
            hold(4.5)
            end()
            scroll(page.locator("[data-strategy-explanation]"), offset=90)
            start("leg_remarks", "The recommendation names the vessel, voyage, leg and exact tonnes.", 1.2, (925, 330))
            hold(7)
            end()
            start("energy", "Replacement energy stays on the same leg. HVO and MGO tonnes differ.", 1.2, (925, 330))
            hold(4)
            end()
            page.evaluate("window.scrollTo({top:0,behavior:'smooth'})")
            hold(.8)
            start("audit", "Export the saved inputs and calculations for a traceable decision.", 1.0)
            with page.expect_download() as download:
                click(page.get_by_role("link", name="Audit file"))
            download.value.save_as(str(out / "demo-audit.json"))
            hold(2)
            with page.expect_download() as download:
                click(page.get_by_role("link", name="Download CSV"))
            download.value.save_as(str(out / "demo-results.csv"))
            hold(1)
            end()
            video = page.video
            duration = perf_counter()-origin
            context.close()
            video.save_as(str(out / "raw" / "walkthrough.webm"))
            browser.close()
        audit = json.loads((out / "demo-audit.json").read_text(encoding="utf-8"))
        best = next(s for s in audit["results"]["strategies"] if s["key"] == "fuel")
        pool = next(s for s in audit["results"]["strategies"] if s["key"] == "pool")
        self.assertAlmostEqual(best["npv"], 1216283.69, places=2)
        self.assertAlmostEqual(pool["npv"], 1218152.18, places=2)
        self.assertEqual(audit["inputs"], data.to_dict())
        self.assertEqual(audit["results"], expected)
        self.assertEqual(audit["results"], AnalysisRun.objects.get(scenario=scenario).results)
        self.assertEqual(errors, [])
        manifest = {"recording_wall_seconds": duration, "viewport": [1600, 800], "scenes": scenes,
                    "annual_cost_eur": best["npv"], "pooling_option_eur": pool["npv"],
                    "saving_vs_pooling_eur": pool["npv"]-best["npv"], "best_key": "fuel"}
        (out / "capture.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Capture and independent audit checks passed.", flush=True)
