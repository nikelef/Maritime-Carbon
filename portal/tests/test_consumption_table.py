import csv
import io
import json
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from portal.engine.calculator import profile, simulate
from portal.engine.schema import ScenarioInput, Vessel
from portal.forms import VesselForm, consumption_initial_rows
from portal.models import AnalysisRun, Company, Membership, Scenario


def consumption_case():
    vessel = Vessel(name="Fuel and legs", consumption=[
        {"voyage": 1, "fuel": "HSFO", "intra_t": 100, "extra_t": 200, "outside_t": 300, "eu_berth_t": 40, "non_eu_berth_t": 50, "ops_share": .25},
        {"voyage": 1, "fuel": "MGO", "eu_berth_t": 20, "non_eu_berth_t": 10, "ops_share": 1}])
    return ScenarioInput(start_year=2026, end_year=2026, vessels=[vessel], scope_confirmed=True)


class ConsumptionEngineTests(SimpleTestCase):
    def test_voyages_keep_separate_shore_power_shares_and_add_their_costs(self):
        data = consumption_case()
        vessel = data.vessels[0]
        vessel.ops_ready = True
        vessel.consumption = [{"voyage": 1, "fuel": "HSFO", "extra_t": 100, "eu_berth_t": 40, "ops_share": .25},
                              {"voyage": 2, "fuel": "HSFO", "extra_t": 300, "eu_berth_t": 160, "ops_share": .75}]
        data.validate()
        row = profile(vessel, data, 2026, ops=True)
        self.assertEqual([entry["voyage"] for entry in row["berth_fuels"]], [1, 2])
        self.assertEqual([entry["eu_berth_t"] for entry in row["berth_fuels"]], [30, 40])
        self.assertAlmostEqual(row["electricity_mwh"], 130*40500*.4/.95/3600)
        self.assertEqual(row["fuel_tonnes"]["HSFO"], 470)
        self.assertEqual([entry["voyage"] for entry in row["baseline_fuels"]], [1, 2])

    def test_invalid_voyage_numbers_rejected(self):
        for voyage in (0, 101, -1, True, 1.5, "2", None):
            with self.subTest(voyage=voyage), self.assertRaisesRegex(ValueError, "voyage number"):
                data = consumption_case()
                data.vessels[0].consumption[0]["voyage"] = voyage
                data.validate()

    def test_eu_berth_fully_scoped_other_berth_cost_only(self):
        data = consumption_case()
        data.validate()
        row = profile(data.vessels[0], data, 2026)
        # HSFO: 100 intra + half of 200 extra + all 40 EU berth tonnes.
        # Both outside sea and non-EU berth contribute only to fuel costs.
        hsfo_co2e = 3.114 + .00005*28 + .00018*265
        mgo_co2e = 3.206 + .00005*28 + .00018*265
        self.assertAlmostEqual(row["ets_t"], 240*hsfo_co2e + 20*mgo_co2e)
        self.assertAlmostEqual(row["energy_mj"], 240*40500 + 20*42700)
        self.assertAlmostEqual(row["fuel_cost"], 690*470 + 30*720)
        self.assertEqual(row["berth_t"], 60)
        self.assertEqual(row["non_eu_berth_t"], 60)
        self.assertEqual(row["fuel_tonnes"]["HSFO"], 690)

    def test_ops_uses_each_eu_berth_fuel_lcv_and_replaceable_share(self):
        data = consumption_case()
        vessel = data.vessels[0]
        vessel.ops_ready = True
        row = profile(vessel, data, 2026, ops=True)
        self.assertAlmostEqual(row["electricity_mwh"], (10*40500 + 20*42700)*.4/.95/3600)
        self.assertEqual(row["berth_t"], 30)
        self.assertEqual(row["non_eu_berth_t"], 60)
        self.assertEqual(row["fuel_tonnes"]["HSFO"], 680)
        self.assertEqual(row["fuel_tonnes"]["MGO"], 10)
        # A boiler/non-replaceable fuel row is preserved even with OPS enabled.
        vessel.consumption[0]["ops_share"] = 0
        self.assertEqual(profile(vessel, data, 2026, ops=True)["fuel_tonnes"]["HSFO"], 690)

    def test_non_eu_berth_is_not_replaced_or_counted_in_regulatory_energy(self):
        data = consumption_case()
        data.vessels[0].consumption = [{"fuel": "HSFO", "non_eu_berth_t": 100}]
        data.vessels[0].ops_ready = True
        data.validate()
        row = profile(data.vessels[0], data, 2026, ops=True)
        self.assertEqual(row["energy_mj"], 0)
        self.assertEqual(row["ets_t"], 0)
        self.assertEqual(row["electricity_mwh"], 0)
        self.assertEqual(row["fuel_cost"], 47000)

    def test_berth_methane_uses_separate_consumer(self):
        data = consumption_case()
        vessel = data.vessels[0]
        vessel.consumption = [{"fuel": "LNG", "intra_t": 100, "eu_berth_t": 100}]
        vessel.fuel_consumer = "diesel_slow"
        vessel.fuel_systems_confirmed = True
        vessel.technical_reference = "TEST: separate main and auxiliary engines"
        with self.assertRaisesRegex(ValueError, "select the LNG consumer"):
            data.validate()
        vessel.berth_consumer = "otto_medium"
        data.validate()
        expected = 100*(2.75*(1-.002)+.002*28+.00011*(1-.002)*265)
        expected += 100*(2.75*(1-.031)+.031*28+.00011*(1-.031)*265)
        self.assertAlmostEqual(profile(vessel, data, 2026)["ets_t"], expected)

    def test_renewable_berth_requires_evidence_and_enters_rfnbo_share(self):
        data = consumption_case()
        data.vessels[0].consumption = [{"fuel": "E_DIESEL", "eu_berth_t": 100, "non_eu_berth_t": 100}]
        with self.assertRaisesRegex(ValueError, "current fuel E_DIESEL"):
            data.validate()
        fuel = next(f for f in data.fuels if f.code == "E_DIESEL")
        fuel.eligible, fuel.wtt, fuel.evidence = True, -50, "TEST certified pathway"
        data.validate()
        row = profile(data.vessels[0], data, 2033)
        self.assertEqual(row["rfnbo_share"], 1)
        self.assertEqual(row["rfnbo_energy_mj"], 100*42700)
        self.assertEqual(row["rewarded_energy_mj"], 2*100*42700)

    def test_legacy_conversion_preserves_costs_energy_and_emissions(self):
        data = consumption_case()
        old = Vessel(pilot_t=50, berth_t=125, ops_ready=True, compatible=True,
                     sea_fuels=[{"fuel": "HSFO", "sea_t": 700, "intra_share": .2, "extra_share": .7},
                                {"fuel": "MGO", "sea_t": 50, "intra_share": .8, "extra_share": .1}])
        new = replace(old, consumption=old.consumption_entries())
        hvo = next(f for f in data.fuels if f.code == "HVO")
        hvo.eligible, hvo.evidence = True, "TEST pathway"
        for share, ops in ((0, False), (.3, False), (.3, True)):
            with self.subTest(share=share, ops=ops):
                old_result, new_result = profile(old, data, 2026, share, ops), profile(new, data, 2026, share, ops)
                for key in ("energy_mj", "ets_t", "fuel_cost", "electricity_cost", "attained_g", "balance_t", "alternative_t"):
                    self.assertAlmostEqual(old_result[key], new_result[key], places=6)
                for code in old_result["fuel_tonnes"]:
                    self.assertAlmostEqual(old_result["fuel_tonnes"][code], new_result["fuel_tonnes"][code])

    def test_all_categories_count_toward_supply(self):
        data = consumption_case()
        fuel = next(f for f in data.fuels if f.code == "HSFO")
        fuel.supply_t = 689
        self.assertIsNone(simulate(data, [(0, False)]))
        fuel.supply_t = 690
        self.assertIsNotNone(simulate(data, [(0, False)]))

    def test_malformed_or_empty_consumption_rejected(self):
        for entries in ([], {}, [None], [{"fuel": "HSFO", "intra_t": -1}], [{"fuel": "HSFO", "eu_berth_t": float("nan")}],
                        [{"fuel": "HSFO", "eu_berth_t": True}], [{"fuel": "HSFO", "eu_berth_t": 1, "ops_share": 2}],
                        [{"fuel": "missing", "eu_berth_t": 1}], [{"fuel": "HSFO", "intra_t": 1}]*2,
                        [{"fuel": "HSFO", "eu_berth_t": 0}], [{"fuel": "HSFO", "bogus": 1}]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                data = consumption_case()
                data.vessels[0].consumption = entries
                data.validate()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ConsumptionPortalTests(TestCase):
    def setUp(self):
        company = Company.objects.create(name="Consumption table tests", status="active", access_until=timezone.localdate()+timedelta(days=30))
        user = get_user_model().objects.create_user("table_analyst", password="test-only-password")
        Membership.objects.create(company=company, user=user, role="analyst")
        self.client.force_login(user)
        self.data = consumption_case()
        self.scenario = Scenario.objects.create(company=company, name="Fuel and leg table", created_by=user, inputs=self.data.to_dict())

    def payload(self):
        initial = VesselForm.initial_for(self.data.vessels[0], self.scenario.revision)
        return {key: value for key, value in initial.items() if key not in ("consumption", "consumption_rows", "sea_fuels")}

    def test_same_fuel_category_on_another_voyage_saves_reopens_and_exports(self):
        payload = self.payload() | {"consumption-TOTAL_FORMS": 8, "consumption-7-voyage": 2,
            "consumption-7-fuel": "HSFO", "consumption-7-leg": "eu_berth_t", "consumption-7-tonnes": 160,
            "consumption-7-ops_share": 75}
        response = self.client.post(reverse("vessel_edit", args=[self.scenario.pk, 0]), payload)
        self.assertEqual(response.status_code, 302)
        self.scenario.refresh_from_db()
        stored = self.scenario.inputs["vessels"][0]["consumption"]
        self.assertEqual(stored[-1], {"voyage": 2, "fuel": "HSFO", "eu_berth_t": 160, "ops_share": .75})
        reopened = self.client.get(reverse("vessel_edit", args=[self.scenario.pk, 0]))
        self.assertEqual(reopened.context["form"].consumption_formset[7]["voyage"].value(), 2)
        self.assertEqual(reopened.context["form"].consumption_formset[7]["ops_share"].value(), 75)
        self.client.post(reverse("run_analysis", args=[self.scenario.pk]), {"revision": 2})
        run = AnalysisRun.objects.get(scenario=self.scenario)
        self.assertContains(self.client.get(reverse("report", args=[run.pk])), "Voyage 2")
        exported = json.loads(self.client.get(reverse("export_run", args=[run.pk, "json"])).content)
        self.assertEqual(exported["inputs"]["vessels"][0]["consumption"][-1]["voyage"], 2)
        rows = list(csv.DictReader(io.StringIO(self.client.get(reverse("export_run", args=[run.pk, "csv"])).content.decode("utf-8-sig"))))
        self.assertIn(2, [entry["voyage"] for entry in json.loads(rows[0]["berth_fuels_json"])])

    def test_voyage_is_retained_on_add_and_invalid_choice_is_not_saved(self):
        payload = self.payload() | {"add_sea_fuel": "1", "consumption-0-voyage": 3}
        response = self.client.post(reverse("vessel_edit", args=[self.scenario.pk, 0]), payload)
        self.assertEqual(int(response.context["form"].consumption_formset[0]["voyage"].value()), 3)
        self.scenario.refresh_from_db()
        self.assertEqual(self.scenario.revision, 1)
        payload = self.payload() | {"consumption-0-voyage": 101}
        response = self.client.post(reverse("vessel_edit", args=[self.scenario.pk, 0]), payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].consumption_formset[0].errors["voyage"])
        self.scenario.refresh_from_db()
        self.assertEqual(self.scenario.revision, 1)

    def test_table_saves_repeated_fuel_on_different_legs_and_exports_berth(self):
        response = self.client.post(reverse("vessel_edit", args=[self.scenario.pk, 0]), self.payload())
        self.assertEqual(response.status_code, 302)
        self.scenario.refresh_from_db()
        self.assertEqual(self.scenario.inputs["vessels"][0]["consumption"], self.data.vessels[0].consumption)
        response = self.client.get(reverse("vessel_edit", args=[self.scenario.pk, 0]))
        self.assertEqual(len(response.context["form"].consumption_formset), 7)
        self.assertNotContains(response, "Default voyage mix")
        self.assertNotContains(response, "Annual EU berth MGO")
        self.client.post(reverse("run_analysis", args=[self.scenario.pk]), {"revision": 2})
        run = AnalysisRun.objects.get(scenario=self.scenario)
        self.assertContains(self.client.get(reverse("report", args=[run.pk])), "Non-EU berth fuels")
        rows = list(csv.DictReader(io.StringIO(self.client.get(reverse("export_run", args=[run.pk, "csv"])).content.decode("utf-8-sig"))))
        vessel_row = next(row for row in rows if row["vessel"] == "Fuel and legs")
        self.assertEqual(json.loads(vessel_row["berth_fuels_json"])[0]["fuel"], "HSFO")
        self.assertEqual(float(vessel_row["non_EU_berth_tonnes"]), 60)
        for strategy in run.results["strategies"]:
            self.assertAlmostEqual(sum(float(row["NPV_EUR"]) for row in rows if row["strategy"] == strategy["name"]), strategy["npv"])

    def test_duplicate_fuel_and_leg_rejected_but_draft_is_retained(self):
        payload = self.payload() | {"consumption-1-leg": "intra_t"}
        response = self.client.post(reverse("vessel_edit", args=[self.scenario.pk, 0]), payload)
        self.assertContains(response, "same voyage/berth category")
        self.assertEqual(response.context["form"].consumption_formset[1]["tonnes"].value(), "200")
        self.scenario.refresh_from_db()
        self.assertEqual(self.scenario.revision, 1)

    def test_no_script_add_preserves_incomplete_inputs_without_saving(self):
        payload = self.payload() | {"add_sea_fuel": "1", "gt": "", "consumption-0-tonnes": "1234"}
        response = self.client.post(reverse("vessel_edit", args=[self.scenario.pk, 0]), payload)
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(len(form.consumption_formset), 8)
        self.assertEqual(form.consumption_formset[0]["tonnes"].value(), "1234")
        self.assertFalse(form.errors)
        self.scenario.refresh_from_db()
        self.assertEqual(self.scenario.revision, 1)

    def test_legacy_inputs_are_converted_to_rows_on_get_without_changing_snapshot(self):
        old = Vessel(pilot_t=20, berth_t=100)
        self.data.vessels = [old]
        self.scenario.inputs = self.data.to_dict()
        self.scenario.save()
        self.client.post(reverse("run_analysis", args=[self.scenario.pk]), {"revision": 1})
        run = AnalysisRun.objects.get(scenario=self.scenario)
        saved = deepcopy(run.inputs)
        response = self.client.get(reverse("vessel_edit", args=[self.scenario.pk, 0]))
        form = response.context["form"]
        self.assertEqual(len(form.consumption_formset), len(consumption_initial_rows(old)))
        payload = VesselForm.initial_for(old, 1)
        payload = {key: value for key, value in payload.items() if key not in ("consumption_rows", "sea_fuels")}
        initial_rows = consumption_initial_rows(old)
        payload.update({"consumption-TOTAL_FORMS": len(initial_rows), "consumption-INITIAL_FORMS": len(initial_rows)})
        for index, row in enumerate(initial_rows):
            payload.update({f"consumption-{index}-{key}": value for key, value in row.items()})
        self.assertEqual(self.client.post(reverse("vessel_edit", args=[self.scenario.pk, 0]), payload).status_code, 302)
        self.scenario.refresh_from_db()
        current = ScenarioInput.from_dict(self.scenario.inputs).vessels[0]
        self.assertEqual(current.current_pilot_t, 0)
        self.assertAlmostEqual(current.total_sea_t, 4020)
        self.assertEqual(current.total_eu_berth_t, 100)
        run.refresh_from_db()
        self.assertEqual(run.inputs, saved)

    def test_old_editor_cannot_overwrite_a_saved_consumption_table(self):
        old_payload = {key: value for key, value in VesselForm.initial_for(Vessel(), 1).items() if key != "consumption_rows"}
        response = self.client.post(reverse("vessel_edit", args=[self.scenario.pk, 0]), old_payload)
        self.assertContains(response, "consumption table is missing")
        self.scenario.refresh_from_db()
        self.assertEqual(self.scenario.revision, 1)
