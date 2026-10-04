"""Independent energy ledgers and optimizer checks for annual FuelEU attribution."""
from copy import deepcopy
from dataclasses import replace

from django.test import SimpleTestCase

from portal.engine.calculator import profile, optimize, simulate, saved_decision, leg_demands
from portal.engine.leg_optimizer import leg_decision
from portal.engine.rules import target
from portal.engine.schema import ScenarioInput, Vessel


def allocation_case():
    data = ScenarioInput(start_year=2026, end_year=2026, scope_confirmed=True,
                         vessels=[Vessel(name="Allocation", compatible=True, max_blend=1,
                             consumption=[{"fuel": "HVO", "extra_t": 20},
                                          {"fuel": "TEST_MGO", "extra_t": 15},
                                          {"fuel": "TEST_VLSFO", "extra_t": 25},
                                          {"fuel": "TEST_HSFO", "extra_t": 40}])])
    # Synthetic equal-LCV fuels keep this independent 100-unit ledger transparent.
    # Known regulatory oil codes, including the MGO pilot, stay canonical.
    originals = {fuel.code: fuel for fuel in data.fuels}
    for code, intensity in (("MGO", 85), ("VLSFO", 90), ("HSFO", 95)):
        data.fuels.append(replace(originals[code], code="TEST_" + code,
                                  lcv=40000, wtw=intensity, wtt=None))
    hvo = originals["HVO"]
    hvo.lcv, hvo.wtw = 40000, 20
    hvo.eligible, hvo.evidence = True, "TEST certified fuel"
    data.validate()
    return data


def allocated(row):
    return {s["fuel"]: s["allocated_energy_mj"] for s in row["fueleu_allocation"]}


class PrioritizedAllocationTests(SimpleTestCase):
    def test_alternative_and_conventional_fuels_fill_exact_covered_energy(self):
        data = allocation_case()
        row = profile(data.vessels[0], data, 2026)
        energies = allocated(row)
        self.assertEqual(energies, {"OPS": 0, "HVO": 800000, "TEST_MGO": 600000,
                                    "TEST_VLSFO": 600000, "TEST_HSFO": 0, "MGO": 0})
        self.assertEqual(row["energy_mj"], 2000000)
        self.assertEqual(row["attained_g"], (20*20+15*85+15*90)/50)
        # ETS and purchase costs still use the actual mix and proportional scope.
        expected_ets = .5*(20*(.00005*28+.00018*265)
                          +15*(3.206+.00005*28+.00018*265)
                          +65*(3.114+.00005*28+.00018*265))
        self.assertAlmostEqual(row["ets_t"], expected_ets)
        prices = {f.code: f.price for f in data.fuels}
        self.assertEqual(row["fuel_cost"], sum(t*prices[f] for f,t in
                          (("HVO",20),("TEST_MGO",15),("TEST_VLSFO",25),("TEST_HSFO",40))))

    def test_annual_allocation_crosses_voyages_and_does_not_depend_on_row_order(self):
        data = allocation_case()
        v = data.vessels[0]
        v.consumption = [{"voyage": 1, "fuel": "HVO", "extra_t": 20},
                         {"voyage": 2, "fuel": "TEST_HSFO", "intra_t": 30, "extra_t": 50}]
        row = profile(v, data, 2026)
        self.assertEqual(allocated(row)["HVO"], 20*40000)
        self.assertEqual(allocated(row)["TEST_HSFO"], 45*40000)
        v.consumption.reverse()
        other = profile(v, data, 2026)
        self.assertEqual(other["fueleu_allocation"], row["fueleu_allocation"])

    def test_outside_sea_and_non_eu_berth_cannot_supply_allocation(self):
        data = allocation_case()
        v = data.vessels[0]
        v.consumption = [{"fuel": "HVO", "outside_t": 100, "non_eu_berth_t": 100},
                         {"fuel": "TEST_HSFO", "extra_t": 100}]
        row = profile(v, data, 2026)
        self.assertEqual(allocated(row)["HVO"], 0)
        self.assertEqual(row["attained_g"], 95)
        self.assertEqual(row["fuel_tonnes"]["HVO"], 200)
        # No inventory or intensity can leak from another ship.
        data.vessels.append(replace(v, name="Other", consumption=[{"fuel":"HVO", "intra_t":100}]))
        result = simulate(data, [(0, False), (0, False)])
        self.assertEqual(result["rows"][0]["attained_g"], 95)

    def test_conventional_only_mix_is_prioritized_and_all_in_scope_is_unchanged(self):
        data = allocation_case()
        v = data.vessels[0]
        v.consumption = [{"fuel":"TEST_MGO", "extra_t":30}, {"fuel":"TEST_HSFO", "extra_t":70}]
        row = profile(v, data, 2026)
        self.assertEqual(row["attained_g"], (30*85+20*95)/50)
        v.consumption = [{"fuel":"TEST_MGO", "intra_t":30}, {"fuel":"TEST_HSFO", "intra_t":70}]
        self.assertEqual(profile(v, data, 2026)["attained_g"], (30*85+70*95)/100)

    def test_mixed_leg_replacement_does_not_make_outside_energy_eligible(self):
        data = allocation_case()
        v = data.vessels[0]
        v.consumption = [{"fuel":"TEST_HSFO", "extra_t":100, "outside_t":100}]
        row = profile(v, data, 2026, .2)
        self.assertEqual(row["alternative_t"], 40)
        self.assertEqual(allocated(row)["HVO"], 20*40000)
        self.assertEqual(row["attained_g"], (20*20+30*95)/50)

    def test_allocation_caps_surplus_renewable_and_applies_reward_afterwards(self):
        data = allocation_case()
        f = next(f for f in data.fuels if f.code == "E_DIESEL")
        f.eligible, f.evidence, f.wtt = True, "TEST RFNBO", -50
        v = data.vessels[0]
        v.consumption = [{"fuel":"E_DIESEL", "extra_t":100}]
        for year, reward in ((2033, 2), (2034, 1)):
            row = profile(v, data, year)
            self.assertEqual(row["rfnbo_energy_mj"], 50*42700)
            self.assertEqual(row["allocated_rfnbo_energy_mj"], 50*42700)
            self.assertEqual(row["rewarded_energy_mj"], 50*42700*reward)
            self.assertEqual(row["rfnbo_share"], 1)
            self.assertEqual(sum(allocated(row).values()), row["energy_mj"])

    def test_ops_and_pilot_keep_physical_energy_separate_from_attribution(self):
        data = allocation_case()
        v = data.vessels[0]
        v.ops_ready = True
        v.alternative_energy_ratio, v.alternative_pilot_share = .8, .1
        v.consumption = [{"fuel":"TEST_HSFO", "extra_t":100}, {"fuel":"TEST_MGO", "eu_berth_t":10}]
        row = profile(v, data, 2026, .2, True)
        electricity = 10*40000*.4/.95
        self.assertAlmostEqual(row["energy_mj"], 80*40000*.5+20*40000*.8*.5+electricity)
        self.assertAlmostEqual(allocated(row)["HVO"], 20*40000*.8*.9)
        self.assertAlmostEqual(allocated(row)["MGO"], 20*40000*.8*.1)
        self.assertAlmostEqual(allocated(row)["OPS"], electricity)
        self.assertAlmostEqual(row["fuel_energy_mj"], row["energy_mj"]-electricity)
        self.assertEqual(row["fuel_tonnes"]["MGO"], 20*40000*.8*.1/42700)

    def test_optimizer_closes_extra_eu_deficit_with_full_alternative_attribution(self):
        data = allocation_case()
        v = data.vessels[0]
        v.consumption = [{"fuel":"TEST_HSFO", "extra_t":100}]
        result = optimize(data, False)
        # Solve 20*x + 95*(50-x) = target*50, using full HVO energy.
        expected = (95-target(2026))*50/(95-20)
        self.assertAlmostEqual(result["decisions"][0]["alternative_t"], expected, places=6)
        self.assertAlmostEqual(result["rows"][0]["balance_t"], 0, places=7)
        # Reconstruct the physical final inventory independently of replacements.
        final = deepcopy(data)
        final.vessels[0].consumption = [{"fuel":"TEST_HSFO", "extra_t":100-expected},
                                       {"fuel":"HVO", "extra_t":expected}]
        self.assertAlmostEqual(result["npv"], simulate(final, [(0,False)])["npv"], places=5)

    def test_optimizer_checks_source_exhaustion_and_fractional_supply_boundary(self):
        data = allocation_case()
        v = data.vessels[0]
        v.consumption = [{"fuel":"TEST_HSFO", "extra_t":100}]
        data.start_year = data.end_year = 2050
        next(f for f in data.fuels if f.code == "HVO").price = 800
        # Target below HVO intensity: reduction pays until exactly 50% energy
        # is replaced, then only fuel/ETS costs change. The kink is the optimum.
        result = optimize(data, False)
        self.assertAlmostEqual(result["decisions"][0]["blend"], .5, places=6)
        next(f for f in data.fuels if f.code == "HVO").supply_t = 7.123456
        result = optimize(data, False)
        self.assertAlmostEqual(result["decisions"][0]["alternative_t"], 7.123456, places=6)

    def test_optimizer_is_no_worse_than_independent_two_leg_grid(self):
        data = allocation_case()
        v = data.vessels[0]
        v.consumption = [{"fuel":"TEST_HSFO", "extra_t":100}, {"fuel":"TEST_MGO", "intra_t":20}]
        v.max_blend = .1
        result = optimize(data, False)
        demands = leg_demands(v, data)
        for a in range(11):
            for b in range(11):
                decision = leg_decision(demands, {"1:TEST_HSFO:extra_t":a/100, "1:TEST_MGO:intra_t":b/100}, False)
                if decision[0] <= v.max_blend:
                    self.assertLessEqual(result["npv"], simulate(data, [decision])["npv"]+1e-5)
        replay = simulate(data, [saved_decision(d) for d in result["decisions"]])
        self.assertEqual(result["npv"], replay["npv"])

    def test_multiyear_reward_expiry_bank_and_supply_are_evaluated_together(self):
        data = allocation_case()
        data.start_year, data.end_year = 2033, 2034
        v = data.vessels[0]
        v.alternative = "E_DIESEL"
        v.opening_bank = 1
        v.consumption = [{"fuel":"TEST_HSFO", "extra_t":100}]
        fuel = next(f for f in data.fuels if f.code == "E_DIESEL")
        fuel.eligible, fuel.ets_eligible, fuel.evidence = True, True, "TEST RFNBO"
        fuel.wtt, fuel.price, fuel.supply_t = -50, 1000, 30
        data.rfnbo_subtarget, data.rfnbo_penalty_pd = "assume_active", 1000
        data.rfnbo_reference = "TEST conditional rule"
        data.validate()
        best = optimize(data, False)
        for step in range(301):
            fraction = step/1000
            trial = simulate(data, [(fraction,False)])
            if trial is not None:
                self.assertLessEqual(best["npv"], trial["npv"]+1e-5)
        self.assertTrue(all(row["alternative_t"] <= 30+1e-7 for row in best["rows"]))
        self.assertEqual(best["rows"][0]["rfnbo_reward"], 2)
        self.assertEqual(best["rows"][1]["rfnbo_reward"], 1)

    def test_same_fuel_with_different_consumers_is_ranked_by_actual_wtw(self):
        data = allocation_case()
        v = data.vessels[0]
        v.fuel_consumer, v.berth_consumer = "diesel_slow", "otto_medium"
        v.consumption = [{"fuel":"LNG", "extra_t":100, "eu_berth_t":20}]
        row = profile(v, data, 2026)
        gas = [s for s in row["fueleu_allocation"] if s["fuel"] == "LNG"]
        self.assertEqual([s["consumer"] for s in gas], ["diesel_slow", "otto_medium"])
        self.assertAlmostEqual(gas[0]["allocated_energy_mj"], 70*49100)
        self.assertEqual(gas[1]["allocated_energy_mj"], 0)
