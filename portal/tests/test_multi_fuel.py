"""Mixed-fuel mass/energy accounting and the saved-vessel workflow."""
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
from portal.forms import VesselForm
from portal.models import AnalysisRun, Company, Membership, Scenario


def mixed_case():
    vessel = Vessel(name="Mixed oils", berth_t=20, pilot_t=5, intra_share=.3, extra_share=.6,
                    sea_fuels=[{"fuel": "HSFO", "sea_t": 1000, "intra_share": .1, "extra_share": .8},
                               {"fuel": "VLSFO", "sea_t": 600, "intra_share": .4, "extra_share": .4},
                               {"fuel": "MGO", "sea_t": 100, "intra_share": 1, "extra_share": 0}])
    return ScenarioInput(start_year=2026, end_year=2026, scope_confirmed=True, vessels=[vessel])


class MultiFuelEngineTests(SimpleTestCase):
    def test_cost_energy_and_emissions_use_each_fuel_and_its_scope(self):
        data = mixed_case()
        data.validate()
        row = profile(data.vessels[0], data, 2026)
        # Independently hand-summed tonnes, energy and Annex oil factors.
        scoped_residual = 1000 * .5 + 600 * .6
        scoped_mgo = 100 + 5 * .6 + 20
        expected_energy = scoped_residual * 40500 + scoped_mgo * 42700
        residual_ttw = 3.114 + .00005 * 28 + .00018 * 265
        mgo_ttw = 3.206 + .00005 * 28 + .00018 * 265
        expected_ets = scoped_residual * residual_ttw + scoped_mgo * mgo_ttw
        expected_ghg = scoped_residual * (40500 * 13.5 + residual_ttw * 1e6) + scoped_mgo * (42700 * 14.4 + mgo_ttw * 1e6)
        self.assertAlmostEqual(row["fuel_cost"], 1000 * 470 + 600 * 575 + 125 * 720)
        self.assertAlmostEqual(row["energy_mj"], expected_energy)
        self.assertAlmostEqual(row["ets_t"], expected_ets)
        self.assertAlmostEqual(row["attained_g"], expected_ghg / expected_energy)
        self.assertEqual(row["fuel_tonnes"], {f.code: {"HSFO": 1000, "VLSFO": 600, "MGO": 125}.get(f.code, 0) for f in data.fuels})

    def test_switching_preserves_total_and_scoped_service_energy(self):
        data = mixed_case()
        vessel = data.vessels[0]
        vessel.compatible = True
        vessel.max_blend = 1
        vessel.alternative_energy_ratio = .8
        vessel.alternative_pilot_share = .02
        hvo = next(f for f in data.fuels if f.code == "HVO")
        hvo.eligible, hvo.evidence = True, "TEST pathway"
        baseline = profile(vessel, data, 2026)
        reference_energy = 1600 * 40500 + 105 * 42700
        for share in (0, .25, 1):
            with self.subTest(share=share):
                row = profile(vessel, data, 2026, share)
                self.assertEqual([entry["sea_t"] for entry in row["baseline_fuels"]], [1000 * (1-share), 600 * (1-share), 100 * (1-share)])
                self.assertAlmostEqual(row["alternative_t"], reference_energy * share * .8 * .98 / 44000)
                self.assertAlmostEqual(row["pilot_t"], 5 * (1-share) + reference_energy * share * .8 * .02 / 42700)
                self.assertAlmostEqual(row["energy_mj"], (baseline["energy_mj"] - 20 * 42700) * (1-share + share*.8) + 20*42700)

    def test_single_row_matches_legacy_for_baseline_switching_and_ops(self):
        data = mixed_case()
        hvo = next(f for f in data.fuels if f.code == "HVO")
        hvo.eligible, hvo.evidence = True, "TEST pathway"
        legacy = Vessel(sea_t=1800, pilot_t=40, compatible=True, max_blend=1, ops_ready=True)
        mixed = replace(legacy, sea_fuels=[{"fuel": "VLSFO", "sea_t": 1800}])
        for share, ops in ((0, False), (.3, False), (1, True)):
            old, new = profile(legacy, data, 2026, share, ops), profile(mixed, data, 2026, share, ops)
            self.assertEqual(old, new)

    def test_each_fuel_supply_cap_includes_all_uses(self):
        data = mixed_case()
        mgo = next(f for f in data.fuels if f.code == "MGO")
        mgo.supply_t = 125
        self.assertIsNotNone(simulate(data, [(0, False)]))
        mgo.supply_t = 124
        self.assertIsNone(simulate(data, [(0, False)]))
        mgo.supply_t = None
        next(f for f in data.fuels if f.code == "VLSFO").supply_t = 599
        self.assertIsNone(simulate(data, [(0, False)]))

    def test_malformed_mix_is_rejected(self):
        invalid = [None, {}, [None], [{"fuel": [] , "sea_t": 1}], [{"fuel": "unknown", "sea_t": 1}],
                   [{"fuel": "HSFO", "sea_t": float("nan")}], [{"fuel": "HSFO", "sea_t": -1}],
                   [{"fuel": "HSFO", "sea_t": True}], [{"fuel": "HSFO"}],
                   [{"fuel": "HSFO", "sea_t": 1, "intra_share": .8, "extra_share": .8}],
                   [{"fuel": "HSFO", "sea_t": 1}] * 2, [{"fuel": "HSFO", "sea_t": 1, "extra": 0}]]
        for entries in invalid:
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                data = mixed_case()
                data.vessels[0].sea_fuels = entries
                data.validate()

    def test_all_current_fuels_require_evidence_and_methane_engine(self):
        data = mixed_case()
        data.vessels[0].sea_fuels.append({"fuel": "HVO", "sea_t": 10})
        with self.assertRaisesRegex(ValueError, "current fuel HVO"):
            data.validate()
        data.vessels[0].sea_fuels[-1]["fuel"] = "LNG"
        with self.assertRaisesRegex(ValueError, "LNG consumer"):
            data.validate()
        vessel = data.vessels[0]
        vessel.fuel_consumer = "diesel_slow"
        vessel.fuel_systems_confirmed = True
        vessel.technical_reference = "TEST engine and pilot review"
        data.validate()
        row = profile(vessel, data, 2026)
        self.assertEqual(row["baseline_slip_pct"], .2)
        self.assertGreater(row["fuel_tonnes"]["LNG"], 0)

    def test_roundtrip_and_old_json_without_mix(self):
        data = mixed_case()
        restored = ScenarioInput.from_dict(json.loads(json.dumps(data.to_dict())))
        self.assertEqual(restored.to_dict(), data.to_dict())
        raw = ScenarioInput(vessels=[Vessel()], scope_confirmed=True).to_dict()
        raw["vessels"][0].pop("sea_fuels")
        restored = ScenarioInput.from_dict(raw)
        restored.validate()
        self.assertEqual(restored.vessels[0].total_sea_t, 4000)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class MultiFuelPortalTests(TestCase):
    def setUp(self):
        company = Company.objects.create(name="Mixed-fuel tests", status="active", access_until=timezone.localdate()+timedelta(days=30))
        user = get_user_model().objects.create_user("mixed_analyst", password="test-only-password")
        Membership.objects.create(company=company, user=user, role="analyst")
        self.client.force_login(user)
        self.data = mixed_case()
        self.scenario = Scenario.objects.create(company=company, name="Mixed oils", inputs=self.data.to_dict(), created_by=user)

    def payload(self):
        payload = VesselForm.initial_for(self.data.vessels[0], self.scenario.revision)
        payload.pop("sea_fuels")
        payload.pop("fuel")
        payload.pop("sea_t")
        return payload

    def test_save_reopen_compare_and_export_all_fuels(self):
        response = self.client.post(reverse("vessel_edit", args=[self.scenario.pk, 0]), self.payload())
        self.assertEqual(response.status_code, 302)
        self.scenario.refresh_from_db()
        saved = self.scenario.inputs["vessels"][0]
        self.assertEqual(saved["sea_fuels"], self.data.vessels[0].sea_fuels)
        self.assertEqual(saved["sea_t"], 1700)
        reopened = self.client.get(reverse("vessel_edit", args=[self.scenario.pk, 0]))
        self.assertContains(reopened, "MGO / LSMGO")
        self.assertEqual(len(reopened.context["form"].sea_fuel_formset), 3)
        self.assertEqual(self.client.post(reverse("run_analysis", args=[self.scenario.pk]), {"revision": 2}).status_code, 302)
        run = AnalysisRun.objects.get(scenario=self.scenario)
        self.assertEqual(self.client.get(reverse("report", args=[run.pk])).status_code, 200)
        exported = json.loads(self.client.get(reverse("export_run", args=[run.pk, "json"])).content)
        self.assertEqual(len(exported["inputs"]["vessels"][0]["sea_fuels"]), 3)
        rows = list(csv.DictReader(io.StringIO(self.client.get(reverse("export_run", args=[run.pk, "csv"])).content.decode("utf-8-sig"))))
        fuel_row = next(row for row in rows if row["vessel"] == "Mixed oils")
        self.assertEqual(len(json.loads(fuel_row["current_sea_fuels_json"])), 3)
        self.assertEqual(json.loads(fuel_row["total_fuel_tonnes_json"])["MGO"], 125)
        self.assertTrue(all(None not in row for row in rows))
        for strategy in run.results["strategies"]:
            self.assertAlmostEqual(sum(float(row["NPV_EUR"]) for row in rows if row["strategy"] == strategy["name"]), strategy["npv"])

    def test_remove_row_and_inherit_default_shares(self):
        payload = self.payload()
        payload.update({"sea_fuels-1-DELETE": "on", "sea_fuels-0-intra_share": "", "sea_fuels-0-extra_share": ""})
        self.assertEqual(self.client.post(reverse("vessel_edit", args=[self.scenario.pk, 0]), payload).status_code, 302)
        self.scenario.refresh_from_db()
        vessel = ScenarioInput.from_dict(self.scenario.inputs).vessels[0]
        self.assertEqual([row["fuel"] for row in vessel.sea_fuels], ["HSFO", "MGO"])
        self.assertEqual(vessel.sea_fuel_entries()[0]["intra_share"], .3)
        self.assertEqual(vessel.sea_fuel_entries()[0]["extra_share"], .6)

    def test_invalid_rows_do_not_save_and_keep_entered_mix(self):
        for changes in ({"sea_fuels-1-fuel": "HSFO"}, {"sea_fuels-0-sea_t": "-1"},
                        {"sea_fuels-0-intra_share": "90"}, {"sea_fuels-0-fuel": "unknown"},
                        {"sea_fuels-TOTAL_FORMS": "1000"}, {"sea_fuels-TOTAL_FORMS": "0"}):
            with self.subTest(changes=changes):
                payload = self.payload() | changes
                response = self.client.post(reverse("vessel_edit", args=[self.scenario.pk, 0]), payload)
                self.assertEqual(response.status_code, 200)
                self.scenario.refresh_from_db()
                self.assertEqual(self.scenario.revision, 1)
                self.assertEqual(self.scenario.inputs, self.data.to_dict())

    def test_missing_formset_cannot_silently_replace_a_saved_mix(self):
        payload = VesselForm.initial_for(Vessel(), 1)
        response = self.client.post(reverse("vessel_edit", args=[self.scenario.pk, 0]), payload)
        self.assertContains(response, "fuel rows are missing")
        self.scenario.refresh_from_db()
        self.assertEqual(self.scenario.revision, 1)

    def test_add_fuel_without_javascript_preserves_unsaved_fields(self):
        payload = self.payload() | {"add_sea_fuel": "1", "name": "Draft name", "sea_fuels-0-sea_t": "1234", "sea_fuels-1-DELETE": "on", "gt": ""}
        response = self.client.post(reverse("vessel_edit", args=[self.scenario.pk, 0]), payload)
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(len(form.sea_fuel_formset), 4)
        self.assertEqual(form["name"].value(), "Draft name")
        self.assertEqual(form["gt"].value(), "")
        self.assertEqual(form.sea_fuel_formset[0]["sea_t"].value(), "1234")
        self.assertTrue(form.sea_fuel_formset[1]["DELETE"].value())
        self.assertFalse(form.errors)
        self.assertFalse(form.sea_fuel_formset.non_form_errors())
        self.scenario.refresh_from_db()
        self.assertEqual(self.scenario.revision, 1)
        self.assertEqual(self.scenario.inputs, self.data.to_dict())

    def test_add_fuel_rejects_invalid_management_counts_without_writing(self):
        for total in ("-1", "9999", "bad", "40"):
            response = self.client.post(reverse("vessel_edit", args=[self.scenario.pk, 0]), self.payload() | {"add_sea_fuel": "1", "sea_fuels-TOTAL_FORMS": total})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].non_field_errors())
            self.scenario.refresh_from_db()
            self.assertEqual(self.scenario.revision, 1)

    def test_existing_snapshot_keeps_original_mix_after_edit(self):
        self.client.post(reverse("run_analysis", args=[self.scenario.pk]), {"revision": 1})
        run = AnalysisRun.objects.get(scenario=self.scenario)
        original = deepcopy(run.inputs)
        payload = self.payload() | {"sea_fuels-0-sea_t": 2000}
        self.assertEqual(self.client.post(reverse("vessel_edit", args=[self.scenario.pk, 0]), payload).status_code, 302)
        run.refresh_from_db()
        self.assertEqual(run.inputs, original)
