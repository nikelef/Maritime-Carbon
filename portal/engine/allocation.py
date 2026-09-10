"""Annual FuelEU attribution, separate from physical consumption and ETS.

Commission FuelEU guidance (8 October 2025), section 4.4, pages 51–52.
The app elects lowest-WtW-first attribution within each ship/reporting year.
"""
from math import fsum


def prioritize_energy(sources, energy_scope):
    """Fill physical Article 2 energy from eligible sources in WtW order.

    Sources carry their full MRV-eligible energy, not their 50%-weighted energy.
    Separate consumer classes remain separate sources. Zero-quantity sources
    are retained to expose linear capacity boundaries to the optimizer.
    RFNBO reward is applied by the caller after physical attribution.
    """
    ordered = sorted(sources, key=lambda s: (s["wtw_g"], s["fuel"], s["consumer"], s["source_type"]))
    remaining = energy_scope
    result = []
    for source in ordered:
        allocated = min(source["available_energy_mj"], max(0.0, remaining))
        result.append(source | {"allocated_energy_mj": allocated})
        remaining -= allocated
    if remaining > max(1e-6, energy_scope * 1e-12):
        raise ValueError("FuelEU energy scope exceeds eligible annual energy.")
    return result


def allocation_breakpoints(left, right, low=0.0, high=1.0):
    """Exact capacity kinks along a linear change in physical fuel demand."""
    a = left["fueleu_allocation"]
    b = right["fueleu_allocation"]
    # Sources, including zero capacities, must have stable identities/order.
    if [(s["fuel"], s["consumer"], s["source_type"]) for s in a] != [(s["fuel"], s["consumer"], s["source_type"]) for s in b]:
        raise ValueError("FuelEU allocation sources changed during line search.")
    points = set()
    for end in range(1, len(a) + 1):
        x = fsum(s["available_energy_mj"] for s in a[:end]) - left["energy_mj"]
        y = fsum(s["available_energy_mj"] for s in b[:end]) - right["energy_mj"]
        if abs(y - x) > 1e-12:
            t = -x / (y - x)
            if low < t < high:
                points.add(t)
    return points
