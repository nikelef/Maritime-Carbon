"""Independent reference calculations for the v6 fuel/consumer contract."""
from copy import deepcopy
from dataclasses import replace
from django.test import SimpleTestCase
from portal.engine.schema import ScenarioInput, Vessel, default_fuels
from portal.engine.calculator import profile, simulate, compare, options, optimize, fuel_intensity, emissions_factor
from portal.engine.rules import LNG_CONSUMERS, rfnbo_reward, target


def reviewed_case(code="LNG", **kwargs):
    vessel = Vessel(name="Transition vessel", sea_t=1000, berth_t=0, intra_share=1, extra_share=0,
                    alternative=code, max_blend=1, compatible=True, alternative_consumer="diesel_slow",
                    fuel_systems_confirmed=True, technical_reference="TEST ONLY: reviewed system and cost basis")
    data = ScenarioInput(start_year=2026, end_year=2026, scope_confirmed=True, vessels=[vessel], **kwargs)
    for fuel in data.fuels:
        if fuel.code == code and fuel.renewable:
            fuel.eligible = True
            fuel.ets_eligible = True
            fuel.evidence = "TEST ONLY: certified production / carbon adjustment / engine factors"
            fuel.wtt = 10 - (fuel.co2 + (fuel.ch4 or 0) * 28 + (fuel.n2o or 0) * 265) * 1e6 / fuel.lcv
            if fuel.measured_factors_required:
                fuel.ch4 = 0
                fuel.n2o = .0001
                fuel.factors_confirmed = True
    return data


class LNGReferenceTests(SimpleTestCase):
    def test_default_catalogue_has_methane_and_distinct_rfnbo_pathways(self):
        fuels = {f.code: f for f in default_fuels()}
        self.assertTrue({"LNG", "LBM", "E_LNG", "E_METHANOL", "E_AMMONIA", "E_HYDROGEN", "E_HYDROGEN_ICE", "E_DIESEL"} <= set(fuels))
        self.assertFalse(fuels["LNG"].renewable)
        self.assertFalse(fuels["LBM"].rfnbo)
        self.assertTrue(fuels["E_LNG"].rfnbo)
        self.assertTrue(all(not f.eligible for f in fuels.values() if f.renewable))

    def test_all_four_lng_engine_defaults_against_hand_calculation(self):
        fuel = next(f for f in default_fuels() if f.code == "LNG")
        for consumer, slip in (("otto_medium", .031), ("otto_slow", .017), ("diesel_slow", .002), ("lbsi", .026)):
            with self.subTest(consumer=consumer):
                co2 = 2.75 * (1 - slip)
                non_co2 = 28 * slip + 265 * .00011 * (1 - slip)
                self.assertAlmostEqual(emissions_factor(fuel, 2025, consumer), co2)
                self.assertAlmostEqual(emissions_factor(fuel, 2026, consumer), co2 + non_co2)
                self.assertAlmostEqual(fuel_intensity(fuel, consumer), 18.5 + (co2 + non_co2) * 1e6 / 49100)

    def test_same_gas_different_consumers_have_different_results(self):
        data = reviewed_case()
        data.vessels[0].fuel = "LNG"
        data.vessels[0].fuel_consumer = "otto_medium"
        medium = profile(data.vessels[0], data, 2026)
        slow = profile(replace(data.vessels[0], fuel_consumer="diesel_slow"), data, 2026)
        self.assertGreater(medium["attained_g"], slow["attained_g"])
        self.assertGreater(medium["ets_t"], slow["ets_t"])
        self.assertEqual(medium["fuel_cost"], slow["fuel_cost"])
        self.assertEqual(medium["scoped_ch4_t"], 31)
        self.assertEqual(slow["scoped_ch4_t"], 2)

    def test_fossil_lng_can_be_selected_as_alternative_without_renewable_credit(self):
        data = reviewed_case()
        data.validate()
        self.assertIn((1, False, (("VLSFO", 1.0),)), options(data.vessels[0], data))
        row = profile(data.vessels[0], data, 2026, 1)
        self.assertGreater(row["ets_t"], 0)
        self.assertEqual(row["rfnbo_energy_mj"], 0)
        self.assertAlmostEqual(row["alternative_t"], 1000 * 40500 / 49100)

    def test_lng_and_pilot_extra_eu_scope_halves_emissions_not_costs(self):
        data = reviewed_case()
        data.vessels[0].alternative_pilot_share = .03
        full = profile(data.vessels[0], data, 2026, 1)
        half = profile(replace(data.vessels[0], intra_share=0, extra_share=1), data, 2026, 1)
        for field in ("energy_mj", "ets_t", "scoped_ch4_t"):
            self.assertAlmostEqual(half[field], full[field] / 2)
        # FuelEU fills the covered half with lower-WtW LNG, excluding MGO
        # pilot from attribution while retaining it in physical/ETS consumption.
        lng = next(f for f in data.fuels if f.code == "LNG")
        expected = fuel_intensity(lng, "diesel_slow")
        self.assertAlmostEqual(half["attained_g"], expected)
        self.assertAlmostEqual(half["balance_t"], (target(2026)-expected)*half["energy_mj"]/1e6)
        self.assertEqual(full["fuel_cost"], half["fuel_cost"])

    def test_bio_lng_and_e_lng_zero_only_eligible_co2_not_slip(self):
        for code in ("LBM", "E_LNG"):
            data = reviewed_case(code)
            fuel = next(f for f in data.fuels if f.code == code)
            self.assertEqual(emissions_factor(fuel, 2025, "diesel_slow"), 0)
            self.assertAlmostEqual(emissions_factor(fuel, 2026, "diesel_slow"), .002 * 28 + .00011 * .998 * 265)
            fuel.ets_eligible = False
            self.assertAlmostEqual(emissions_factor(fuel, 2025, "diesel_slow"), 2.75 * .998)

    def test_methane_requires_engine_and_technical_review(self):
        for changes in ({"alternative_consumer": ""}, {"fuel_systems_confirmed": False}, {"technical_reference": ""}):
            data = reviewed_case()
            data.vessels[0] = replace(data.vessels[0], **changes)
            self.assertRaises(ValueError, data.validate)


class RFNBOReferenceTests(SimpleTestCase):
    def test_multiplier_expiry_and_physical_balance_energy(self):
        data = reviewed_case("E_DIESEL")
        data.start_year, data.end_year = 2033, 2034
        for year, reward in ((2033, 2), (2034, 1)):
            row = profile(data.vessels[0], data, year, 1)
            self.assertEqual(rfnbo_reward(year), reward)
            self.assertAlmostEqual(row["attained_g"], 10 / reward)
            self.assertAlmostEqual(row["energy_mj"], 40500000)
            self.assertAlmostEqual(row["rewarded_energy_mj"], 40500000 * reward)
            self.assertAlmostEqual(row["balance_t"], (target(year) - 10 / reward) * 40.5)

    def test_partial_rfnbo_reward_includes_pilot_and_berth_without_rewarding_them(self):
        data = reviewed_case("E_DIESEL")
        v = data.vessels[0]
        v.berth_t, v.pilot_t, v.alternative_pilot_share = 30, 10, .02
        row = profile(v, data, 2026, .4)
        rfnbo_energy = (40500000 + 10 * 42700) * .4 * .98
        self.assertAlmostEqual(row["rfnbo_energy_mj"], rfnbo_energy)
        self.assertAlmostEqual(row["energy_mj"], 40500000 + 40 * 42700)
        self.assertAlmostEqual(row["rewarded_energy_mj"], row["energy_mj"] + rfnbo_energy)
        self.assertAlmostEqual(row["rfnbo_share"], rfnbo_energy / row["fuel_energy_mj"])

    def test_elective_reward_can_be_disabled_without_changing_physical_energy(self):
        data = reviewed_case("E_DIESEL")
        fuel = next(f for f in data.fuels if f.code == "E_DIESEL")
        enabled = profile(data.vessels[0], data, 2026, 1)
        fuel.reward_enabled = False
        disabled = profile(data.vessels[0], data, 2026, 1)
        self.assertAlmostEqual(disabled["attained_g"], 2 * enabled["attained_g"])
        self.assertEqual(disabled["rewarded_energy_mj"], disabled["energy_mj"])
        self.assertEqual(disabled["rfnbo_share"], enabled["rfnbo_share"])
        self.assertEqual(disabled["fuel_cost"], enabled["fuel_cost"])

    def test_rfnbo_can_be_current_fuel_and_ets_assertion_is_separate(self):
        data = reviewed_case("E_METHANOL")
        data.vessels[0].fuel = "E_METHANOL"
        data.validate()
        row = profile(data.vessels[0], data, 2026)
        self.assertEqual(row["rfnbo_share"], 1)
        fuel = next(f for f in data.fuels if f.code == "E_METHANOL")
        zero = row["ets_t"]
        fuel.ets_eligible = False
        self.assertAlmostEqual(profile(data.vessels[0], data, 2026)["ets_t"] - zero, 1000 * 1.375)
        self.assertEqual(profile(data.vessels[0], data, 2026)["attained_g"], row["attained_g"])

    def test_uncertified_alternative_is_excluded_and_uncertified_baseline_rejected(self):
        data = reviewed_case("E_DIESEL")
        fuel = next(f for f in data.fuels if f.code == "E_DIESEL")
        fuel.eligible = False
        self.assertEqual(options(data.vessels[0], data), [(0, False, (("VLSFO", 0.0),))])
        self.assertRaises(ValueError, profile, data.vessels[0], data, 2026, .1)
        data.vessels[0].fuel = "E_DIESEL"
        self.assertRaises(ValueError, data.validate)

    def test_unknown_tbm_factors_cannot_enable_fuel_or_default_to_zero(self):
        for code in ("E_METHANOL", "E_AMMONIA", "E_HYDROGEN_ICE"):
            data = reviewed_case(code)
            fuel = next(f for f in data.fuels if f.code == code)
            for changes in ({"n2o": None}, {"ch4": None}, {"factors_confirmed": False}, {"wtt": None}, {"evidence": ""}):
                with self.subTest(code=code, changes=changes):
                    bad = replace(fuel, **changes)
                    self.assertRaises(ValueError, bad.validate)

    def test_ammonia_n2o_changes_fueleu_and_ets_despite_zero_physical_co2(self):
        data = reviewed_case("E_AMMONIA")
        fuel = next(f for f in data.fuels if f.code == "E_AMMONIA")
        low = profile(data.vessels[0], data, 2026, 1)
        fuel.n2o += .001
        high = profile(data.vessels[0], data, 2026, 1)
        self.assertAlmostEqual(high["ets_t"] - low["ets_t"], low["alternative_t"] * .001 * 265)
        self.assertAlmostEqual(high["attained_g"] - low["attained_g"], .001 * 265 * 1e6 / 18600 / 2)

    def test_hydrogen_fuel_cell_and_combustion_are_distinct_pathways(self):
        data = reviewed_case("E_HYDROGEN")
        data.validate()
        row = profile(data.vessels[0], data, 2026, 1)
        self.assertEqual(row["ets_t"], 0)
        self.assertEqual(row["attained_g"], 5)
        combustion = reviewed_case("E_HYDROGEN_ICE")
        combustion.validate()
        self.assertGreater(profile(combustion.vessels[0], combustion, 2026, 1)["ets_t"], 0)


class TransitionCostTests(SimpleTestCase):
    def test_pilot_energy_and_relative_efficiency_preserve_service_not_mass(self):
        data = reviewed_case("E_HYDROGEN")
        v = data.vessels[0]
        v.pilot_t = 10
        v.alternative_pilot_share = .02
        v.alternative_energy_ratio = .8
        row = profile(v, data, 2026, .5)
        reference = 40500000 + 10 * 42700
        self.assertAlmostEqual(row["energy_mj"], reference * (.5 + .5 * .8))
        self.assertAlmostEqual(row["pilot_t"], 5 + reference * .5 * .8 * .02 / 42700)
        self.assertAlmostEqual(row["alternative_t"], reference * .5 * .8 * .98 / 120000)

    def test_conversion_fixed_cost_is_not_scaled_by_blend_and_is_only_once(self):
        data = reviewed_case()
        v = data.vessels[0]
        v.fuel_capex, v.fuel_annual = 1000000, 50000
        self.assertEqual(profile(v, data, 2026, .05)["implementation_cost"], 1050000)
        self.assertEqual(profile(v, data, 2027, .05)["implementation_cost"], 50000)
        self.assertEqual(profile(v, data, 2026, 0)["implementation_cost"], 0)

    def test_pilot_supply_cap_counts_baseline_and_alternative_pilot(self):
        data = reviewed_case()
        v = data.vessels[0]
        v.pilot_t, v.alternative_pilot_share = 5, .02
        mgo = next(f for f in data.fuels if f.code == "MGO")
        mgo.supply_t = 6
        self.assertIsNotNone(simulate(data, [(0, False)]))
        self.assertIsNone(simulate(data, [(1, False)]))

    def test_optimizer_can_choose_lng_and_conversion_cost_can_reverse_choice(self):
        data = reviewed_case()
        next(f for f in data.fuels if f.code == "LNG").price = 1
        self.assertEqual(optimize(data, False)["decisions"][0]["blend"], 1)
        data.vessels[0].fuel_capex = 100000000
        self.assertEqual(optimize(data, False)["decisions"][0]["blend"], 0)

    def test_search_improves_or_matches_exhaustive_single_vessel_for_each_new_fuel(self):
        for code in ("LNG", "LBM", "E_LNG", "E_METHANOL", "E_AMMONIA", "E_HYDROGEN", "E_HYDROGEN_ICE", "E_DIESEL"):
            with self.subTest(code=code):
                data = reviewed_case(code)
                data.end_year = 2028
                data.validate()
                exhaustive = min(simulate(data, [option])["npv"] for option in options(data.vessels[0], data))
                result = optimize(data, False)
                self.assertLessEqual(result["npv"], exhaustive + 1e-7)
                for row in result["rows"]:
                    self.assertAlmostEqual(row["total_cost"], sum(row[k] for k in ("fuel_cost", "ets_cost", "penalty_cost", "pool_cost", "electricity_cost", "implementation_cost")))


class RFNBOSubtargetTests(SimpleTestCase):
    def test_future_default_is_unresolved_not_a_fabricated_tariff(self):
        data = reviewed_case("E_DIESEL")
        data.start_year, data.end_year = 2033, 2034
        result = compare(data)
        self.assertTrue(any("unpriced" in text for text in result["coverage_limits"]))
        rows = simulate(data, [(0, False)])["rows"]
        self.assertEqual(rows[0]["rfnbo_deficit_mj"], 0)
        self.assertEqual(rows[1]["rfnbo_deficit_mj"], .02 * 40500000)
        self.assertEqual(rows[1]["rfnbo_penalty_cost"], 0)

    def test_active_stress_test_requires_explicit_price_and_reference(self):
        data = reviewed_case()
        data.end_year = 2034
        data.rfnbo_subtarget = "assume_active"
        self.assertRaises(ValueError, data.validate)
        data.rfnbo_penalty_pd, data.rfnbo_reference = 1000, "TEST ONLY future assumption"
        data.validate()

    def test_separate_shortfall_cost_not_erased_by_ghg_bank_or_pool(self):
        data = reviewed_case("E_DIESEL", rfnbo_subtarget="assume_active", rfnbo_penalty_pd=1000, rfnbo_reference="TEST ONLY")
        data.start_year, data.end_year = 2034, 2035
        data.vessels[0].opening_bank = 100000
        rows = simulate(data, [(0, False)], True)["rows"]
        self.assertEqual(rows[0]["ghg_penalty_cost"], 0)
        self.assertAlmostEqual(rows[0]["rfnbo_penalty_cost"], .02 * 40500000 / 41000 * 1000)
        self.assertAlmostEqual(rows[1]["rfnbo_penalty_cost"], rows[0]["rfnbo_penalty_cost"] * 1.1)
        self.assertEqual(rows[0]["penalty_cost"], rows[0]["rfnbo_penalty_cost"])
        self.assertAlmostEqual(simulate(data, [(0, False)], score_only=True), simulate(data, [(0, False)])["npv"])

    def test_ops_is_excluded_and_rfnbo_is_not_double_counted_for_two_percent(self):
        data = reviewed_case("E_DIESEL")
        data.start_year, data.end_year = 2034, 2034
        v = data.vessels[0]
        v.berth_t, v.ops_ready = 100, True
        row = profile(v, data, 2034, .01, True)
        self.assertAlmostEqual(row["rfnbo_deficit_mj"], .01 * 40500000)
        self.assertGreater(row["energy_mj"], row["fuel_energy_mj"])
        self.assertEqual(profile(v, data, 2034, .02, True)["rfnbo_deficit_mj"], 0)

    def test_legacy_five_fuel_payload_still_round_trips_without_catalogue_rewrite(self):
        data = ScenarioInput(vessels=[Vessel()], scope_confirmed=True).to_dict()
        data["fuels"] = data["fuels"][:5]
        for fuel in data["fuels"]:
            for key in ("pathway", "rfnbo", "wtt", "ets_eligible", "factors_confirmed"):
                fuel.pop(key)
        old = deepcopy(data)
        loaded = ScenarioInput.from_dict(data)
        loaded.validate()
        self.assertEqual(len(loaded.fuels), 5)
        self.assertEqual(data, old)
