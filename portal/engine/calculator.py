"""Pure annual cash-flow model, independent of the web framework.

FuelEU accounts are ship-specific. ETS mass is always allocated proportionally.
Prices are assumptions, and pools are conditional commercial arrangements.
"""
from dataclasses import replace
from math import fsum, isfinite
from .rules import target, ets_phase, penalty, borrowing_limit, rfnbo_reward, LNG_CONSUMERS, GWP_CH4, GWP_N2O, SOURCES, CHECKED_ON


def physical_factors(fuel, consumer=""):
    if fuel.ch4 is None or fuel.n2o is None:
        raise ValueError(f"{fuel.code}: missing measured CH4/N2O factors.")
    slip = 0
    if fuel.pathway == "methane":
        if consumer not in LNG_CONSUMERS:
            raise ValueError(f"{fuel.code}: select the LNG consumer class.")
        slip = LNG_CONSUMERS[consumer][1]
    return (fuel.co2 * (1 - slip), fuel.ch4 * (1 - slip) + slip, fuel.n2o * (1 - slip))


def emissions_factor(fuel, year, consumer=""):
    co2, ch4, n2o = physical_factors(fuel, consumer)
    co2 = 0 if fuel.ets_zero_rated else co2
    return co2 + (ch4 * GWP_CH4 + n2o * GWP_N2O if year >= 2026 else 0)


def fuel_intensity(fuel, consumer=""):
    if fuel.pathway == "methane" or fuel.rfnbo:
        if fuel.wtt is None:
            raise ValueError(f"{fuel.code}: missing FuelEU WtT pathway factor.")
        co2, ch4, n2o = physical_factors(fuel, consumer)
        return fuel.wtt + (co2 + ch4 * GWP_CH4 + n2o * GWP_N2O) * 1e6 / fuel.lcv
    return fuel.wtw


def sea_demands(vessel, scenario):
    """Annual sea tonnes by fuel, including any legacy separate MGO pilot."""
    tonnes = {}
    for entry in vessel.sea_fuel_entries():
        tonnes[entry["fuel"]] = tonnes.get(entry["fuel"], 0) + entry["sea_t"]
    if vessel.current_pilot_t:
        tonnes["MGO"] = tonnes.get("MGO", 0) + vessel.current_pilot_t
    fuels = {f.code: f for f in scenario.fuels}
    total = fsum(t * fuels[c].lcv for c, t in tonnes.items())
    return {c: {"tonnes": t, "weight": t * fuels[c].lcv / total}
            for c, t in sorted(tonnes.items()) if t > 0} if total else {}


def profile(vessel, scenario, year, blend=0, ops=False, replacements=None):
    fuels = {f.code: f for f in scenario.fuels}
    alt, berth = fuels[vessel.alternative], fuels["MGO"]
    if isinstance(blend, bool) or not isinstance(blend, (int, float)) or not isfinite(blend):
        raise ValueError("Replacement share must be a finite number.")
    entries = vessel.sea_fuel_entries()
    demands = sea_demands(vessel, scenario)
    # Scalar decisions remain supported for old callers. New decisions specify
    # the fraction of each current fuel removed, aggregated across its sea legs.
    shares = {code: blend for code in demands} if replacements is None else dict(replacements)
    if (set(shares) - set(demands) or
            any(isinstance(x, bool) or not isinstance(x, (int, float)) or
                not isfinite(x) or x < 0 or x > 1 for x in shares.values())):
        raise ValueError("Invalid current-fuel replacement allocation.")
    actual_blend = fsum(d["weight"] * shares.get(code, 0) for code, d in demands.items())
    if replacements is not None and abs(blend - actual_blend) > 1e-9:
        raise ValueError("Fuel allocations do not match the overall replacement share.")
    if blend < 0 or blend > vessel.max_blend + 1e-10:
        raise ValueError("Replacement exceeds the vessel's service-share limit.")
    if blend and (not vessel.compatible or not alt.available_for_use):
        raise ValueError("Fuel substitution requires compatibility and fuel evidence.")
    if ops and not vessel.ops_ready:
        raise ValueError("Shore power requires confirmed ship/port readiness.")
    # Keep the same service demand. Pilot fuel is part of the system's energy,
    # not an unpriced addition to an otherwise 100% renewable replacement.
    sea_scope = vessel.intra_share + .5 * vessel.extra_share
    reference_energy = fsum(entry["sea_t"] * fuels[entry["fuel"]].lcv for entry in entries) + vessel.current_pilot_t * berth.lcv
    replaced_energy = reference_energy * actual_blend
    scoped_replaced_energy = fsum(entry["sea_t"] * shares.get(entry["fuel"], 0) * fuels[entry["fuel"]].lcv * (entry["intra_share"] + .5 * entry["extra_share"]) for entry in entries) + vessel.current_pilot_t * shares.get("MGO", 0) * berth.lcv * sea_scope
    alternative_scope = scoped_replaced_energy / replaced_energy if replaced_energy else 0
    baseline_fuels = [dict(entry, sea_t=entry["sea_t"] * (1 - shares.get(entry["fuel"], 0))) for entry in entries]
    fossil_t = fsum(entry["sea_t"] for entry in baseline_fuels)
    alternative_system_energy = replaced_energy * vessel.alternative_energy_ratio
    alt_t = alternative_system_energy * (1 - vessel.alternative_pilot_share) / alt.lcv
    remaining_pilot_t = vessel.current_pilot_t * (1 - shares.get("MGO", 0))
    alternative_pilot_t = alternative_system_energy * vessel.alternative_pilot_share / berth.lcv
    pilot_t = remaining_pilot_t + alternative_pilot_t
    berth_fuels = []
    replaced_berth_energy = []
    for entry in vessel.berth_fuel_entries():
        share = entry.get("ops_share", vessel.ops_fraction) if ops else 0
        replaced_berth_energy.append(entry["eu_berth_t"] * share * fuels[entry["fuel"]].lcv)
        berth_fuels.append(dict(entry, eu_berth_t=entry["eu_berth_t"] * (1-share)))
    berth_t = fsum(entry["eu_berth_t"] for entry in berth_fuels)
    non_eu_berth_t = fsum(entry["non_eu_berth_t"] for entry in berth_fuels)
    # Only eligible EU berth generator fuel is replaced; non-EU berth is untouched.
    electricity_mwh = fsum(replaced_berth_energy) * vessel.generator_efficiency / vessel.ops_efficiency / 3600
    fueleu_applies = vessel.gt > 5000
    ets_applies = vessel.gt >= 5000
    sea_parts = [(fuels[entry["fuel"]], entry["sea_t"], vessel.fuel_consumer, entry["intra_share"] + .5 * entry["extra_share"]) for entry in baseline_fuels]
    sea_parts += [(alt, alt_t, vessel.alternative_consumer, alternative_scope),
                  (berth, remaining_pilot_t, "", sea_scope), (berth, alternative_pilot_t, "", alternative_scope)]
    for entry in berth_fuels:
        sea_parts.extend([(fuels[entry["fuel"]], entry["eu_berth_t"], vessel.berth_consumer, 1),
                          (fuels[entry["fuel"]], entry["non_eu_berth_t"], vessel.berth_consumer, 0)])
    parts = [(f, tonnes, consumer, scope) for f, tonnes, consumer, scope in sea_parts if tonnes > 0]
    scoped_fuel_energy = fsum(tonnes * f.lcv * scope for f, tonnes, _, scope in parts)
    energy = (scoped_fuel_energy + electricity_mwh * 3600) if fueleu_applies else 0
    numerator = fsum(tonnes * f.lcv * fuel_intensity(f, consumer) * scope for f, tonnes, consumer, scope in parts) if fueleu_applies else 0
    rfnbo_energy = fsum(tonnes * f.lcv * scope for f, tonnes, _, scope in parts if f.rfnbo and f.eligible) if fueleu_applies else 0
    reward_eligible_energy = fsum(tonnes * f.lcv * scope for f, tonnes, _, scope in parts if f.rfnbo and f.eligible and f.reward_enabled) if fueleu_applies else 0
    rewarded_energy = energy + (rfnbo_reward(year) - 1) * reward_eligible_energy
    # Annex I: electricity from shore has zero emissions in this regulatory intensity.
    attained = numerator / rewarded_energy if rewarded_energy else 0
    # Annex IV uses physical energy, not the RFNBO-rewarded denominator.
    balance = (target(year) - attained) * energy / 1e6
    ets = fsum(tonnes * emissions_factor(f, year, consumer) * scope for f, tonnes, consumer, scope in parts) * ets_phase(year) if ets_applies else 0
    ch4_t = fsum(tonnes * physical_factors(f, consumer)[1] * scope for f, tonnes, consumer, scope in parts)
    fuel_energy = scoped_fuel_energy if fueleu_applies else 0
    rfnbo_deficit = max(0, .02 * fuel_energy - rfnbo_energy) if year >= 2034 else 0
    rfnbo_active = year >= 2034 and scenario.rfnbo_subtarget == "assume_active"
    if rfnbo_active and scenario.rfnbo_penalty_pd is None:
        raise ValueError("An active RFNBO subtarget stress test requires a price-difference factor.")
    delta = year - scenario.start_year
    fuel_multiplier = (1 + scenario.fuel_escalation) ** delta
    fuel_cost = fsum(tonnes * f.price for f, tonnes, _, _ in parts) * fuel_multiplier
    fuel_tonnes = {code: fsum(tonnes for f, tonnes, _, _ in parts if f.code == code) for code in fuels}
    electricity_cost = electricity_mwh * scenario.electricity_price * fuel_multiplier
    ets_cost = ets * scenario.eua_price * (1 + scenario.eua_escalation) ** delta
    return {"vessel": vessel.name, "year": year, "target_g": target(year), "attained_g": attained,
            "energy_mj": energy, "balance_t": balance, "ets_t": ets, "fuel_cost": fuel_cost,
            "ets_cost": ets_cost, "electricity_cost": electricity_cost, "electricity_mwh": electricity_mwh,
            "alternative_t": alt_t, "fossil_t": fossil_t, "baseline_t": fossil_t, "berth_t": berth_t, "pilot_t": pilot_t, "berth_fuels": berth_fuels, "non_eu_berth_t": non_eu_berth_t,
            "alternative": alt.code, "blend": blend, "ops": ops,
            "fuel_replacements": [{"fuel": code, "fraction": shares.get(code, 0),
                                   "original_t": d["tonnes"], "replaced_t": d["tonnes"] * shares.get(code, 0),
                                   "remaining_t": d["tonnes"] * (1 - shares.get(code, 0))}
                                  for code, d in demands.items()],
            "baseline_fuel": " + ".join(entry["fuel"] for entry in entries), "baseline_fuels": baseline_fuels,
            "fuel_tonnes": fuel_tonnes, "baseline_consumer": vessel.fuel_consumer, "alternative_consumer": vessel.alternative_consumer,
            "baseline_slip_pct": LNG_CONSUMERS[vessel.fuel_consumer][1] * 100 if any(fuels[entry["fuel"]].pathway == "methane" and entry["sea_t"] > 0 for entry in baseline_fuels) else 0,
            "alternative_slip_pct": LNG_CONSUMERS[vessel.alternative_consumer][1] * 100 if alt.pathway == "methane" and alt_t else 0,
            "scoped_ch4_t": ch4_t, "fuel_energy_mj": fuel_energy,
            "rfnbo_energy_mj": rfnbo_energy, "rewarded_energy_mj": rewarded_energy,
            "rfnbo_reward": 1 + (rfnbo_reward(year) - 1) * reward_eligible_energy / rfnbo_energy if rfnbo_energy else 1,
            "rfnbo_share": rfnbo_energy / fuel_energy if fuel_energy else 0,
            "rfnbo_deficit_mj": rfnbo_deficit, "rfnbo_subtarget_active": rfnbo_active,
            "rfnbo_penalty_base": rfnbo_deficit / 41000 * scenario.rfnbo_penalty_pd if rfnbo_active else 0,
            "implementation_cost": ((vessel.ops_annual + (vessel.ops_capex if delta == 0 else 0)) if ops else 0) + ((vessel.fuel_annual + (vessel.fuel_capex if delta == 0 else 0)) if blend else 0),
            "borrowing_limit_t": borrowing_limit(energy, year)}


def simulate(scenario, decisions, use_pool=False, *, profile_cache=None, score_only=False):
    if len(decisions) != len(scenario.vessels):
        raise ValueError("Each vessel needs exactly one strategy decision.")
    banks = [v.opening_bank for v in scenario.vessels]
    streaks = [v.prior_penalties for v in scenario.vessels]
    rows, annual, scores = [], [], []
    for year in range(scenario.start_year, scenario.end_year + 1):
        year_rows = []
        for index, (vessel, decision) in enumerate(zip(scenario.vessels, decisions)):
            key = (index, year, *decision)
            if profile_cache is not None:
                if key not in profile_cache:
                    profile_cache[key] = profile(vessel, scenario, year, *decision)
                year_rows.append(dict(profile_cache[key]))
            else:
                year_rows.append(profile(vessel, scenario, year, *decision))
        for fuel in scenario.fuels:
            used = fsum(r["fuel_tonnes"].get(fuel.code, 0) for r in year_rows)
            if fuel.supply_t is not None and used > fuel.supply_t + 1e-7:
                return None
        for i, row in enumerate(year_rows):
            row["bank_open_t"] = banks[i]
            row["bank_used_t"] = min(banks[i], max(0, -row["balance_t"]))
            banks[i] -= row["bank_used_t"]
            row["settlement_balance_t"] = row["balance_t"] + row["bank_used_t"]
            row.update(pool_transfer_t=0.0, pool_buy_t=0.0, pool_cost=0.0)
        deficits = fsum(max(0, -r["settlement_balance_t"]) for r in year_rows)
        surplus = fsum(max(0, r["settlement_balance_t"]) for r in year_rows)
        external_need = max(0, deficits - surplus)
        # A pooled result is used only when the whole modelled fleet can be settled.
        # Retain a small positive donor balance for the Article 21 positive-pool rule.
        buffer = 1e-6 if deficits > 1e-9 else 0.0
        internal_valid = surplus - deficits > buffer
        external_valid = scenario.pool_enabled and external_need + buffer <= scenario.pool_cap
        pooled = use_pool and deficits > 1e-9 and (internal_valid or external_valid)
        if pooled:
            donor_take = min(max(0, surplus - buffer), deficits)
            external_buy = max(0, deficits - donor_take)
            for row in year_rows:
                balance = row["settlement_balance_t"]
                if balance > 0 and surplus:
                    row["pool_transfer_t"] = -donor_take * balance / surplus
                elif balance < 0:
                    share = -balance / deficits
                    row["pool_transfer_t"] = donor_take * share
                    row["pool_buy_t"] = external_buy * share
                    row["pool_cost"] = row["pool_buy_t"] * scenario.pool_price
                row["settlement_balance_t"] += row["pool_transfer_t"] + row["pool_buy_t"]
        for i, row in enumerate(year_rows):
            deficit = max(0, -row["settlement_balance_t"])
            penalized = deficit > 1e-9 or (row["rfnbo_subtarget_active"] and row["rfnbo_deficit_mj"] > 1e-6)
            streaks[i] = streaks[i] + 1 if penalized else 0
            row["penalty_years"] = streaks[i]
            row["ghg_penalty_cost"] = penalty(deficit, row["attained_g"], max(1, streaks[i]))
            row["rfnbo_penalty_cost"] = row["rfnbo_penalty_base"] * (1 + (max(1, streaks[i]) - 1) / 10)
            row["penalty_cost"] = row["ghg_penalty_cost"] + row["rfnbo_penalty_cost"]
            row["residual_deficit_t"] = deficit
            banks[i] += max(0, row["settlement_balance_t"])
            row["bank_close_t"] = banks[i]
            row["pooled"] = pooled and row["energy_mj"] > 0
            row["total_cost"] = fsum(row[k] for k in ("fuel_cost", "electricity_cost", "ets_cost", "penalty_cost", "pool_cost", "implementation_cost"))
            row["npv_cost"] = row["total_cost"] / (1 + scenario.discount_rate) ** (year - scenario.start_year)
        if score_only:
            scores.append(fsum(r["npv_cost"] for r in year_rows) + scenario.other_annual_cost / (1 + scenario.discount_rate) ** (year - scenario.start_year))
            continue
        sums = {key: fsum(r[key] for r in year_rows) for key in ("fuel_cost", "electricity_cost", "ets_cost", "penalty_cost", "pool_cost", "implementation_cost", "total_cost", "npv_cost", "ets_t", "balance_t", "pool_buy_t", "bank_close_t", "residual_deficit_t", "electricity_mwh", "alternative_t")}
        sums["other_cost"] = scenario.other_annual_cost
        sums.update({key: fsum(r[key] for r in year_rows) for key in ("ghg_penalty_cost", "rfnbo_penalty_cost", "rfnbo_energy_mj", "rfnbo_deficit_mj", "pilot_t")})
        sums["total_cost"] += scenario.other_annual_cost
        sums["npv_cost"] += scenario.other_annual_cost / (1 + scenario.discount_rate) ** (year - scenario.start_year)
        sums["implementation_and_other_cost"] = sums["implementation_cost"] + sums["other_cost"]
        sums["year"] = year
        sums["target_g"] = target(year)
        sums["pool_used"] = pooled
        annual.append(sums)
        rows.extend(year_rows)
    if score_only:
        return fsum(scores)
    return {"npv": fsum(r["npv_cost"] for r in annual), "total": fsum(r["total_cost"] for r in annual), "annual": annual, "rows": rows, "decisions": [{"vessel": v.name, "alternative": v.alternative, "blend": d[0], "ops": d[1],
            "replacements": {item["fuel"]: item["fraction"] for item in row["fuel_replacements"]},
            "fuel_replacements": row["fuel_replacements"], "alternative_t": row["alternative_t"]}
            for v, d, row in zip(scenario.vessels, decisions, rows[:len(scenario.vessels)])], "use_pool": use_pool,
            "residual_deficit_t": fsum(r["residual_deficit_t"] for r in annual), "pool_cost": fsum(r["pool_cost"] for r in annual), "penalty_cost": fsum(r["penalty_cost"] for r in annual)}


def allocated_decision(demands, shares, ops):
    fractions = tuple((code, min(1.0, max(0.0, shares.get(code, 0)))) for code in demands)
    return (fsum(demands[code]["weight"] * share for code, share in fractions), ops, fractions)


def share_grid(limit):
    return sorted({0.0, max(0.0, limit)} | {i / 20 for i in range(1, 21) if i / 20 <= limit})


def options(vessel, scenario):
    fuel = next(f for f in scenario.fuels if f.code == vessel.alternative)
    shares = [0.0]
    if vessel.compatible and fuel.available_for_use:
        shares = share_grid(vessel.max_blend)
    demands = sea_demands(vessel, scenario)
    return [allocated_decision(demands, {code: share if code != vessel.alternative else 0 for code in demands}, ops)
            for share in shares for ops in ([False, True] if vessel.ops_ready else [False])]


def allocation_options(vessel, scenario, decision):
    """Vary one fuel or transfer replacement between two fuels at fixed total.

    Steps are 5% of the ship's total original sea energy, with exact fuel
    exhaustion and remaining vessel-cap endpoints. Each fuel retains its legs.
    Pair transfers allow a full cap to move from one source fuel to another.
    """
    demands = sea_demands(vessel, scenario)
    fuel = next(f for f in scenario.fuels if f.code == vessel.alternative)
    candidates = set(options(vessel, scenario))
    if not vessel.compatible or not fuel.available_for_use:
        return sorted(candidates)
    shares = dict(decision[2]) if len(decision) > 2 else {code: decision[0] for code in demands}
    amounts = {code: d["weight"] * shares.get(code, 0) for code, d in demands.items()}
    codes = [code for code in demands if code != vessel.alternative]
    ops_choices = [False, True] if vessel.ops_ready else [False]

    def add(values):
        ratios = {code: amount / demands[code]["weight"] for code, amount in values.items()}
        for ops in ops_choices:
            candidates.add(allocated_decision(demands, ratios, ops))

    add(amounts)
    for code in codes:
        others = fsum(value for c, value in amounts.items() if c != code)
        limit = min(demands[code]["weight"], max(0.0, vessel.max_blend - others))
        for amount in share_grid(limit):
            add(dict(amounts, **{code: amount}))
        for donor in codes:
            if donor == code or amounts[donor] <= 1e-12:
                continue
            limit = min(amounts[donor], demands[code]["weight"] - amounts[code])
            for transfer in share_grid(limit):
                add(dict(amounts, **{code: amounts[code] + transfer, donor: amounts[donor] - transfer}))
    return sorted(candidates)


def optimize(scenario, use_pool):
    """Deterministic per-fuel coordinate search with bounded pair transfers.

    Decisions stay fixed across the horizon. This is not a global optimizer of
    banking, chartering, fuel procurement or voyage scheduling.
    """
    choices = [options(v, scenario) for v in scenario.vessels]
    zero = [c[0] for c in choices]
    profile_cache = {}
    score_cache = {}

    def score(decisions):
        key = tuple(decisions)
        if key not in score_cache:
            score_cache[key] = simulate(scenario, decisions, use_pool, profile_cache=profile_cache, score_only=True)
        return score_cache[key]

    best_score = score(zero)
    best_decisions = list(zero)
    trials = 0
    # Different starts help with the discontinuity at fleet pooling feasibility.
    for initial in (zero, [c[-1] for c in choices]):
        current = list(initial)
        current_score = score(current)
        if current_score is None:
            current, current_score = list(zero), score(zero)
        if current_score is None:
            # A baseline supply cap can require substitution; search uniform starts.
            for share in range(21):
                candidate = [min(c, key=lambda d: abs(d[0] - share / 20) + int(d[1])) for c in choices]
                candidate_score = score(candidate)
                if candidate_score is not None:
                    current, current_score = candidate, candidate_score
                    break
        if current_score is None:
            continue
        for _ in range(3):
            changed = False
            for index, vessel in enumerate(scenario.vessels):
                for _ in range(3):
                    selected = current[index]
                    for candidate in allocation_options(vessel, scenario, current[index]):
                        attempt = list(current)
                        attempt[index] = candidate
                        candidate_score = score(attempt)
                        trials += 1
                        if candidate_score is not None and candidate_score < current_score - .001:
                            selected, current_score = candidate, candidate_score
                    if selected == current[index]:
                        break
                    changed = True
                    current[index] = selected
            if not changed:
                break
        if best_score is None or current_score < best_score:
            best_decisions, best_score = list(current), current_score
    if best_score is None:
        return None
    best = simulate(scenario, best_decisions, use_pool, profile_cache=profile_cache)
    best["evaluations"] = trials
    add_replacement_priority(scenario, best, best_decisions, score)
    best["unique_evaluations"] = len(score_cache)
    return best


def add_replacement_priority(scenario, result, decisions, score):
    """Compare current source fuels and rank the selected reductions by cost.

    Other vessels and this ship's OPS choice are held at the selected strategy.
    Ranking is explanatory, not a claim of a chronological or global optimum.
    """
    for index, (vessel, output) in enumerate(zip(scenario.vessels, result["decisions"])):
        selected = [entry for entry in output["fuel_replacements"] if entry["fraction"] > 1e-9]
        if not selected:
            output["replacement_priority"] = []
            output["first_step_comparison"] = []
            continue
        demands = sea_demands(vessel, scenario)
        sources = [entry for entry in output["fuel_replacements"] if entry["fuel"] != vessel.alternative]
        step = min(.05, vessel.max_blend, *(demands[e["fuel"]]["weight"] for e in sources))
        trial = list(decisions)
        trial[index] = allocated_decision(demands, {}, output["ops"])
        reference = score(trial)
        comparisons = []
        for entry in sources:
            code = entry["fuel"]
            trial = list(decisions)
            trial[index] = allocated_decision(demands, {code: step / demands[code]["weight"]}, output["ops"])
            value = score(trial)
            comparisons.append(dict(entry, first_step_npv=value,
                                    first_step_savings=reference - value if reference is not None and value is not None else None))
        output["first_step_comparison"] = sorted(comparisons, key=lambda e: (
            e["first_step_npv"] is None, e["first_step_npv"] or 0, e["fuel"]))
        output["priority_step"] = step
        ranked = [entry for entry in output["first_step_comparison"] if entry["fraction"] > 1e-9]
        if any(entry["first_step_npv"] is None for entry in ranked):
            output["replacement_priority"] = []
            output["priority_note"] = "Fuel supply limits prevent a like-for-like first-step comparison; use the selected quantities together."
        else:
            output["replacement_priority"] = sorted(ranked, key=lambda e: (e["first_step_npv"], e["fuel"]))


def fuel_choice_notices(scenario):
    """Explain selection gates separately from economic rejection of a fuel."""
    fuels = {fuel.code: fuel for fuel in scenario.fuels}
    notices = []
    for index, vessel in enumerate(scenario.vessels):
        fuel = fuels[vessel.alternative]
        reasons = []
        if not vessel.compatible:
            reasons.append("Vessel compatibility has not been confirmed.")
        if vessel.max_blend == 0:
            reasons.append("The vessel's maximum replacement share is 0%.")
        if fuel.renewable and not fuel.eligible:
            reasons.append("FuelEU pathway eligibility is not enabled in the fuel library. A low WtW value alone does not enable this fuel.")
        if fuel.measured_factors_required and not fuel.factors_confirmed:
            reasons.append("Required measured emission factors have not been confirmed.")
        if fuel.supply_t == 0:
            reasons.append("The annual fleet supply limit for this fuel is zero.")
        if not any(code != vessel.alternative for code in sea_demands(vessel, scenario)):
            reasons.append("There is no current sea fuel to replace with this alternative; sea-fuel switching does not replace berth consumption.")
        if reasons:
            notices.append({"vessel": vessel.name, "vessel_index": index, "fuel": fuel.code,
                            "excluded": True, "reasons": reasons})
        elif fuel.renewable and not fuel.ets_zero_rated:
            notices.append({"vessel": vessel.name, "vessel_index": index, "fuel": fuel.code,
                            "excluded": False, "reasons": [
                                "This fuel is evaluated, but ETS CO2 zero-rating is not enabled. Its physical CO2 factor is still charged under ETS; lowering FuelEU WtW does not change that factor."]})
    return notices


def compare(scenario):
    scenario.validate()
    zero = [(0, False)] * len(scenario.vessels)
    baseline = simulate(scenario, zero)
    if baseline is None:
        raise ValueError("Baseline fuel consumption exceeds an entered annual supply cap. Adjust the baseline or cap before comparing.")
    strategies = []
    for key, name, result in [
        ("baseline", "Current fuels · settle deficits", baseline),
        ("pool", "Current fuels · arrange pooling", simulate(scenario, zero, True)),
        ("fuel", "Fuel & shore-power choices", optimize(scenario, False)),
        ("combined", "Fuel choices & pooling", optimize(scenario, True)),
    ]:
        if result:
            result.update(key=key, name=name, savings=baseline["npv"] - result["npv"])
            strategies.append(result)
    strategies.sort(key=lambda s: (s["npv"], s["key"] != "baseline", s["key"]))
    coverage_limits = []
    warnings = ["Prices and consumption are planning assumptions; prices are not a live market feed.",
                "Lowest evaluated cost selects replacement separately by current sea fuel. The search varies or transfers replacement in steps of 5% of total baseline sea energy, including exact fuel-exhaustion and vessel-limit endpoints. Two starts, up to three fleet passes and three allocation passes per ship are used. Decisions are fixed over the horizon; a global optimum is not guaranteed.",
                "Annual fuel shares use proportional voyage allocation. Confirm EU/EEA applicability, exclusions and transhipment rules for both regimes before relying on results.",
                "Unused banked surplus has no cash income or terminal value. No surplus sale or borrowing is assumed."]
    if not scenario.pool_enabled:
        warnings.append("External pooling is disabled. Only a self-sufficient fleet pool can offset balances across ships.")
    else:
        warnings.append("External pooling is conditional on the entered quote/capacity, a positive complete pool, verifier acceptance and database registration. No units are bought by this application.")
    if scenario.end_year >= 2030 and any(v.ship_type in ("container", "passenger") for v in scenario.vessels):
        coverage_limits.append("Mandatory OPS port-call penalties and exemptions for container/passenger ships are not priced.")
        warnings.append("OPS obligations for container/passenger ships from 2030 (and wider port coverage from 2035) require a port-call assessment. OPS non-compliance penalties and exemptions are not calculated; these results are not a complete compliance-cost forecast for those ships.")
    if scenario.end_year >= 2034:
        if scenario.rfnbo_subtarget == "unresolved":
            coverage_limits.append("Conditional RFNBO subtarget from 2034: possible shortfall is shown but its penalty is unpriced. Select a future-rule assumption to stress-test the cost.")
        elif scenario.rfnbo_subtarget == "assume_active":
            coverage_limits.append("RFNBO subtarget penalties use an assumed activation and user-entered price-difference factor, not a settled future statutory tariff.")
        else:
            coverage_limits.append("RFNBO subtarget is assumed inactive from 2034; that is a planning assumption, not a confirmed exemption.")
        warnings.append("Article 5's 2% RFNBO subtarget from 2034 is conditional. OPS is excluded from its energy basis. No RFNBO-specific banking/pooling or equivalent-fuel exemptions are assumed; GHG-intensity banks/pools never settle this separate MJ shortfall.")
    if any(v.gt <= 5000 for v in scenario.vessels):
        warnings.append("FuelEU requires ships above 5,000 GT; ETS cargo/passenger coverage starts at 5,000 GT. Ships below these thresholds are not priced under the respective regime.")
    if any("HSFO" in {entry["fuel"] for entry in v.consumption_entries()} | {v.alternative} for v in scenario.vessels):
        warnings.append("HSFO requires a lawful sulphur-compliance arrangement; scrubber cost/operability and local discharge restrictions are not automatically assessed.")
    if any(not v.compatible for v in scenario.vessels):
        warnings.append("Alternative fuel switching is disabled for vessels without confirmed engine, fuel-system and operational compatibility.")
    if any(not f.available_for_use for f in scenario.fuels if f.renewable):
        warnings.append("Renewable fuels without eligibility/evidence are excluded from switching. Illustrative WtW values are not supplier certificates.")
    if any(f.rfnbo for f in scenario.fuels if any(f.code in {entry["fuel"] for entry in v.consumption_entries()} | {v.alternative} for v in scenario.vessels)):
        warnings.append("RFNBOs require certified production/lifecycle evidence, including applicable RED and delegated-act criteria. Where enabled for the fuel, the elective reward is 2 in the intensity denominator through 2033 and 1 thereafter; physical compliance-balance energy is not doubled. The reward setting is fixed, not optimized. ETS CO2 zero-rating is a separate user assertion and does not remove CH4/N2O.")
    if any(f.pathway == "methane" for f in scenario.fuels if any(f.code in {entry["fuel"] for entry in v.consumption_entries()} | {v.alternative} for v in scenario.vessels)):
        warnings.append("LNG, bio-LNG and e-LNG use the selected engine's Annex II default methane slip, with the combusted fraction reduced accordingly. This annual model uses separate current sea, berth and alternative methane consumer classes per vessel; mixed engines, load-dependent or measured slip, additional venting and boil-off require a separate assessment.")
    warnings.append("One alternative system is evaluated per vessel per case. The overall replacement limit applies to total baseline sea service demand, not separately to each fuel. Each current fuel can have a different replacement fraction, applied proportionally across all its sea legs; the alternative inherits the coverage of the actual displaced energy. Individual legs are not optimized. Actual alternative energy uses the entered system-energy ratio and MGO pilot fraction. Current pilot in the consumption table, and legacy separate MGO pilot, are included once in their current-fuel demand. Berth fuel is unchanged by sea-fuel switching; only eligible EU berth fuel is replaced by shore power. Enter conversion, downtime and incremental annual costs; compare separate cases for other technologies.")
    warnings.append("First-step comparisons cover all current source fuels except the alternative itself, using equal original sea-energy steps and full-horizon fleet present cost with other ships and shore power held at the selected strategy. Replacement priority ranks the fuels selected for reduction. The final quantities are optimized together; priority is not a year-by-year switching schedule. Ties use fuel code order. Price sensitivities retain the saved per-fuel allocations.")
    warnings.append("Administrative, hedging, financing, charter-party allocation and unmodelled operating costs must be added to the annual other-cost assumption where relevant.")
    sensitivities = []
    alternative_codes = {v.alternative for v in scenario.vessels}
    for label, changed in [("EUA −20%", replace(scenario, eua_price=scenario.eua_price * .8)), ("EUA +20%", replace(scenario, eua_price=scenario.eua_price * 1.2)), ("Pool price +20%", replace(scenario, pool_price=scenario.pool_price * 1.2)), ("Alternative fuel +20%", replace(scenario, fuels=[replace(f, price=f.price * 1.2) if f.code in alternative_codes else f for f in scenario.fuels]))]:
        values = []
        for strategy in strategies:
            decisions = [(d["blend"], d["ops"], tuple(sorted(d["replacements"].items()))) for d in strategy["decisions"]]
            result = simulate(changed, decisions, strategy["use_pool"])
            if result:
                values.append((result["npv"], strategy["name"]))
        winner = min(values)
        sensitivities.append({"assumption": label, "npv": winner[0], "winner": winner[1]})
    return {"strategies": strategies, "best_key": strategies[0]["key"], "baseline_npv": baseline["npv"], "warnings": warnings, "sensitivities": sensitivities,
            "fuel_choice_notices": fuel_choice_notices(scenario),
            "horizon": f"{scenario.start_year}–{scenario.end_year}", "vessel_count": len(scenario.vessels), "coverage_limits": coverage_limits, "sources": [dict(s) for s in SOURCES], "checked_on": CHECKED_ON}
