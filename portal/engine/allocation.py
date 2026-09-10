"""Annual FuelEU attribution, separate from physical consumption and ETS.

Commission FuelEU guidance (8 October 2025), section 4.4, pages 51–52.
The app minimizes annual attained intensity including any elected RFNBO reward.
"""
from math import fsum


def _identity(source):
    return source["fuel"], source["consumer"], source["source_type"]


def _fill(ordered, energy_scope):
    remaining = energy_scope
    result = []
    for source in ordered:
        allocated = min(source["available_energy_mj"], max(0.0, remaining))
        result.append(source | {"allocated_energy_mj": allocated})
        remaining -= allocated
    if remaining > max(1e-6, energy_scope * 1e-12):
        raise ValueError("FuelEU energy scope exceeds eligible annual energy.")
    return result


def _intensity(allocation):
    denominator = fsum(s["allocated_energy_mj"] * s["reward_multiplier"] for s in allocation)
    return (fsum(s["allocated_energy_mj"] * s["wtw_g"] for s in allocation)
            / denominator if denominator else 0.0)


def _order(sources, intensity):
    return sorted(sources, key=lambda s: (
        s["wtw_g"] - intensity * (s["reward_multiplier"] - 1),
        s["wtw_g"], *_identity(s)))


def prioritize_energy(sources, energy_scope, reward=1.0):
    """Minimize N / (E + sum((reward_i-1)*x_i)) with sum(x_i)=E.

    Sources carry their full MRV-eligible energy, not their 50%-weighted energy.
    Separate consumer classes remain separate sources. Zero-quantity sources
    are retained for audit and line-search identities. Dinkelbach iteration
    solves the positive-denominator linear-fractional allocation: at intensity
    q, fill the bounded inventory by g_i-q*(reward_i-1). With no reward this
    reduces to lowest physical WtW first. This is not sorting by g_i/reward_i.
    The reward election itself stays a fixed user input. Physical MJ, ETS and
    purchases are never multiplied. Negative WtW and zero OPS are supported.
    """
    sources = [s | {"reward_multiplier": reward if s.get("reward_enabled") else 1.0}
               for s in sources]
    intensity = 0.0
    for _ in range(len(sources)**2 + 2):
        result = _fill(_order(sources, intensity), energy_scope)
        updated = _intensity(result)
        if abs(updated-intensity) <= 1e-12 * max(1.0, abs(updated)):
            return result
        intensity = updated
    raise ValueError("FuelEU reward-aware allocation did not converge.")


def allocation_breakpoints(left, right, low=0.0, high=1.0):
    """Capacity and reward-order boundaries along affine physical demand.

    Source order may differ at the endpoints. Enumerate the possible score
    orders between pairwise intensity crossings, retain capacity roots active
    at their optimal intensity, and solve F(q,t)=N-q*D=0 at each order crossing.
    F is piecewise affine at fixed q, so those roots are exact up to rounding.
    """
    a = {_identity(s): s for s in left["fueleu_allocation"]}
    b = {_identity(s): s for s in right["fueleu_allocation"]}
    if a.keys() != b.keys():
        raise ValueError("FuelEU allocation sources changed during line search.")
    keys = [k for k in sorted(a) if a[k]["available_energy_mj"] or b[k]["available_energy_mj"]]
    if not keys:
        return set()
    for k in keys:
        if (a[k]["wtw_g"], a[k]["reward_multiplier"]) != (b[k]["wtw_g"], b[k]["reward_multiplier"]):
            raise ValueError("FuelEU source factors changed during line search.")

    def energy(t):
        return left["energy_mj"] + t*(right["energy_mj"]-left["energy_mj"])

    def sources_at(t):
        return [a[k] | {"available_energy_mj": max(0.0, a[k]["available_energy_mj"]
                    + t*(b[k]["available_energy_mj"]-a[k]["available_energy_mj"]))} for k in keys]

    def capacities(order):
        roots = []
        for end in range(1, len(order)):
            prefix = order[:end]
            x = fsum(a[k]["available_energy_mj"] for k in prefix)-left["energy_mj"]
            y = fsum(b[k]["available_energy_mj"] for k in prefix)-right["energy_mj"]
            if abs(y-x) > 1e-12:
                t = -x/(y-x)
                if low < t < high:
                    roots.append((t, end))
        return roots

    sources = [a[k] for k in keys]
    lower = min(s["wtw_g"]/s["reward_multiplier"] for s in sources)
    upper = max(s["wtw_g"]/s["reward_multiplier"] for s in sources)
    crossings = set()
    for i, s in enumerate(sources):
        for other in sources[i+1:]:
            delta = s["reward_multiplier"]-other["reward_multiplier"]
            if delta:
                q = (s["wtw_g"]-other["wtw_g"])/delta
                if lower <= q <= upper:
                    crossings.add(q)
    bounds = sorted({lower, upper} | crossings)
    probes = bounds + [(x+y)/2 for x,y in zip(bounds, bounds[1:])]
    orders = {tuple(_identity(s) for s in _order(sources, q)) for q in probes}
    points = set()
    reward = max(s["reward_multiplier"] for s in sources)
    for order in orders:
        for t, end in capacities(order):
            q = _intensity(prioritize_energy(sources_at(t), energy(t), reward))
            scores = [a[k]["wtw_g"]-q*(a[k]["reward_multiplier"]-1) for k in order]
            if max(scores[:end]) <= min(scores[end:]) + 1e-10:
                points.add(t)
    for q in crossings:
        order = tuple(_identity(s) for s in _order(sources, q))
        segments = sorted({low, high} | {t for t,_ in capacities(order)})
        def residual(t):
            inventory = {_identity(s): s for s in sources_at(t)}
            allocation = _fill([inventory[k] for k in order], energy(t))
            return fsum(s["allocated_energy_mj"]*(s["wtw_g"]-q*s["reward_multiplier"])
                        for s in allocation)
        for start, end in zip(segments, segments[1:]):
            x, y = residual(start), residual(end)
            if x*y < 0:
                points.add(start-x*(end-start)/(y-x))
            elif x == 0 and low < start < high:
                points.add(start)
            elif y == 0 and low < end < high:
                points.add(end)
    return points
