"""RFNBO physical-energy accounting, independent of annual GHG attribution."""
import csv
import io
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.engine.calculator import compare, leg_demands, profile, simulate
from portal.engine.leg_optimizer import leg_decision
from portal.engine.rules import ENGINE_VERSION, RULESET_VERSION, target
from portal.engine.schema import ScenarioInput, Vessel
from portal.models import AnalysisRun, Company, Membership, Scenario


def stress_case(vessel, end_year=2034):
    return ScenarioInput(start_year=2034, end_year=end_year, scope_confirmed=True,
        rfnbo_subtarget="assume_active", rfnbo_penalty_pd=1000,
        rfnbo_reference="TEST ONLY: future activation and price assumption",
        vessels=[vessel])


def enable_fuel(data, code, **factors):
    fuel = next(f for f in data.fuels if f.code == code)
    fuel.eligible, fuel.evidence = True, "TEST ONLY: reviewed pathway"
    for name, value in factors.items():
        setattr(fuel, name, value)


def rfnbo_omitted_case():
    data = stress_case(Vessel(alternative="E_DIESEL", max_blend=0,
        fuel_systems_confirmed=True, technical_reference="TEST system review",
        consumption=[dict(fuel="HVO", extra_t=975),
                     dict(fuel="E_DIESEL", extra_t=25)]))
    enable_fuel(data, "HVO", wtw=5)
    enable_fuel(data, "E_DIESEL", wtt=-56.36744730679157)  # Complete WtW = 20.
    return data


def ops_omitted_case(end_year=2034):
    data = stress_case(Vessel(max_blend=0, ops_ready=True,
        consumption=[dict(fuel="HVO", extra_t=1000),
                     dict(fuel="MGO", eu_berth_t=100)]), end_year)
    enable_fuel(data, "HVO", wtw=-10)
    return data


class RFNBOPhysicalAccountingTests(SimpleTestCase):
    def test_consumed_rfnbo_meets_subtarget_when_ghg_allocation_omits_it(self):
        data = rfnbo_omitted_case()
        data.validate()
        row = simulate(data, [(0, False)])["rows"][0]
        # Both streams are physically 50% in scope. The RFNBO exceeds 2%
        # even without taking advantage of free annual source attribution.
        self.assertEqual(row["fuel_energy_mj"], 21_983_750)
        self.assertEqual(row["rfnbo_energy_mj"], 533_750)
        self.assertAlmostEqual(row["rfnbo_share"], 533750 / 21983750)
        self.assertGreater(row["rfnbo_share"], .02)
        self.assertEqual(row["allocated_rfnbo_energy_mj"], 0)
        self.assertEqual(row["rfnbo_deficit_mj"], 0)
        self.assertEqual(row["rfnbo_penalty_cost"], 0)
        self.assertEqual(row["penalty_years"], 0)
        # Annual GHG attribution still uses only the lower-intensity HVO.
        self.assertEqual(row["attained_g"], 5)
        self.assertEqual(row["rewarded_energy_mj"], 21_983_750)
        self.assertAlmostEqual(row["balance_t"], (target(2034)-5)*21983750/1e6)

    def test_actual_ops_is_excluded_when_negative_fuel_displaces_its_allocation(self):
        data = ops_omitted_case()
        data.validate()
        row = simulate(data, [(0, True)])["rows"][0]
        electricity_mj = 100*42700*.4/.95
        self.assertAlmostEqual(row["electricity_mwh"], electricity_mj/3600)
        self.assertAlmostEqual(row["energy_mj"], 22_000_000+electricity_mj)
        self.assertEqual(row["fuel_energy_mj"], 22_000_000)
        self.assertEqual(row["rfnbo_deficit_mj"], 440_000)
        self.assertAlmostEqual(row["rfnbo_penalty_cost"], 440000/41000*1000)
        self.assertEqual(row["allocated_fuel_energy_mj"], row["energy_mj"])
        ops = next(s for s in row["fueleu_allocation"] if s["fuel"] == "OPS")
        self.assertEqual(ops["allocated_energy_mj"], 0)
        self.assertEqual(row["attained_g"], -10)
        self.assertAlmostEqual(row["balance_t"],
            (target(2034)+10)*(22000000+electricity_mj)/1e6)

    def test_mixed_scope_switching_pilot_wind_and_berth_use_physical_energy(self):
        wind_mgo = {leg: dict(propulsion_share=.5, net_saving=.2)
                    for leg in ("intra_t", "extra_t", "outside_t")}
        wind_rfnbo = {leg: dict(propulsion_share=1, net_saving=.2)
                      for leg in ("intra_t", "extra_t", "outside_t")}
        vessel = Vessel(alternative="E_DIESEL", max_blend=1, compatible=True,
            alternative_energy_ratio=.8, alternative_pilot_share=.1,
            fuel_systems_confirmed=True, technical_reference="TEST system review",
            wind_mode="retrofit", wind_confirmed=True, wind_reference="TEST savings",
            ops_ready=True, consumption=[
                dict(voyage=1, fuel="MGO", intra_t=100, extra_t=200, outside_t=300,
                     eu_berth_t=20, non_eu_berth_t=30, ops_share=.75, wind=wind_mgo),
                dict(voyage=2, fuel="E_DIESEL", intra_t=10, extra_t=20, outside_t=30,
                     eu_berth_t=40, non_eu_berth_t=50, ops_share=.5, wind=wind_rfnbo)])
        data = stress_case(vessel)
        data.start_year = 2033
        enable_fuel(data, "E_DIESEL", wtt=-56.36744730679157)
        data.validate()
        demands = leg_demands(vessel, data)
        fractions = {key: {"intra_t": .25, "extra_t": .5, "outside_t": 1}[d["leg"]]
                     if d["fuel"] == "MGO" else 0 for key, d in demands.items()}
        decision = leg_decision(demands, fractions, True, True)
        # After wind: MGO sea = 90/180/270 t and RFNBO = 8/16/24 t.
        # Remaining scoped MGO including berth = 67.5+90/2+5 = 117.5 t.
        # Existing scoped RFNBO including berth = 8+16/2+20 = 36 t.
        # Replaced scoped demand = 22.5+90/2 = 67.5 MGO-equivalent t.
        fuel_energy = (117.5+36+67.5*.8)*42700
        rfnbo_energy = (36+67.5*.8*.9)*42700
        ops_energy = (20*.75+40*.5)*42700*.4/.95
        # Full MRV-eligible RFNBO sources remain available for GHG allocation.
        allocated_rfnbo = (8+16+20+(22.5+90)*.8*.9)*42700
        mgo_wtw = 14.4+(3.206+.00005*25+.00018*298)*1e6/42700
        for year, reward in ((2033, 2), (2034, 1)):
            with self.subTest(year=year):
                row = profile(vessel, data, year, *decision)
                self.assertAlmostEqual(row["fuel_energy_mj"], fuel_energy)
                self.assertAlmostEqual(row["rfnbo_energy_mj"], rfnbo_energy)
                self.assertAlmostEqual(row["energy_mj"], fuel_energy+ops_energy)
                self.assertAlmostEqual(row["allocated_rfnbo_energy_mj"], allocated_rfnbo)
                rewarded_energy = fuel_energy+ops_energy+(reward-1)*allocated_rfnbo
                expected_intensity = (allocated_rfnbo*20+
                    (fuel_energy-allocated_rfnbo)*mgo_wtw)/rewarded_energy
                self.assertAlmostEqual(row["rewarded_energy_mj"], rewarded_energy)
                self.assertAlmostEqual(row["attained_g"], expected_intensity)
                self.assertAlmostEqual(row["balance_t"],
                    (target(year)-expected_intensity)*(fuel_energy+ops_energy)/1e6)
                self.assertEqual(row["rfnbo_deficit_mj"], 0)
                self.assertAlmostEqual(row["wind_saved_t"], 72)
                self.assertEqual(row["non_eu_berth_t"], 80)

    def test_reward_election_does_not_change_physical_subtarget_quantities(self):
        data = rfnbo_omitted_case()
        data.start_year, data.end_year = 2033, 2034
        # Make RFNBO beneficial in the rewarded GHG allocation as well.
        next(f for f in data.fuels if f.code == "HVO").wtw = 15
        enabled = profile(data.vessels[0], data, 2033)
        next(f for f in data.fuels if f.code == "E_DIESEL").reward_enabled = False
        disabled = profile(data.vessels[0], data, 2033)
        expired = profile(data.vessels[0], data, 2034)
        self.assertGreater(enabled["allocated_rfnbo_energy_mj"], 0)
        self.assertEqual(disabled["allocated_rfnbo_energy_mj"], 0)
        self.assertGreater(enabled["rewarded_energy_mj"], enabled["energy_mj"])
        self.assertEqual([row["rfnbo_reward"] for row in (enabled, disabled, expired)], [2, 1, 1])
        for row in (enabled, disabled, expired):
            self.assertEqual(row["rfnbo_energy_mj"], 533750)
            self.assertEqual(row["fuel_energy_mj"], 21983750)
            self.assertEqual(row["rfnbo_deficit_mj"], 0)

    def test_charge_streak_and_annual_totals_use_corrected_physical_shortfall(self):
        data = ops_omitted_case(end_year=2035)
        data.vessels[0].opening_bank = 10000
        data.vessels[0].prior_penalties = 2
        data.validate()
        result = simulate(data, [(0, True)], True)
        base_charge = 440000/41000*1000
        for index, (row, annual) in enumerate(zip(result["rows"], result["annual"])):
            self.assertEqual(row["penalty_years"], index+3)
            self.assertEqual(row["ghg_penalty_cost"], 0)
            self.assertAlmostEqual(row["rfnbo_penalty_cost"], base_charge*(1.2+index*.1))
            self.assertEqual(row["penalty_cost"], row["rfnbo_penalty_cost"])
            self.assertEqual(annual["fuel_energy_mj"], 22000000)
            self.assertEqual(annual["rfnbo_deficit_mj"], 440000)
            self.assertEqual(annual["rfnbo_penalty_cost"], row["rfnbo_penalty_cost"])
        self.assertAlmostEqual(result["npv"],
            simulate(data, [(0, True)], True, score_only=True))

    def test_unresolved_case_reports_physical_shortfall_without_charge_or_streak(self):
        data = ops_omitted_case(end_year=2035)
        data.rfnbo_subtarget = "unresolved"
        data.rfnbo_penalty_pd = None
        data.validate()
        for row in simulate(data, [(0, True)])["rows"]:
            self.assertEqual(row["rfnbo_deficit_mj"], 440000)
            self.assertFalse(row["rfnbo_subtarget_active"])
            self.assertEqual(row["rfnbo_penalty_cost"], 0)
            self.assertEqual(row["penalty_years"], 0)

    def test_fueleu_scope_threshold_and_outside_activity_exclude_physical_energy(self):
        for gt, leg in ((5000, "extra_t"), (4999, "intra_t"), (25000, "outside_t")):
            with self.subTest(gt=gt, leg=leg):
                data = rfnbo_omitted_case()
                data.vessels[0].gt = gt
                data.vessels[0].consumption = [dict(fuel="E_DIESEL", **{leg: 25})]
                data.validate()
                row = profile(data.vessels[0], data, 2034)
                for name in ("fuel_energy_mj", "rfnbo_energy_mj", "rfnbo_deficit_mj"):
                    self.assertEqual(row[name], 0)

    def test_new_comparisons_identify_physical_subtarget_accounting(self):
        result = compare(rfnbo_omitted_case())
        self.assertEqual(result["rfnbo_subtarget_accounting_method"], "physical_scoped")
        for strategy in result["strategies"]:
            for row in strategy["rows"]:
                self.assertEqual(row["rfnbo_subtarget_accounting_method"], "physical_scoped")


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RFNBOPhysicalExportTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="RFNBO accounting tests", status="active",
            access_until=timezone.localdate()+timedelta(days=30))
        self.user = get_user_model().objects.create_user("rfnbo_analyst", password="test-only-password")
        Membership.objects.create(company=self.company, user=self.user, role="analyst")
        self.client.force_login(self.user)

    def export_case(self, data, decision):
        data.validate()
        scenario = Scenario.objects.create(company=self.company, name="Physical RFNBO audit",
            inputs=data.to_dict(), created_by=self.user)
        strategy = simulate(data, [decision])
        strategy.update(key="baseline", name="Audit reference")
        run = AnalysisRun.objects.create(company=self.company, scenario=scenario,
            scenario_name=scenario.name, scenario_revision=1, inputs=data.to_dict(),
            results={"strategies": [strategy]}, input_digest="test-only-digest",
            engine_version=ENGINE_VERSION, ruleset_version=RULESET_VERSION, created_by=self.user)
        response = self.client.get(reverse("export_run", args=[run.pk, "json"]))
        self.assertEqual(response.status_code, 200)
        json_row = json.loads(response.content)["results"]["strategies"][0]["rows"][0]
        response = self.client.get(reverse("export_run", args=[run.pk, "csv"]))
        self.assertEqual(response.status_code, 200)
        csv_rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertTrue(all(None not in row for row in csv_rows))
        return json_row, csv_rows[0]

    def test_exports_distinguish_physical_rfnbo_from_zero_ghg_attribution(self):
        row, exported = self.export_case(rfnbo_omitted_case(), (0, False))
        self.assertEqual(row["rfnbo_energy_mj"], 533750)
        self.assertEqual(row["allocated_rfnbo_energy_mj"], 0)
        self.assertEqual(float(exported["RFNBO_energy_MJ"]), 533750)
        self.assertAlmostEqual(float(exported["RFNBO_share"]), 533750/21983750)
        self.assertEqual(float(exported["RFNBO_potential_shortfall_MJ"]), 0)
        self.assertEqual(float(exported["RFNBO_assumed_penalty_EUR"]), 0)
        allocation = json.loads(exported["FuelEU_annual_allocation_json"])
        self.assertEqual(next(s["allocated_energy_mj"] for s in allocation
                              if s["fuel"] == "E_DIESEL"), 0)

    def test_exports_preserve_unresolved_shortfall_and_zero_assumed_charge(self):
        data = ops_omitted_case()
        data.rfnbo_subtarget, data.rfnbo_penalty_pd = "unresolved", None
        row, exported = self.export_case(data, (0, True))
        self.assertEqual(row["fuel_energy_mj"], 22000000)
        self.assertEqual(row["rfnbo_deficit_mj"], 440000)
        self.assertFalse(row["rfnbo_subtarget_active"])
        self.assertEqual(float(exported["RFNBO_potential_shortfall_MJ"]), 440000)
        self.assertEqual(float(exported["RFNBO_assumed_penalty_EUR"]), 0)
        self.assertEqual(float(exported["FuelEU_penalty_EUR"]), 0)

    def test_exports_include_corrected_active_charge_and_prior_penalty_uplift(self):
        data = ops_omitted_case(end_year=2035)
        data.vessels[0].prior_penalties = 2
        row, exported = self.export_case(data, (0, True))
        expected = 440000/41000*1000*1.2
        self.assertEqual(row["penalty_years"], 3)
        self.assertEqual(row["rfnbo_subtarget_accounting_method"], "physical_scoped")
        self.assertAlmostEqual(row["rfnbo_penalty_cost"], expected)
        self.assertEqual(row["fuel_energy_mj"], 22000000)
        self.assertGreater(row["allocated_fuel_energy_mj"], row["fuel_energy_mj"])
        self.assertAlmostEqual(float(exported["RFNBO_assumed_penalty_EUR"]), expected)
        self.assertAlmostEqual(float(exported["FuelEU_penalty_EUR"]), expected)
