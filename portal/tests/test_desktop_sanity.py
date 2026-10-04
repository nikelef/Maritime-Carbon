"""Desktop release checks using fictional fleets and an isolated database.

RUN_BROWSER_TESTS=1 PLAYWRIGHT_CHANNEL=msedge enables desktop UI checks.
No mobile viewports or saved customer cases are used.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from math import fsum, isfinite
import json
import os
from pathlib import Path
import secrets
from time import perf_counter
from unittest import skipUnless

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from portal.engine.calculator import compare, optimize_fuels, saved_decision, simulate, strategy_actions
from portal.engine.schema import Vessel
from portal.models import AnalysisRun, Company, Membership, Scenario
from portal.tests.test_alternative_fuels import reviewed_case
from portal.tests.test_leg_optimizer import leg_case


def desktop_cases():
    oil = leg_case()
    oil.vessels[0].name = "Demo Atlas"
    oil.vessels[0].consumption.append({"voyage": 2, "fuel": "MGO", "outside_t": 40, "non_eu_berth_t": 10})
    yield "Mixed oils and HVO across two voyages", oil
    fame = deepcopy(oil)
    fame.vessels[0].alternative = "FAME"
    fuel = next(f for f in fame.fuels if f.code == "FAME")
    fuel.eligible = fuel.ets_eligible = True
    fuel.evidence = "TEST ONLY: assumed sustainable FAME batch"
    fame.vessels.append(replace(fame.vessels[0], name="Demo Boreas", consumption=[
        {"voyage": 2, "fuel": "VLSFO", "extra_t": 300, "intra_t": 70},
        {"voyage": 3, "fuel": "MGO", "intra_t": 40, "eu_berth_t": 70, "ops_share": .65}],
        ops_ready=True, ops_capex=0, ops_annual=0, opening_bank=5))
    fuel.supply_t = 15.123456
    yield "Two vessels sharing FAME supply with OPS and bank", fame
    for code in ("LNG", "LBM", "E_METHANOL", "E_AMMONIA", "E_HYDROGEN", "E_DIESEL"):
        case = reviewed_case(code)
        vessel = case.vessels[0]
        vessel.name = "Demo " + code
        vessel.consumption = [{"voyage": 1, "fuel": "VLSFO", "intra_t": 250, "extra_t": 400},
                              {"voyage": 2, "fuel": "MGO", "extra_t": 60, "outside_t": 100,
                               "eu_berth_t": 25, "non_eu_berth_t": 15}]
        vessel.alternative_energy_ratio = .8
        vessel.alternative_pilot_share = 0 if code == "E_HYDROGEN" else .03
        vessel.max_blend = .375
        if code == "LBM":
            vessel.consumption[0]["fuel"] = "LNG"
            vessel.fuel_consumer = "otto_medium"
        if code == "E_DIESEL":
            case.start_year, case.end_year = 2033, 2035
            case.rfnbo_subtarget = "assume_active"
            case.rfnbo_penalty_pd = 500
            case.rfnbo_reference = "TEST ONLY: future-rule stress assumption"
        yield code + " with multiple legs and efficiency", case
    disabled = deepcopy(oil)
    next(f for f in disabled.fuels if f.code == "HVO").eligible = False
    yield "Renewable eligibility disabled", disabled
    outside = deepcopy(oil)
    outside.vessels[0].consumption = [{"voyage": 4, "fuel": "MGO", "outside_t": 100, "non_eu_berth_t": 50}]
    yield "Outside-scope voyages only", outside
    thresholds = deepcopy(oil)
    thresholds.vessels = [replace(oil.vessels[0], name="Demo GT " + str(gt), gt=gt,
                                 consumption=deepcopy(oil.vessels[0].consumption)) for gt in (4999, 5000, 5001)]
    yield "Three vessels around coverage thresholds", thresholds


class FleetSanityTests(SimpleTestCase):
    def test_settlement_roundoff_is_not_presented_as_external_pooling(self):
        result = {"decisions": [{"blend": .02}], "annual": [{"electricity_mwh": 0}],
                  "rows": [{"pool_buy_t": 2.744727112e-9, "pool_transfer_t": 65}],
                  "residual_deficit_t": 0}
        original = deepcopy(result)
        actions = strategy_actions(result)
        self.assertEqual(actions["name"], "Alternative sea fuels + fleet pooling")
        self.assertEqual(actions["external_pool_t"], 0)
        self.assertEqual(result, original)
        result["rows"][0]["pool_buy_t"] = .001
        self.assertIn("external pooling", strategy_actions(result)["name"])

    def test_varied_fleets_conserve_energy_reconcile_costs_and_retain_incumbent(self):
        for title, data in desktop_cases():
            with self.subTest(case=title):
                original = deepcopy(data.to_dict())
                started = perf_counter()
                results = compare(data)
                self.assertEqual(data.to_dict(), original)
                fuels = {f.code: f for f in data.fuels}
                for strategy in results["strategies"]:
                    self.assertTrue(isfinite(strategy["npv"]))
                    self.assertAlmostEqual(strategy["npv"], fsum(a["npv_cost"] for a in strategy["annual"]), places=6)
                    self.assertAlmostEqual(strategy["total"], fsum(a["total_cost"] for a in strategy["annual"]), places=6)
                    replay = simulate(data, [saved_decision(d) for d in strategy["decisions"]], strategy["use_pool"])
                    self.assertAlmostEqual(replay["npv"], strategy["npv"], places=6)
                    if strategy["key"] in ("fuel", "combined"):
                        incumbent = optimize_fuels(data, strategy["use_pool"])
                        self.assertLessEqual(strategy["npv"], incumbent["npv"] + .001)
                    for year in range(data.start_year, data.end_year + 1):
                        rows = [r for r in strategy["rows"] if r["year"] == year]
                        for fuel in data.fuels:
                            if fuel.supply_t is not None:
                                self.assertLessEqual(fsum(r["fuel_tonnes"][fuel.code] for r in rows), fuel.supply_t + 1e-7)
                        for vessel, row in zip(data.vessels, rows):
                            attribution = row["fueleu_allocation"]
                            self.assertAlmostEqual(fsum(s["allocated_energy_mj"] for s in attribution), row["energy_mj"], places=6)
                            self.assertTrue(all(0 <= s["allocated_energy_mj"] <= s["available_energy_mj"] for s in attribution))
                            self.assertLessEqual(row["blend"], vessel.max_blend + 1e-10)
                            self.assertAlmostEqual(row["total_cost"], fsum(row[k] for k in (
                                "fuel_cost", "ets_cost", "electricity_cost", "pool_cost", "penalty_cost", "implementation_cost")), places=6)
                            for leg in row["leg_replacements"]:
                                self.assertAlmostEqual(leg["remaining_t"] + leg["replaced_t"], leg["original_t"], places=8)
                                removed = leg["replaced_t"] * fuels[leg["fuel"]].lcv
                                added = leg["alternative_t"] * fuels[vessel.alternative].lcv + leg["pilot_t"] * fuels["MGO"].lcv
                                self.assertAlmostEqual(added, removed * vessel.alternative_energy_ratio, places=6)
                            annual_reference_cost = fsum(
                                tonnes * fuels[code].price for code, tonnes in row["fuel_tonnes"].items()
                            ) * (1 + data.fuel_escalation) ** (year - data.start_year)
                            self.assertAlmostEqual(row["fuel_cost"], annual_reference_cost, places=6)
                            self.assertAlmostEqual(row["non_eu_berth_t"], vessel.total_non_eu_berth_t, places=8)
                best = results["strategies"][0]
                self.assertLessEqual(best["npv"], results["baseline_npv"] + .001)
                print(f"SANITY {title}: {len(data.vessels)} vessels, {perf_counter()-started:.2f}s, "
                      f"best={best['key']}, NPV={best['npv']:.2f}", flush=True)


@skipUnless(os.environ.get("RUN_BROWSER_TESTS") == "1", "Enable RUN_BROWSER_TESTS=1 for desktop browser checks.")
@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class DesktopReleaseTests(StaticLiveServerTestCase):
    def test_desktop_multi_vessel_leg_choices_and_exports(self):
        from playwright.sync_api import sync_playwright, expect
        password = secrets.token_urlsafe(24)
        company = Company.objects.create(name="Desktop release fixture", status="active",
                                         access_until=timezone.localdate() + timedelta(days=30))
        user = get_user_model().objects.create_user("desktop_release_analyst", password=password)
        Membership.objects.create(company=company, user=user, role="analyst")
        selected_cases = list(desktop_cases())
        selected_cases = [selected_cases[i] for i in (0, 1, 3, 4, 7)]
        scenarios = [Scenario.objects.create(company=company, created_by=user, name=title, inputs=data.to_dict())
                     for title, data in selected_cases]
        artifact_dir = Path(settings.BASE_DIR) / "test-artifacts" / "desktop-release"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        errors = []
        audits = []
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True, channel=os.environ.get("PLAYWRIGHT_CHANNEL") or None)
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.set_default_timeout(60000)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + "/accounts/login/")
            page.get_by_label("Username").fill(user.username)
            page.locator("#id_password").fill(password)
            page.get_by_role("button", name="Sign in securely").click()
            for index, scenario in enumerate(scenarios):
                with self.subTest(case=scenario.name):
                    page.goto(self.live_server_url + f"/cases/{scenario.pk}/vessels/0/")
                    expect(page.locator("#id_consumption-0-voyage")).to_have_value("1")
                    # Exercise actual form saving, including voyage selection and a decimal quantity.
                    if index == 0:
                        page.locator('summary').filter(has_text="Consumption & voyage mix").click()
                        page.locator("#id_consumption-0-voyage").select_option("3")
                        page.locator("#id_consumption-0-tonnes").fill("200.125")
                    page.get_by_role("button", name="Save vessel").click()
                    expect(page.get_by_role("heading", name="Every ship keeps its own balance.")).to_be_visible()
                    page.get_by_role("button", name="Compare strategies").click()
                    expect(page.get_by_role("heading", name="The cost of your next move.")).to_be_visible()
                    expect(page.locator("#annual-chart")).to_be_visible()
                    page.screenshot(path=str(artifact_dir / f"case-{index+1}-overview.png"))
                    strategy_links = page.locator(".strategy-option").evaluate_all("links => links.map(a => a.getAttribute('href'))")
                    report_url = page.url.split("?")[0]
                    for href in strategy_links:
                        page.goto(report_url + href)
                        expect(page.locator(".strategy-option[aria-current='true']")).to_have_count(1)
                        expect(page.locator("[data-strategy-explanation]")).to_be_visible()
                    page.goto(report_url)
                    allocation_summary = page.get_by_text("FuelEU annual prioritized energy allocation", exact=True)
                    allocation_summary.click()
                    expect(page.get_by_role("columnheader", name="Allocated FuelEU MJ").first).to_be_visible()
                    if index == 0:
                        allocation_summary.locator("..").screenshot(path=str(artifact_dir / "prioritized-allocation.png"))
                    for label, extension in (("Download CSV", "csv"), ("Audit file", "json")):
                        with page.expect_download() as download:
                            page.get_by_role("link", name=label).click()
                        saved = artifact_dir / f"case-{index+1}.{extension}"
                        download.value.save_as(str(saved))
                        self.assertIn("leg_replacements", saved.read_text(encoding="utf-8-sig"))
                        self.assertIn("annual_reward_aware", saved.read_text(encoding="utf-8-sig"))
                    audit = json.loads((artifact_dir / f"case-{index+1}.json").read_text(encoding="utf-8"))
                    audits.append((scenario.pk, audit))
                    best = next(s for s in audit["results"]["strategies"] if s["key"] == audit["results"]["best_key"])
                    for decision in best["decisions"]:
                        for remark in decision.get("leg_remarks", []):
                            expect(page.locator("[data-strategy-explanation]")).to_contain_text(remark)
                    if page.locator("[data-leg-remarks]").count():
                        page.locator("[data-strategy-explanation]").screenshot(path=str(artifact_dir / f"case-{index+1}-remarks.png"))
                    print(f"DESKTOP {scenario.name}: report, strategy selection and both exports passed", flush=True)
            browser.close()
        for scenario_id, audit in audits:
            self.assertEqual(audit["results"], AnalysisRun.objects.get(scenario_id=scenario_id).results)
        self.assertEqual(errors, [])
