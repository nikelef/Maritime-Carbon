"""Bounded continuous voyage-leg search using full fleet and horizon costs."""
from math import fsum, sqrt
from .allocation import allocation_breakpoints

from .calculator import (leg_demands, optimize_fuels, profile, simulate,
                         add_replacement_priority, GRID_INTERVALS)


def leg_decision(demands, shares, ops):
    fractions = tuple((key, min(1.0, max(0.0, shares.get(key, 0)))) for key in demands)
    return (fsum(demands[key]["weight"] * value for key, value in fractions), ops, None, fractions)


def optimize_legs(scenario, use_pool):
    # Retain the previous search as a feasible incumbent: extending the search
    # must never discard a cheaper previously evaluated allocation.
    seed = optimize_fuels(scenario, use_pool)
    if seed is None:
        return None
    demands = [leg_demands(v, scenario) for v in scenario.vessels]
    initial = [leg_decision(ds, {key: out["replacements"].get(d["fuel"], 0)
                               for key, d in ds.items()}, out["ops"])
               for ds, out in zip(demands, seed["decisions"])]
    zero = [leg_decision(ds, {}, False) for ds in demands]
    profile_cache, score_cache = {}, {}

    def score(choices):
        key = tuple(choices)
        if key not in score_cache:
            score_cache[key] = simulate(scenario, choices, use_pool,
                                       profile_cache=profile_cache, score_only=True)
        return score_cache[key]

    def physical(index, year, choice):
        key = (index, year, *choice)
        if key not in profile_cache:
            profile_cache[key] = profile(scenario.vessels[index], scenario, year, *choice)
        return profile_cache[key]

    def line_search(current, index, left, right):
        """Check limits and balance roots, then refine the best sampled interval.

        No convexity/global optimality claim: banking and pooling can create
        multiple basins. The coarse samples, two starts and pair transfers
        provide bounded coverage of those basins.
        """
        ds = demands[index]
        a, b = dict(left[3]), dict(right[3])
        def choice(t):
            return leg_decision(ds, {key: a[key] + t * (b[key]-a[key]) for key in ds}, left[1])
        # Fuel supply is linear in the allocations and shared across the fleet.
        first = scenario.start_year
        pa, pb = physical(index, first, left), physical(index, first, right)
        low, high = 0.0, 1.0
        for fuel in scenario.fuels:
            if fuel.supply_t is None:
                continue
            others = fsum(physical(j, first, d)["fuel_tonnes"].get(fuel.code, 0)
                          for j, d in enumerate(current) if j != index)
            start = others + pa["fuel_tonnes"].get(fuel.code, 0)
            delta = pb["fuel_tonnes"].get(fuel.code, 0) - pa["fuel_tonnes"].get(fuel.code, 0)
            if abs(delta) < 1e-12:
                if start > fuel.supply_t + 1e-7:
                    return None, None
            elif delta > 0:
                high = min(high, (fuel.supply_t-start)/delta)
            else:
                low = max(low, (fuel.supply_t-start)/delta)
        if high < low or high < 0 or low > 1:
            return None, None
        low, high = max(0.0, low), min(1.0, high)
        points = {low, high} | {low+(high-low)*i/GRID_INTERVALS for i in range(1, GRID_INTERVALS)}
        # FuelEU attribution changes slope whenever a cumulative source capacity
        # reaches the Article 2 energy total. Whole-line interpolation of the
        # compliance balance is no longer valid. Split at all such boundaries.
        kinks = allocation_breakpoints(pa, pb, low, high)
        points.update(kinks)
        years = range(scenario.start_year, scenario.end_year+1)
        other_balances = {year: fsum(physical(j, year, d)["balance_t"]
                          for j, d in enumerate(current) if j != index) for year in years}
        residual_cache = {}

        def residuals(t):
            if t not in residual_cache:
                bank = scenario.vessels[index].opening_bank
                fleet = fsum(v.opening_bank for v in scenario.vessels)
                values = []
                for year in years:
                    p = physical(index, year, choice(t))
                    balance = p["balance_t"]
                    other = other_balances[year]
                    bank += balance
                    fleet += balance + other
                    values.extend((balance, bank, balance+other,
                                   balance+other+scenario.pool_cap-1e-6, fleet))
                    if p["rfnbo_subtarget_active"]:
                        values.append(p["rfnbo_energy_mj"] - .02*p["fuel_energy_mj"])
                residual_cache[t] = values
            return residual_cache[t]

        boundaries = sorted({low, high} | kinks)
        for start, end in zip(boundaries, boundaries[1:]):
            for position, (x, y) in enumerate(zip(residuals(start), residuals(end))):
                if x*y >= 0 or abs(y-x) < 1e-12:
                    continue
                t = start - x*(end-start)/(y-x)
                # With RFNBO reward, balances can be rational, not linear.
                # Validate interpolation and bisect the actual annual profiles.
                value = residuals(t)[position]
                if abs(value) > 1e-9:
                    lo, hi, flo = start, end, x
                    for _ in range(40):
                        if value*flo > 0:
                            lo, flo = t, value
                        else:
                            hi = t
                        t = (lo+hi)/2
                        value = residuals(t)[position]
                        if abs(value) < 1e-10:
                            break
                points.add(t)
        samples = sorted(points)
        best_choice, best_value, best_t = None, None, low
        def evaluate(t):
            nonlocal best_choice, best_value, best_t
            candidate = choice(t)
            attempt = list(current); attempt[index] = candidate
            value = score(attempt)
            if value is not None and (best_value is None or value < best_value-1e-6):
                best_choice, best_value, best_t = candidate, value, t
            return float("inf") if value is None else value
        for t in samples:
            evaluate(t)
        if best_choice is None:
            return None, None
        # Refine around the best sampled point, including an interior minimum
        # that is not itself a regulatory or capacity boundary.
        k = samples.index(best_t)
        lo, hi = samples[max(0,k-1)], samples[min(len(samples)-1,k+1)]
        ratio = (sqrt(5)-1)/2
        x, y = hi-ratio*(hi-lo), lo+ratio*(hi-lo)
        fx, fy = evaluate(x), evaluate(y)
        for _ in range(36):
            if hi-lo < 1e-10:
                break
            if fx <= fy:
                hi, y, fy = y, x, fx
                x = hi-ratio*(hi-lo); fx = evaluate(x)
            else:
                lo, x, fx = x, y, fy
                y = lo+ratio*(hi-lo); fy = evaluate(y)
        return best_choice, best_value

    best, best_value = initial, score(initial)
    for start in (initial, zero):
        current, value = list(start), score(start)
        if value is None:
            continue
        for _ in range(3):
            improved = False
            for index, (vessel, ds) in enumerate(zip(scenario.vessels, demands)):
                alternative = next(f for f in scenario.fuels if f.code == vessel.alternative)
                can_switch = vessel.compatible and alternative.available_for_use and vessel.max_blend > 0
                keys = [key for key, d in ds.items() if d["fuel"] != vessel.alternative] if can_switch else []
                for ops in ([False, True] if vessel.ops_ready else [False]):
                    candidate = leg_decision(ds, dict(current[index][3]), ops)
                    attempt = list(current); attempt[index] = candidate
                    candidate_value = score(attempt)
                    if candidate_value is not None and candidate_value < value-1e-4:
                        current[index], value, improved = candidate, candidate_value, True
                    for key in keys:
                        shares = dict(current[index][3])
                        others = fsum(d["weight"]*shares[k] for k,d in ds.items() if k != key)
                        limit = min(1.0, max(0.0, vessel.max_blend-others)/ds[key]["weight"])
                        left = leg_decision(ds, shares | {key: 0.0}, ops)
                        right = leg_decision(ds, shares | {key: limit}, ops)
                        candidate, candidate_value = line_search(current, index, left, right)
                        if candidate_value is not None and candidate_value < value-1e-4:
                            current[index], value, improved = candidate, candidate_value, True
                    # Move an already allocated energy amount to another leg
                    # without requiring temporary extra ship capacity.
                    for recipient in keys:
                        for donor in keys:
                            shares = dict(current[index][3])
                            if donor == recipient or shares[donor] <= 1e-9 or shares[recipient] >= 1-1e-9:
                                continue
                            energy = min(ds[donor]["weight"]*shares[donor],
                                         ds[recipient]["weight"]*(1-shares[recipient]))
                            left = leg_decision(ds, shares, ops)
                            right = leg_decision(ds, shares | {donor: shares[donor]-energy/ds[donor]["weight"],
                                                              recipient: shares[recipient]+energy/ds[recipient]["weight"]}, ops)
                            candidate, candidate_value = line_search(current, index, left, right)
                            if candidate_value is not None and candidate_value < value-1e-4:
                                current[index], value, improved = candidate, candidate_value, True
            if not improved:
                break
        if best_value is None or value < best_value-1e-4:
            best, best_value = list(current), value
    result = simulate(scenario, best, use_pool, profile_cache=profile_cache)
    result["evaluations"] = len(score_cache)
    add_replacement_priority(scenario, result, best, score)
    result["unique_evaluations"] = len(score_cache)
    for output in result["decisions"]:
        output["leg_remarks"] = [
            f"Voyage {d['voyage']} · {d['leg_label']}: replace {d['replaced_t']:.3f} t/year of {d['fuel']} "
            f"with {d['alternative_t']:.3f} t/year of {output['alternative']}"
            + (f" + {d['pilot_t']:.3f} t/year MGO pilot" if d['pilot_t'] > 0 else "")
            + "; supply the replacement energy on this same leg."
            for d in output["leg_replacements"] if d["replaced_t"] > 1e-8]
    return result
