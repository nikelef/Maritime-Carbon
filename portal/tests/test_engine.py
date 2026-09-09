from copy import deepcopy
from dataclasses import replace
from itertools import product
from math import isfinite
from django.test import SimpleTestCase
from portal.engine.schema import ScenarioInput, Vessel, Fuel, default_fuels
from portal.engine.calculator import profile, simulate, compare, emissions_factor, optimize, options
from portal.engine.rules import target, penalty, borrowing_limit


def case(**kwargs):
    defaults = {"start_year": 2026, "end_year": 2026, "vessels": [Vessel(name="Test vessel", sea_t=1000, berth_t=0, intra_share=1, extra_share=0)], "scope_confirmed": True}
    defaults.update(kwargs)
    return ScenarioInput(**defaults)


class RegulatoryReferenceTests(SimpleTestCase):
    def test_exact_target_boundaries(self):
        expected = {2025: 89.3368, 2029: 89.3368, 2030: 85.6904, 2034: 85.6904, 2035: 77.9418, 2040: 62.9004, 2045: 34.6408, 2050: 18.232}
        for year, value in expected.items():
            with self.subTest(year=year):
                self.assertAlmostEqual(target(year), value, places=8)

    def test_annex_iv_penalty_hand_calculation(self):
        # 1,000 t fuel, 41,000 MJ/t, 100 g/MJ attained, 89.3368 target:
        # (100 - 89.3368) * 41,000,000 g = 437.1912 t deficit.
        self.assertAlmostEqual(penalty(437.1912, 100), 255916.8)
        self.assertAlmostEqual(penalty(437.1912, 100, 3), 307100.16)
        self.assertEqual(penalty(-10, 50), 0)

    def test_ets_zero_rating_retains_ch4_and_n2o(self):
        fuel = Fuel("BIO", "Test", 40000, 20, 3, .001, .002, 1000, True, True, "Reviewed pathway")
        self.assertEqual(emissions_factor(fuel, 2025), 0)
        self.assertAlmostEqual(emissions_factor(fuel, 2026), .558)
        self.assertAlmostEqual(emissions_factor(replace(fuel, eligible=False), 2026), 3.558)

    def test_phase_in_is_by_reporting_not_surrender_year(self):
        data = case(start_year=2025, end_year=2026)
        v = data.vessels[0]
        self.assertAlmostEqual(profile(v, data, 2025)["ets_t"], 1000 * 3.114 * .7)
        self.assertAlmostEqual(profile(v, data, 2026)["ets_t"], 1000 * (3.114 + .00005 * 28 + .00018 * 265))

    def test_proportional_extra_eu_scope_preserves_entire_fuel_cost(self):
        data = case()
        full = profile(data.vessels[0], data, 2026)
        half = profile(replace(data.vessels[0], intra_share=0, extra_share=1), data, 2026)
        outside = profile(replace(data.vessels[0], intra_share=0, extra_share=0), data, 2026)
        for key in ("ets_t", "balance_t", "energy_mj"):
            self.assertAlmostEqual(half[key], full[key] / 2)
            self.assertEqual(outside[key], 0)
        self.assertEqual(full["fuel_cost"], half["fuel_cost"])
        self.assertEqual(full["fuel_cost"], outside["fuel_cost"])

    def test_5000_gt_boundary_differs_between_regimes(self):
        data = case()
        row = profile(replace(data.vessels[0], gt=5000), data, 2026)
        self.assertEqual(row["energy_mj"], 0)
        self.assertGreater(row["ets_t"], 0)
        self.assertEqual(profile(replace(data.vessels[0], gt=4999), data, 2026)["ets_t"], 0)

    def test_borrowing_limit_units(self):
        self.assertAlmostEqual(borrowing_limit(41_000_000, 2025), 73.256176)

    def test_repeated_deficit_penalties_and_history(self):
        data = case(end_year=2028)
        rows = simulate(data, [(0, False)])["rows"]
        p = rows[0]["penalty_cost"]
        self.assertAlmostEqual(rows[1]["penalty_cost"], p * 1.1)
        self.assertAlmostEqual(rows[2]["penalty_cost"], p * 1.2)
        data.vessels[0].prior_penalties = 1
        self.assertAlmostEqual(simulate(data, [(0, False)])["rows"][0]["penalty_cost"], p * 1.1)


class PhysicalAndFinancialTests(SimpleTestCase):
    def setUp(self):
        self.data = case()
        for fuel in self.data.fuels:
            if fuel.code in ("HVO", "FAME"):
                fuel.eligible = True
                fuel.evidence = "test fixture: approved pathway"
        self.data.vessels[0].compatible = True

    def test_fuel_switch_conserves_energy_not_mass(self):
        row = profile(self.data.vessels[0], self.data, 2026, .3)
        self.assertAlmostEqual(row["fossil_t"], 700)
        self.assertAlmostEqual(row["alternative_t"], 1000 * 40500 * .3 / 44000)
        self.assertAlmostEqual(row["energy_mj"], 1000 * 40500)

    def test_shore_power_uses_generator_output_and_costs_money(self):
        v = replace(self.data.vessels[0], sea_t=0, berth_t=100, ops_ready=True, ops_efficiency=.95, generator_efficiency=.4, ops_capex=10000, ops_annual=1000)
        row = profile(v, self.data, 2026, ops=True)
        expected_mwh = 100 * 42700 * .4 / .95 / 3600
        self.assertAlmostEqual(row["electricity_mwh"], expected_mwh)
        self.assertAlmostEqual(row["electricity_cost"], expected_mwh * 160)
        self.assertEqual(row["attained_g"], 0)
        self.assertEqual(row["fuel_cost"], 0)
        self.assertEqual(row["ets_cost"], 0)
        self.assertEqual(row["implementation_cost"], 11000)
        self.assertEqual(profile(v, self.data, 2027, ops=True)["implementation_cost"], 1000)

    def test_no_automatic_surplus_revenue(self):
        row = simulate(self.data, [(.3, False)])["rows"][0]
        self.assertGreater(row["balance_t"], 0)
        self.assertEqual(row["penalty_cost"], 0)
        self.assertEqual(row["pool_cost"], 0)
        self.assertEqual(row["total_cost"], row["fuel_cost"] + row["ets_cost"])

    def test_bank_is_not_transferred_to_another_vessel(self):
        self.data.vessels.append(replace(self.data.vessels[0], name="Second", sea_t=2000))
        self.data.vessels[0].opening_bank = 10000
        result = simulate(self.data, [(0, False), (0, False)], True)
        self.assertGreater(result["rows"][1]["penalty_cost"], 0)
        self.assertEqual(result["rows"][1]["bank_used_t"], 0)
        self.assertEqual(result["rows"][0]["pool_transfer_t"], 0)

    def test_valid_internal_pool_conserves_balances(self):
        self.data.vessels.append(replace(self.data.vessels[0], name="Second"))
        result = simulate(self.data, [(.3, False), (0, False)], True)
        self.assertAlmostEqual(sum(r["pool_transfer_t"] for r in result["rows"]), 0)
        self.assertEqual(result["penalty_cost"], 0)
        self.assertEqual(result["pool_cost"], 0)
        self.assertTrue(all(r["bank_close_t"] >= 0 for r in result["rows"]))

    def test_insufficient_external_capacity_does_not_create_an_invalid_pool(self):
        self.data.pool_enabled = True
        self.data.pool_reference = "Test quote"
        self.data.pool_cap = 1
        result = simulate(self.data, [(0, False)], True)
        self.assertGreater(result["penalty_cost"], 0)
        self.assertFalse(result["annual"][0]["pool_used"])
        self.assertEqual(result["pool_cost"], 0)

    def test_external_pool_is_a_cash_purchase(self):
        self.data.pool_enabled = True
        self.data.pool_reference = "Test quote"
        result = simulate(self.data, [(0, False)], True)
        row = result["rows"][0]
        self.assertAlmostEqual(row["pool_cost"], -row["balance_t"] * self.data.pool_price)
        self.assertEqual(row["penalty_cost"], 0)

    def test_out_of_scope_ship_is_not_recorded_as_pool_participant(self):
        self.data.pool_enabled = True
        self.data.pool_reference = "Test quote"
        self.data.vessels.append(replace(self.data.vessels[0], name="Small ship", gt=4999))
        result = simulate(self.data, [(0, False), (0, False)], True)
        self.assertTrue(result["rows"][0]["pooled"])
        self.assertFalse(result["rows"][1]["pooled"])

    def test_fast_score_matches_full_ledger_with_banking_and_pooling(self):
        self.data.pool_enabled = True
        self.data.pool_reference = "Test quote"
        self.data.end_year = 2035
        self.data.other_annual_cost = 1234.56
        self.data.vessels.append(replace(self.data.vessels[0], name="Second"))
        decisions = [(.3, False), (.05, False)]
        self.assertAlmostEqual(simulate(self.data, decisions, True, profile_cache={}, score_only=True), simulate(self.data, decisions, True)["npv"])

    def test_supply_cap_is_shared_across_fleet_and_zero_is_unavailable(self):
        self.data.vessels.append(replace(self.data.vessels[0], name="Second"))
        bio = next(f for f in self.data.fuels if f.code == "HVO")
        bio.supply_t = 300
        self.assertIsNone(simulate(self.data, [(.3, False), (.3, False)]))
        self.assertIsNotNone(simulate(self.data, [(.3, False), (0, False)]))
        bio.supply_t = 0
        self.assertIsNone(simulate(self.data, [(.05, False), (0, False)]))

    def test_yearly_totals_npv_and_ledger_reconcile(self):
        self.data.end_year = 2030
        self.data.other_annual_cost = 1234.56
        result = simulate(self.data, [(.1, False)])
        expected = 0
        for row in result["annual"]:
            costs = sum(row[k] for k in ("fuel_cost", "ets_cost", "penalty_cost", "pool_cost", "electricity_cost", "implementation_cost", "other_cost"))
            self.assertAlmostEqual(row["total_cost"], costs)
            expected += costs / 1.07 ** (row["year"] - 2026)
        self.assertAlmostEqual(result["npv"], expected)
        for row in result["rows"]:
            self.assertAlmostEqual(row["bank_close_t"] - row["bank_open_t"], row["balance_t"] + row["residual_deficit_t"] + row["pool_transfer_t"] + row["pool_buy_t"])

    def test_one_ship_search_improves_or_matches_exhaustive_grid_and_is_repeatable(self):
        self.data.end_year = 2030
        best = optimize(self.data, False)
        exhaustive = min(simulate(self.data, [option])["npv"] for option in options(self.data.vessels[0], self.data))
        self.assertLessEqual(best["npv"], exhaustive + 1e-7)
        self.assertEqual(compare(self.data), compare(self.data))

    def test_compatibility_and_evidence_are_both_required(self):
        self.data.vessels[0].compatible = False
        self.assertEqual(options(self.data.vessels[0], self.data), [(0.0, False, (("VLSFO", 0.0),))])
        with self.assertRaises(ValueError):
            profile(self.data.vessels[0], self.data, 2026, .1)
        self.data.vessels[0].compatible = True
        next(f for f in self.data.fuels if f.code == "HVO").eligible = False
        with self.assertRaises(ValueError):
            profile(self.data.vessels[0], self.data, 2026, .1)


class InputValidationTests(SimpleTestCase):
    def test_nan_inf_negative_and_boolean_prices_rejected(self):
        for value in (float("nan"), float("inf"), -1, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                case(eua_price=value).validate()

    def test_year_order_scope_and_empty_fleet(self):
        for value in (case(start_year=2030, end_year=2026), case(vessels=[]), case(scope_confirmed=False), case(start_year=2024)):
            with self.assertRaises(ValueError):
                value.validate()

    def test_unknown_fields_wrong_types_and_duplicate_ships(self):
        data = case().to_dict()
        for payload in ({"company_id": 1}, {"vessels": "bad"}, {"fuels": [{}]}):
            with self.assertRaises(ValueError):
                ScenarioInput.from_dict(payload)
        data["vessels"] *= 2
        with self.assertRaises(ValueError):
            ScenarioInput.from_dict(data).validate()

    def test_scope_shares_and_imo_check_digit(self):
        data = case()
        data.vessels[0].extra_share = .1
        with self.assertRaises(ValueError):
            data.validate()
        data.vessels[0].extra_share = 0
        data.vessels[0].imo = "1234568"
        self.assertRaises(ValueError, data.validate)
        data.vessels[0].imo = "9074729"
        data.validate()

    def test_evidence_cannot_zero_rate_fossil_fuel(self):
        data = case()
        data.fuels[0].eligible = True
        data.fuels[0].evidence = "not a renewable pathway"
        self.assertRaises(ValueError, data.validate)

    def test_inconsistent_fossil_wtw_cannot_hide_combustion_emissions(self):
        data = case()
        data.fuels[0].wtw = 1
        self.assertRaises(ValueError, data.validate)

    def test_history_cannot_predate_regulation(self):
        data = case(start_year=2025, end_year=2025)
        data.vessels[0].opening_bank = 1
        self.assertRaises(ValueError, data.validate)
        data.vessels[0].opening_bank = 0
        data.vessels[0].prior_penalties = 1
        self.assertRaises(ValueError, data.validate)
