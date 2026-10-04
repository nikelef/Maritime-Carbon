"""Mandatory fossil defaults, server enforcement and explicit legacy repair."""
from copy import deepcopy
from dataclasses import asdict

from django.test import SimpleTestCase

from portal.engine.calculator import compare, profile
from portal.engine.schema import ScenarioInput, Vessel, fossil_oil_defaults
from portal.forms import FuelForm


def oil_case():
    return ScenarioInput(start_year=2026, end_year=2026, scope_confirmed=True,
                         vessels=[Vessel(name="Oil defaults", fuel="MGO", sea_t=1000,
                                         berth_t=0, intra_share=1, extra_share=0)])


def submitted_form(fuel, **changes):
    initial = asdict(fuel) | {"revision": 1, "ets_eligible": fuel.ets_zero_rated}
    return FuelForm(initial | changes, fuel=fuel, initial=initial)


class FossilDefaultTests(SimpleTestCase):
    def test_supported_default_paths_match_independent_annex_calculations(self):
        case = oil_case()
        case.validate()
        for code, lcv, co2, wtt in (("HSFO", 40500, 3.114, 13.5),
                                    ("VLSFO", 40500, 3.114, 13.5),
                                    ("MGO", 42700, 3.206, 14.4)):
            with self.subTest(code=code):
                fuel = next(f for f in case.fuels if f.code == code)
                expected = wtt + (co2 + .00005 * 25 + .00018 * 298) * 1e6 / lcv
                self.assertEqual(fuel.wtw, expected)
                self.assertEqual(fuel.wtt, wtt)
                self.assertEqual(fossil_oil_defaults(code)["wtw"], expected)
        row = profile(case.vessels[0], case, 2026)
        self.assertAlmostEqual(row["attained_g"], 90.76744730679158)
        self.assertAlmostEqual(row["balance_t"], -61.08864)
        self.assertAlmostEqual(row["ets_t"], 3255.1)

    def test_engine_rejects_prohibited_overrides_even_without_the_form(self):
        for code in ("HSFO", "VLSFO", "MGO"):
            canonical = fossil_oil_defaults(code)
            for field, value in (("co2", 1), ("wtw", canonical["wtw"] - canonical["wtt"]),
                                  ("wtt", 0), ("lcv", 40000), ("ch4", 0), ("n2o", 0)):
                with self.subTest(code=code, field=field):
                    case = oil_case()
                    setattr(next(f for f in case.fuels if f.code == code), field, value)
                    with self.assertRaisesRegex(ValueError, "supported Annex II fossil defaults"):
                        compare(case)

    def test_modified_known_code_cannot_disguise_its_fossil_pathway(self):
        for field, value in (("renewable", True), ("pathway", "hydrogen_cell")):
            fuel = next(f for f in oil_case().fuels if f.code == "HSFO")
            setattr(fuel, field, value)
            self.assertRaises(ValueError, fuel.validate)

    def test_tampered_form_uses_canonical_factors_and_preserves_commercial_inputs(self):
        for code in ("HSFO", "VLSFO", "MGO"):
            with self.subTest(code=code):
                fuel = next(f for f in oil_case().fuels if f.code == code)
                form = submitted_form(fuel, co2=1, ch4=0, n2o=0, lcv=150000,
                                      wtw=1, wtt=0, price=913, supply_t=50,
                                      evidence="Reviewed batch and monitoring plan")
                self.assertTrue(form.is_valid(), form.errors)
                for key, value in fossil_oil_defaults(code).items():
                    self.assertEqual(form.cleaned_data[key], value)
                self.assertEqual(form.cleaned_data["price"], 913)
                self.assertEqual(form.cleaned_data["supply_t"], 50)
                self.assertEqual(form.cleaned_data["evidence"], "Reviewed batch and monitoring plan")
                for field in ("lcv", "co2", "ch4", "n2o", "wtw"):
                    self.assertTrue(form.fields[field].disabled)

    def test_old_override_is_rejected_until_explicit_fuel_save_repairs_it(self):
        case = oil_case()
        fuel = next(f for f in case.fuels if f.code == "MGO")
        fuel.co2, fuel.wtw, fuel.wtt, fuel.ch4 = 1, 40, 0, 0
        fuel.price, fuel.supply_t, fuel.evidence = 913, 1200, "Existing batch reference"
        old_inputs = deepcopy(case.to_dict())
        with self.assertRaises(ValueError):
            case.validate()
        # Merely opening the editor must leave the saved override untouched.
        form = submitted_form(fuel)
        self.assertEqual(case.to_dict(), old_inputs)
        self.assertEqual(form.initial["wtw"], fossil_oil_defaults("MGO")["wtw"])
        self.assertTrue(form.is_valid(), form.errors)
        for key, value in form.cleaned_data.items():
            if key != "revision":
                setattr(fuel, key, value)
        case.validate()
        row = profile(case.vessels[0], case, 2026)
        self.assertAlmostEqual(row["balance_t"], -61.08864)
        self.assertAlmostEqual(row["ets_t"], 3255.1)
        self.assertEqual((fuel.price, fuel.supply_t, fuel.evidence),
                         (913, 1200, "Existing batch reference"))
        # An old serialized snapshot remains unchanged by the explicit repair.
        old_mgo = next(f for f in old_inputs["fuels"] if f["code"] == "MGO")
        self.assertEqual((old_mgo["co2"], old_mgo["wtw"]), (1, 40))

    def test_valid_legacy_oil_without_explicit_wtt_still_runs(self):
        case = oil_case()
        for fuel in case.fuels:
            if fossil_oil_defaults(fuel.code) is not None:
                fuel.wtt = None
        case.validate()

    def test_renewable_pathway_factors_remain_editable(self):
        case = oil_case()
        fuel = next(f for f in case.fuels if f.code == "HVO")
        form = submitted_form(fuel, co2=3.115, ch4=.00002, n2o=.00012,
                              wtw=17, eligible=True, ets_eligible=False,
                              evidence="Supplier-certified renewable pathway")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.fields["co2"].disabled)
        self.assertFalse(form.fields["wtw"].disabled)
        for key, value in form.cleaned_data.items():
            if key != "revision":
                setattr(fuel, key, value)
        fuel.validate()
        self.assertEqual((fuel.co2, fuel.ch4, fuel.n2o, fuel.wtw),
                         (3.115, .00002, .00012, 17))
        self.assertFalse(fuel.ets_zero_rated)
        self.assertIsNone(fossil_oil_defaults("HVO"))
