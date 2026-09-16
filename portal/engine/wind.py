"""Wind input validation and physical demand adjustments, independent of fuel choice.

Savings are net of WAPS auxiliary consumption, expressed in each source fuel.
They are supplied by a reviewed performance assessment, not inferred from the
FuelEU design-power ratio. Retrofit operation starts at the horizon's beginning.
"""
from .schema import bounded, text_value

SEA_LEGS = ("intra_t", "extra_t", "outside_t")


def validate_wind(vessel):
    if vessel.wind_mode not in ("none", "retrofit", "existing"):
        raise ValueError("Choose no wind, a proposed retrofit, or existing wind assistance.")
    for name in ("wind_confirmed", "wind_reward"):
        if type(getattr(vessel, name)) is not bool:
            raise ValueError("Wind review and reward settings must be boolean.")
    for name in ("wind_capex", "wind_annual", "wind_power_kw", "wind_propulsion_kw"):
        bounded(getattr(vessel, name), name, 0, 100_000_000)
    for name in ("wind_reference", "wind_reward_reference"):
        text_value(getattr(vessel, name), name, 1000, False)
    if vessel.wind_mode != "none" and (not vessel.wind_confirmed or not vessel.wind_reference.strip()):
        raise ValueError("Wind assistance requires a reviewed baseline, performance and equipment-cost reference.")
    if vessel.wind_mode != "retrofit" and vessel.wind_capex:
        raise ValueError("Enter new wind investment only for a proposed retrofit; existing capital is sunk.")
    if vessel.wind_mode == "none" and (vessel.wind_reward or vessel.wind_annual):
        raise ValueError("Wind reward and operating costs require a wind installation or proposed retrofit.")
    if vessel.wind_reward:
        if vessel.wind_propulsion_kw <= 0 or vessel.wind_power_kw <= 0 or not vessel.wind_reward_reference.strip():
            raise ValueError("FuelEU wind reward requires positive Pwind/Pprop and an EEDI/EEXI or recognised-body review reference.")
    if vessel.wind_mode == "retrofit" and vessel.consumption is None:
        raise ValueError("Use the consumption table and review propulsion shares before evaluating a wind retrofit.")
    for row in vessel.consumption if isinstance(vessel.consumption, list) else []:
        if not isinstance(row, dict):
            continue  # The consumption contract reports malformed rows.
        settings = row.get("wind", {})
        if not isinstance(settings, dict) or set(settings) - set(SEA_LEGS):
            raise ValueError("Wind performance can be specified only on sea legs.")
        for leg, item in settings.items():
            if not isinstance(item, dict) or set(item) != {"propulsion_share", "net_saving"}:
                raise ValueError("Each wind sea-leg input needs propulsion_share and net_saving.")
            bounded(item["propulsion_share"], "Propulsion share", 0, 1)
            bounded(item["net_saving"], "Net propulsion fuel saving", 0, .99)
            if vessel.wind_mode == "existing" and item["net_saving"]:
                raise ValueError("Existing wind consumption is already net: clear proposed wind savings to avoid counting them twice.")
        if vessel.wind_mode == "retrofit":
            for leg in SEA_LEGS:
                if row.get(leg, 0) and leg not in settings:
                    raise ValueError(f"{vessel.name}: enter propulsion share and net wind saving for every sea row (zero is allowed).")


def wind_choices(vessel):
    return (False, True) if vessel.wind_mode == "retrofit" else (False,)


def adjusted_legs(vessel, legs, selected):
    """Keep decision weights on original demand; adjust actual fuel quantities."""
    lookup = {(r.get("voyage", 1), r["fuel"]): r.get("wind", {})
              for r in vessel.consumption or []}
    result = {}
    for key, demand in legs.items():
        inputs = lookup.get((demand["voyage"], demand["fuel"]), {}).get(demand["leg"], {})
        saving = (inputs.get("propulsion_share", 0) * inputs.get("net_saving", 0)
                  if selected and vessel.wind_mode == "retrofit" else 0)
        result[key] = demand | {
            "original_t": demand["tonnes"], "wind_saved_t": demand["tonnes"] * saving,
            "tonnes": demand["tonnes"] * (1-saving), "energy": demand["energy"] * (1-saving),
        }
    return result
