"""Independent regulatory examples and bounded-polytope allocation oracles."""
from itertools import product
from math import fsum
from random import Random

from django.test import SimpleTestCase

from portal.engine.allocation import prioritize_energy, allocation_breakpoints
from portal.engine.calculator import profile, fuel_intensity, emissions_factor, optimize, simulate
from portal.engine.schema import default_fuels
from portal.tests.test_alternative_fuels import reviewed_case


def source(code, energy, intensity, rewarded=False):
    return dict(fuel=code, consumer="", source_type="electricity" if code == "OPS" else "fuel",
                available_energy_mj=energy, wtw_g=intensity, reward_enabled=rewarded)


def ratio(allocation):
    denominator = fsum(s["allocated_energy_mj"]*s["reward_multiplier"] for s in allocation)
    return fsum(s["allocated_energy_mj"]*s["wtw_g"] for s in allocation)/denominator if denominator else 0


def vertex_minimum(sources, energy, reward):
    # Every vertex of box bounds intersected with sum(x)=E has at most one
    # non-bound variable. Enumerate independently of the production algorithm.
    values = []
    for free in range(len(sources)):
        fixed = [i for i in range(len(sources)) if i != free]
        for bits in product((0, 1), repeat=len(fixed)):
            amounts = {i: bit*sources[i]["available_energy_mj"] for i,bit in zip(fixed,bits)}
            amounts[free] = energy-fsum(amounts.values())
            if -1e-10 <= amounts[free] <= sources[free]["available_energy_mj"]+1e-10:
                n = fsum(amounts[i]*s["wtw_g"] for i,s in enumerate(sources))
                d = fsum(amounts[i]*(reward if s["reward_enabled"] else 1) for i,s in enumerate(sources))
                values.append(n/d)
    return min(values)


class RFNBOAllocationTests(SimpleTestCase):
    def test_reported_counterexample_and_reward_expiry(self):
        sources = [source("BIO",40,20), source("RFNBO",20,25,True), source("FOSSIL",40,90)]
        allocation = prioritize_energy(sources,50,2)
        self.assertEqual({s["fuel"]:s["allocated_energy_mj"] for s in allocation},
                         {"BIO":30,"RFNBO":20,"FOSSIL":0})
        self.assertAlmostEqual(ratio(allocation),1100/70)
        self.assertAlmostEqual(ratio(prioritize_energy(sources,50,1)),1050/50)
        self.assertEqual(sources[1]["available_energy_mj"],20)

    def test_sorting_by_standalone_rewarded_intensity_is_not_sufficient(self):
        # RFNBO has g/r=15 < bio 20, but at the final fleet mix the marginal
        # denominator benefit cannot justify displacing bio with RFNBO g=30.
        sources = [source("OPS",40,0),source("BIO",10,20),source("RFNBO",50,30,True)]
        allocation = prioritize_energy(sources,50,2)
        self.assertEqual(next(s["allocated_energy_mj"] for s in allocation if s["fuel"]=="RFNBO"),0)
        self.assertEqual(ratio(allocation),4)

    def test_randomized_allocations_match_exhaustive_vertices(self):
        rng = Random(670)
        for trial in range(100):
            sources = [source(str(i),rng.uniform(.1,50),rng.uniform(-30,100),i%2==0) for i in range(5)]
            sources.append(source("OPS",rng.uniform(0,30),0))
            energy = sum(s["available_energy_mj"] for s in sources)*rng.uniform(.05,1)
            for reward in (1,2):
                result = prioritize_energy(sources,energy,reward)
                self.assertAlmostEqual(ratio(result),vertex_minimum(sources,energy,reward),places=9)
                self.assertAlmostEqual(sum(s["allocated_energy_mj"] for s in result),energy)
                self.assertTrue(all(0<=s["allocated_energy_mj"]<=s["available_energy_mj"] for s in result))
                self.assertEqual(result,prioritize_energy(list(reversed(sources)),energy,reward))

    def test_zero_scope_full_scope_disabled_reward_and_insufficient_energy(self):
        sources=[source("NEG",10,-20),source("RFNBO",10,-10,True),source("OPS",5,0)]
        self.assertEqual(ratio(prioritize_energy(sources,0,2)),0)
        self.assertEqual(ratio(prioritize_energy(sources,10,2)),-20)
        self.assertAlmostEqual(ratio(prioritize_energy(sources,25,2)),-300/35)
        sources[1]["reward_enabled"]=False
        self.assertAlmostEqual(ratio(prioritize_energy(sources,25,2)),-300/25)
        self.assertRaises(ValueError,prioritize_energy,sources,26,2)

    def test_parametric_boundaries_include_reward_order_changes(self):
        def at(t):
            sources=[source("BIO",10,20),source("RFNBO",20,40,True),
                     source("FOSSIL",100*(1-t),90),source("OPS",40*t,0)]
            return {"energy_mj":50,"fueleu_allocation":prioritize_energy(sources,50,2)}
        points=allocation_breakpoints(at(0),at(1))
        # At t=.5: OPS=20, bio=10, RFNBO=20, I=20. The preferred
        # order of bio and RFNBO reverses here; endpoint orders are different.
        self.assertTrue(any(abs(t-.5)<1e-10 for t in points))
        boundaries=sorted({0,1}|points)
        for start,end in zip(boundaries,boundaries[1:]):
            values=[]
            for part in (.25,.5,.75):
                allocation=at(start+(end-start)*part)["fueleu_allocation"]
                values.append({s["fuel"]:s["allocated_energy_mj"] for s in allocation})
            for key in values[0]:
                self.assertAlmostEqual(values[1][key],(values[0][key]+values[2][key])/2,places=8)
        clipped=allocation_breakpoints(at(0),at(1),.2,.7)
        self.assertTrue(all(.2<t<.7 for t in clipped))

    def test_commission_e_diesel_example_and_distinct_ets_gwp(self):
        fuel=next(f for f in default_fuels() if f.code=="E_DIESEL")
        fuel.eligible, fuel.evidence, fuel.wtt=True,"TEST PoS E=10, eu=73.2",-63.2
        expected=-63.2+(3.206+.00005*25+.00018*298)*1e6/42700
        self.assertAlmostEqual(expected,13.16744730679157)
        self.assertAlmostEqual(fuel_intensity(fuel),expected)
        self.assertAlmostEqual(emissions_factor(fuel,2026),3.206+.00005*28+.00018*265)
        fuel.ets_eligible=True
        self.assertAlmostEqual(emissions_factor(fuel,2026),.00005*28+.00018*265)
        self.assertAlmostEqual(fuel_intensity(fuel),expected)

    def test_randomized_parametric_boundaries_partition_each_reward_regime(self):
        rng=Random(671)
        for trial in range(30):
            start=[source(str(i),rng.uniform(5,40),rng.uniform(-10,100),i%2==0) for i in range(5)]
            end=[s | {"available_energy_mj":rng.uniform(5,40)} for s in start]
            ea,eb=[.6*sum(s["available_energy_mj"] for s in ss) for ss in (start,end)]
            for reward in (1,2):
                def at(t):
                    sources=[s | {"available_energy_mj":s["available_energy_mj"]+
                             t*(e["available_energy_mj"]-s["available_energy_mj"])} for s,e in zip(start,end)]
                    energy=ea+t*(eb-ea)
                    return {"energy_mj":energy,"fueleu_allocation":prioritize_energy(sources,energy,reward)}
                boundaries=sorted({0,1}|allocation_breakpoints(at(0),at(1)))
                for low,high in zip(boundaries,boundaries[1:]):
                    inventories=[]
                    for part in (.2,.5,.8):
                        row=at(low+part*(high-low))
                        inventories.append({s["fuel"]:s["allocated_energy_mj"] for s in row["fueleu_allocation"]})
                    for key in inventories[0]:
                        self.assertAlmostEqual(inventories[1][key],(inventories[0][key]+inventories[2][key])/2,places=7)

    def test_default_oils_use_fueleu_factors(self):
        for code,co2,wtt,lcv in (("HSFO",3.114,13.5,40500),("VLSFO",3.114,13.5,40500),("MGO",3.206,14.4,42700)):
            fuel=next(f for f in default_fuels() if f.code==code)
            self.assertAlmostEqual(fuel_intensity(fuel),wtt+(co2+.00005*25+.00018*298)*1e6/lcv)
            self.assertAlmostEqual(emissions_factor(fuel,2026),co2+.00005*28+.00018*265)

    def test_full_profile_reward_aware_allocation_with_ops_and_pilot(self):
        data=reviewed_case("E_DIESEL")
        v=data.vessels[0]
        v.intra_share,v.extra_share=0,1
        v.berth_t,v.ops_ready,v.alternative_pilot_share=100,True,.03
        for year,reward in ((2033,2),(2034,1)):
            r=profile(v,data,year,.6,True)
            sources=r["fueleu_allocation"]
            self.assertAlmostEqual(r["attained_g"],vertex_minimum(sources,r["energy_mj"],reward),places=9)
            self.assertAlmostEqual(r["rewarded_energy_mj"],r["energy_mj"]+(reward-1)*r["allocated_rfnbo_energy_mj"])
            ops=next(s for s in sources if s["source_type"]=="electricity")
            self.assertEqual(ops["reward_multiplier"],1)
            self.assertAlmostEqual(r["allocated_fuel_energy_mj"],r["energy_mj"]-ops["allocated_energy_mj"])
            self.assertAlmostEqual(r["fuel_energy_mj"],r["energy_mj"]-r["electricity_mwh"]*3600)
            self.assertAlmostEqual(r["rfnbo_energy_mj"],r["alternative_t"]*42700*.5)

    def test_optimizer_multiyear_ops_and_reward_expiry_against_dense_grid(self):
        data=reviewed_case("E_DIESEL")
        data.start_year,data.end_year=2033,2034
        v=data.vessels[0]
        v.intra_share,v.extra_share=0,1
        v.berth_t,v.ops_ready,v.ops_capex=100,True,10000
        v.alternative_pilot_share=.02
        best=optimize(data,False)
        reference=min(simulate(data,[(i/200,ops)])["npv"] for i in range(201) for ops in (False,True))
        self.assertLessEqual(best["npv"],reference+1e-5)
