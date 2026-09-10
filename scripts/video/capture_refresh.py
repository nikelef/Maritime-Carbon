"""Film current results, the actual fuel picker, OPS setting and allocation ledger."""
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
from scripts.video.single_voyage import case_input
from scripts.video.refresh import OUT


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class RefreshedVoyageCapture(StaticLiveServerTestCase):
    def test_record(self):
        plan = {s["key"]: s for s in json.loads((OUT / "shot-plan.json").read_text(encoding="utf-8"))}
        data = case_input()
        expected = compare(data)
        prepared = json.loads((OUT / "prepared-case.json").read_text(encoding="utf-8"))
        self.assertEqual(expected, prepared["results"])
        self.assertEqual(data.to_dict(), prepared["inputs"])
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

            def shot(key, locator, zoom=1, focus=None, action=None, after_speech=None, during=None):
                box = point(locator)
                s = dict(plan[key])
                s.update(start=perf_counter()-origin, zoom=zoom,
                         focus=focus or [800,max(330,min(470,box["y"]+box["height"]/2))])
                if action:
                    action()
                elapsed = perf_counter()-origin-s["start"]
                # Any click/navigation has settled before the narration starts.
                assert elapsed < s["lead"], (key, elapsed, s["lead"])
                if during:
                    during(s)
                    elapsed = perf_counter()-origin-s["start"]
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
            fuel = page.locator("#id_alternative")
            expect(fuel).to_have_value("HVO")
            # Browser-rendered native select picker is visible to screencast.
            # This filming-only CSS keeps the real options and form untouched.
            self.assertTrue(page.evaluate("CSS.supports('appearance','base-select')"))
            page.add_style_tag(content="""
                #id_alternative, #id_alternative::picker(select) { appearance:base-select; }
                #id_alternative::picker(select) { max-height:220px; overflow-y:auto;
                    border:1px solid #087f72; background:white; color:#102e32;
                    font:16px 'Segoe UI',sans-serif; box-shadow:0 8px 24px #102e3233; }
                #id_alternative option { padding:7px 12px; }
            """)
            shot("hvo", fuel, focus=[800,330])
            options = fuel.locator("option").all_text_contents()
            self.assertGreater(len(options), 5)
            def browse_options(s):
                self.assertTrue(fuel.evaluate("el=>el.matches(':open')"))
                box = fuel.bounding_box()
                page.mouse.move(box["x"]+box["width"]*.7, box["y"]+box["height"]+65, steps=12)
                page.wait_for_timeout(1250)
                page.screenshot(path=str(OUT / "raw" / "fuel-options-top.png"))
                page.mouse.wheel(0, 350)
                page.wait_for_timeout(800)
                page.screenshot(path=str(OUT / "raw" / "fuel-options-scrolled.png"))
            shot("fuel_options", fuel, action=lambda:fuel.click(), during=browse_options)
            page.keyboard.press("Escape")
            expect(fuel).to_have_value("HVO")
            shore = page.get_by_text("Shore power & investment assumptions", exact=True)
            shore.click()
            scroll(shore, offset=75)
            expect(page.locator("#id_ops_ready")).not_to_be_checked()
            shot("shore_power", page.locator("label[for='id_ops_ready'] span"))
            expect(page.locator("#id_ops_ready")).not_to_be_checked()
            goto("scenario", case.pk)
            button = page.get_by_role("button", name="Compare strategies")
            def calculate():
                button.click()
                expect(page.get_by_role("heading", name="The cost of your next move.")).to_be_visible()
                point(page.locator(".recommendation h2"))
            # Explain the button first, then click. Trim only the subsequent
            # server wait, retaining the click and the full spoken explanation.
            shot("calculate", button, zoom=1, focus=[800,400], after_speech=calculate)
            scroll(page.get_by_role("heading", name="Which strategy costs less?"), offset=50)
            choices = page.locator(".strategy-option")
            expect(choices).to_have_count(4)
            for index, strategy in enumerate(expected["strategies"]):
                option = choices.nth(index)
                expect(option).to_contain_text(f"€{strategy['npv']:,.0f}")
                shot(f"rank_{index+1}", option)
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
            allocation = page.get_by_text("FuelEU annual prioritized energy allocation", exact=True)
            allocation.click()
            scroll(allocation, offset=50)
            allocation_panel = allocation.locator("..")
            expect(allocation_panel).to_have_attribute("open", "")
            allocation_rows = allocation_panel.locator("tbody tr")
            sources = [s for s in expected["strategies"][0]["rows"][0]["fueleu_allocation"] if s["available_energy_mj"]]
            self.assertEqual(allocation_rows.count(), len(sources))
            for index, source in enumerate(sources):
                expect(allocation_rows.nth(index).locator("td").first).to_have_text(source["fuel"])
                # The app formats physical energy to one decimal place.
                displayed = allocation_rows.nth(index).locator("td").last.inner_text().replace(",", "")
                self.assertAlmostEqual(float(displayed), source["allocated_energy_mj"], delta=.051)
            hvo_row = allocation_rows.filter(has=page.get_by_role("cell", name="HVO", exact=True))
            mgo_row = allocation_rows.filter(has=page.get_by_role("cell", name="MGO", exact=True))
            def show_conventional(s):
                page.wait_for_timeout((s["lead"]+s["speech_seconds"]*.54)*1000)
                point(mgo_row.locator("td").last)
            shot("allocation", hvo_row.locator("td").last, during=show_conventional)
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
        self.assertEqual(audit["engine_version"], prepared["engine_version"])
        self.assertEqual(audit["ruleset_version"], prepared["ruleset_version"])
        self.assertEqual(expected["fueleu_allocation_method"], "annual_reward_aware")
        row = best["rows"][0]
        self.assertAlmostEqual(sum(s["allocated_energy_mj"] for s in row["fueleu_allocation"]), row["energy_mj"])
        self.assertAlmostEqual(row["attained_g"], row["target_g"], places=6)
        for strategy in expected["strategies"]:
            self.assertEqual(strategy["annual"][0]["electricity_cost"], 0)
            self.assertEqual(strategy["annual"][0]["electricity_mwh"], 0)
        self.assertEqual(errors, [])
        (OUT / "capture.json").write_text(json.dumps({"recording_wall_seconds":duration,"scenes":scenes},indent=2,ensure_ascii=False),encoding="utf-8")
        print("Verified current-engine audit, all strategy costs, allocation rows, unchanged HVO, no OPS, and no browser errors.", flush=True)
