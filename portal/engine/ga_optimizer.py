"""Optional mixed-variable genetic search; all costs use the existing calculator.

Each individual is a complete fleet plan. Real-valued voyage-leg fractions and
binary OPS/retrofit choices evolve together. The original optimizer supplies an
incumbent, and its boundary-aware refinement polishes the best GA improvement.
No regulatory equations, settlement policies or result layouts are duplicated.
"""
from collections import OrderedDict
from dataclasses import dataclass
from math import fsum, isfinite
from random import Random
from time import monotonic

from .calculator import leg_demands, profile, saved_decision, simulate
from .leg_optimizer import leg_decision, optimize_legs
from .wind import wind_choices


@dataclass(frozen=True)
class GASettings:
    population_size: int = 32
    generations: int = 24
    seed: int = 1729
    # This bounds the evolutionary stage, not the original search/refinement.
    time_limit_s: float = 10.0


class _ProfileCache(OrderedDict):
    """Bound memory even for long horizons and large voyage tables."""
    def __init__(self, limit):
        super().__init__()
        self.limit = limit

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if len(self) > self.limit:
            self.popitem(last=False)


class _FleetSearch:
    def __init__(self, scenario, use_pool, settings):
        self.scenario, self.use_pool, self.settings = scenario, use_pool, settings
        self.random = Random(settings.seed)
        self.demands = [leg_demands(v, scenario) for v in scenario.vessels]
        fuels = {f.code: f for f in scenario.fuels}
        self.keys = [tuple(k for k, d in ds.items() if d["fuel"] != v.alternative)
                     if v.compatible and v.max_blend > 0 and fuels[v.alternative].available_for_use else ()
                     for v, ds in zip(scenario.vessels, self.demands)]
        self.caps = [f for f in scenario.fuels if f.supply_t is not None]
        largest = max((len(ds) for ds in self.demands), default=1)
        self.profiles = _ProfileCache(max(32, min(1024, 20000 // max(1, largest))))
        self.scores = {}
        self.evaluations = 0

    def choice(self, index, shares, ops=False, wind=False):
        """Repair vessel limits without changing the original energy weights."""
        v, ds = self.scenario.vessels[index], self.demands[index]
        shares = {key: min(1.0, max(0.0, shares.get(key, 0.0))) for key in self.keys[index]}
        blend = fsum(ds[key]["weight"] * x for key, x in shares.items())
        if blend > v.max_blend:
            shares = {key: x * v.max_blend / blend for key, x in shares.items()}
        return leg_decision(ds, shares, bool(ops and v.ops_ready),
                            bool(wind and v.wind_mode == "retrofit"))

    def physical(self, index, decision):
        year = self.scenario.start_year
        key = (index, year, *decision)
        if key not in self.profiles:
            self.profiles[key] = profile(self.scenario.vessels[index], self.scenario, year, *decision)
        return self.profiles[key]

    def repair_supply(self, plan):
        """Clip a joint fuel move at fleet supply boundaries, equipment fixed.

        Physical purchases are affine along this line, including energy ratios,
        pilot fuel, OPS and wind savings. Annual physical demand is fixed in the
        existing model. simulate() still validates every year independently.
        """
        if not self.caps:
            return plan
        zero = tuple(self.choice(i, {}, d[1], len(d) > 4 and d[4]) for i, d in enumerate(plan))
        start = [self.physical(i, d)["fuel_tonnes"] for i, d in enumerate(zero)]
        end = [self.physical(i, d)["fuel_tonnes"] for i, d in enumerate(plan)]
        low, high = 0.0, 1.0
        for fuel in self.caps:
            a = fsum(row.get(fuel.code, 0) for row in start)
            delta = fsum(row.get(fuel.code, 0) for row in end) - a
            if abs(delta) < 1e-12:
                if a > fuel.supply_t + 1e-7:
                    return None
            elif delta > 0:
                high = min(high, (fuel.supply_t - a) / delta)
            else:
                low = max(low, (fuel.supply_t - a) / delta)
        if high < low or high < 0 or low > 1:
            return None
        if high >= 1:
            return plan
        scale = max(low, high - 1e-12)
        return tuple(self.choice(i, {k: x * scale for k, x in d[3]}, d[1], len(d) > 4 and d[4])
                     for i, d in enumerate(plan))

    def evaluate(self, plan):
        plan = self.repair_supply(tuple(plan))
        if plan is None:
            return None
        if plan not in self.scores:
            value = simulate(self.scenario, plan, self.use_pool,
                             profile_cache=self.profiles, score_only=True)
            self.scores[plan] = value
            self.evaluations += 1
        value = self.scores[plan]
        return (value, plan) if value is not None and isfinite(value) else None

    def random_plan(self):
        result = []
        for i, v in enumerate(self.scenario.vessels):
            # Include exact zero and cap endpoints as well as interior fractions.
            scale = self.random.choice((0.0, 1.0, self.random.random()))
            shares = {k: self.random.random() for k in self.keys[i]}
            d = self.choice(i, shares, self.random.choice((False, True)),
                            self.random.choice(wind_choices(v)))
            result.append(self.choice(i, {k: x * scale for k, x in d[3]}, d[1], len(d) > 4 and d[4]))
        return tuple(result)

    def offspring(self, left, right):
        """Cross whole ship plans or individual genes, then mutate jointly."""
        result = []
        for i, (a, b) in enumerate(zip(left, right)):
            if self.random.random() < .5:
                d = self.random.choice((a, b))
                shares, ops, wind = dict(d[3]), d[1], len(d) > 4 and d[4]
            else:
                mix = self.random.random()
                shares = {k: mix * x + (1 - mix) * y for (k, x), (_, y) in zip(a[3], b[3])}
                ops = self.random.choice((a[1], b[1]))
                wind = self.random.choice((len(a) > 4 and a[4], len(b) > 4 and b[4]))
            if self.random.random() < max(.25, 1 / len(left)):
                if self.random.random() < .25:
                    ops = not ops
                if self.random.random() < .25:
                    wind = not wind
                if self.random.random() < .15:
                    shares = {}  # An exact no-conversion option avoids tiny capital-triggering blends.
                else:
                    for key in self.keys[i]:
                        if self.random.random() < max(.15, 1 / len(self.keys[i])):
                            shares[key] = self.random.choice((0.0, 1.0, self.random.random(),
                                                             shares.get(key, 0) + self.random.gauss(0, .2)))
            result.append(self.choice(i, shares, ops, wind))
        return tuple(result)


def optimize_hybrid(scenario, use_pool, *, settings=None):
    """Return the original result or a strictly cheaper, fully rescored plan."""
    settings = settings or GASettings()
    incumbent = optimize_legs(scenario, use_pool)
    if incumbent is None:
        return None
    search = _FleetSearch(scenario, use_pool, settings)
    initial = tuple(saved_decision(d) for d in incumbent["decisions"])
    best = (incumbent["npv"], initial)
    population = {initial: best[0]}
    search.scores[initial] = best[0]
    deadline = monotonic() + settings.time_limit_s
    completed = 0

    def add(plan, target):
        nonlocal best
        evaluated = search.evaluate(plan)
        if evaluated is not None:
            cost, feasible = evaluated
            target[feasible] = cost
            if cost < best[0] - 1e-4:
                best = evaluated

    # Deliberate whole-fleet starts preserve endpoints and joint equipment moves.
    for fraction in (0.0, 1.0):
        for ops, wind in ((False, False), (True, False), (False, True), (True, True)):
            if monotonic() >= deadline:
                break
            add(tuple(search.choice(i, {k: fraction for k in keys}, ops, wind)
                      for i, keys in enumerate(search.keys)), population)
    for _ in range(settings.population_size):
        if monotonic() >= deadline:
            break
        add(search.random_plan(), population)
    for generation in range(settings.generations):
        if monotonic() >= deadline:
            break
        ranked = sorted(population, key=population.get)[:settings.population_size]
        # Elitism plus fresh immigrants avoids losing the incumbent or all diversity.
        next_population = {p: population[p] for p in ranked[:max(1, settings.population_size // 8)]}
        def parent():
            return min(search.random.choices(ranked, k=3), key=population.get)
        for child in range(settings.population_size):
            if monotonic() >= deadline:
                break
            plan = search.random_plan() if child % 5 == 0 else search.offspring(parent(), parent())
            add(plan, next_population)
        else:
            completed = generation + 1
        population = next_population
    time_limited = monotonic() >= deadline

    result = incumbent
    if best[0] < incumbent["npv"] - 1e-4:
        candidate = simulate(scenario, best[1], use_pool)
        if candidate is not None and candidate["npv"] < incumbent["npv"] - 1e-4:
            refined = optimize_legs(scenario, use_pool, initial_result=candidate)
            if refined is not None and refined["npv"] < incumbent["npv"] - 1e-4:
                result = refined
                result["evaluations"] += incumbent.get("evaluations", 0)
                result["unique_evaluations"] += incumbent.get("unique_evaluations", 0)
    # Extra metadata is saved/exported; the existing report shape is retained.
    result = dict(result)
    result["evaluations"] = result.get("evaluations", 0) + search.evaluations
    result["unique_evaluations"] = result.get("unique_evaluations", 0) + search.evaluations
    result["ga_search"] = {"method": "hybrid-ga-v1", "seed": settings.seed,
                           "population_size": settings.population_size,
                           "generation_limit": settings.generations, "time_limit_s": settings.time_limit_s,
                           "generations_completed": completed, "evaluations": search.evaluations,
                           "time_limited": time_limited, "incumbent_npv": incumbent["npv"],
                           "improvement_npv": incumbent["npv"] - result["npv"]}
    return result
