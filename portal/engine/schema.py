"""Typed input contract shared by forms, saved scenarios and exports."""
from dataclasses import dataclass, field, fields, asdict
from math import isfinite, fsum
from .rules import LNG_CONSUMERS, FUELEU_GWP_CH4, FUELEU_GWP_N2O


def bounded(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be a finite number between {low:g} and {high:g}.")


def text_value(value, name, limit=300, required=True):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f"{name} must be text of 1–{limit} characters.")


@dataclass
class Fuel:
    code: str
    name: str
    lcv: float
    wtw: float | None
    co2: float
    ch4: float | None
    n2o: float | None
    price: float
    renewable: bool = False
    eligible: bool = False
    evidence: str = ""
    supply_t: float | None = None
    pathway: str = "oil"
    rfnbo: bool = False
    wtt: float | None = None
    ets_eligible: bool | None = None  # None preserves the old combined oil/bio assertion.
    factors_confirmed: bool = False
    reward_enabled: bool = True

    @property
    def measured_factors_required(self):
        return self.pathway in ("methanol", "ammonia", "hydrogen_ice")

    @property
    def ets_zero_rated(self):
        return self.renewable and (self.eligible if self.ets_eligible is None and not self.rfnbo else self.ets_eligible is True)

    @property
    def available_for_use(self):
        return (not self.renewable or self.eligible) and (not self.measured_factors_required or self.factors_confirmed)

    def validate(self):
        text_value(self.code, "Fuel code", 30)
        text_value(self.name, "Fuel name", 100)
        for name, low, high in [("lcv", 1000, 150000), ("co2", 0, 10), ("price", 0, 50000)]:
            bounded(getattr(self, name), f"{self.code} {name}", low, high)
        if self.wtw is not None or not (self.rfnbo or self.pathway == "methane"):
            bounded(self.wtw, f"{self.code} WtW", -100, 500)
        for name in ("ch4", "n2o"):
            if getattr(self, name) is not None or not self.measured_factors_required:
                bounded(getattr(self, name), f"{self.code} {name}", 0, 1)
        if any(type(getattr(self, name)) is not bool for name in ("renewable", "eligible", "rfnbo", "factors_confirmed", "reward_enabled")) or (self.ets_eligible is not None and type(self.ets_eligible) is not bool):
            raise ValueError("Fuel eligibility must be a boolean.")
        if self.pathway not in ("oil", "methane", "methanol", "ammonia", "hydrogen_cell", "hydrogen_ice"):
            raise ValueError("Unsupported fuel consumer pathway.")
        if self.rfnbo and not self.renewable:
            raise ValueError("An RFNBO must be a renewable pathway.")
        text_value(self.evidence, "Fuel evidence", 1000, False)
        if (self.eligible or self.ets_eligible) and (not self.renewable or not self.evidence.strip()):
            raise ValueError("Renewable fuel eligibility requires an evidence reference.")
        if self.wtt is not None:
            bounded(self.wtt, f"{self.code} WtT", -200, 500)
        if (self.rfnbo or self.pathway == "methane") and (self.eligible or not self.renewable) and self.wtt is None:
            raise ValueError(f"{self.code}: enter the certified FuelEU WtT pathway factor before enabling this fuel.")
        if self.measured_factors_required and (self.eligible or self.factors_confirmed):
            if not self.factors_confirmed or self.ch4 is None or self.n2o is None or not self.evidence.strip():
                raise ValueError(f"{self.code}: measured CH4/N2O factors and their evidence are required; missing factors cannot be treated as zero.")
        if self.code == "LNG" and (self.pathway != "methane" or self.renewable or self.wtt != 18.5):
            raise ValueError("Fossil LNG uses the Annex II WtT default of 18.5 gCO2e/MJ.")
        if self.pathway == "methane" and (self.co2 != 2.75 or self.ch4 != 0 or self.n2o != .00011 or self.lcv != 49100):
            raise ValueError("Methane pathways use Annex II factors: LCV 49,100, CO2 2.75, combustion CH4 0 and N2O 0.00011. Slip is determined per vessel.")
        if self.pathway == "hydrogen_cell" and (self.co2 or self.ch4 or self.n2o):
            raise ValueError("The hydrogen fuel-cell pathway has zero direct CO2, CH4 and N2O factors.")
        if not self.renewable and self.pathway != "methane":
            combustion_g = (self.co2 + self.ch4 * FUELEU_GWP_CH4 + self.n2o * FUELEU_GWP_N2O) * 1e6 / self.lcv
            if self.co2 <= 0 or self.wtw < combustion_g - 1e-8:
                raise ValueError(f"{self.code}: the fossil pathway needs positive CO2 and WtW at least as high as its combustion intensity. Review the factors together.")
        if self.supply_t is not None:
            bounded(self.supply_t, "Annual fleet fuel supply", 0, 10_000_000)


@dataclass
class Vessel:
    name: str = "New vessel"
    imo: str = ""
    ship_type: str = "cargo"
    gt: int = 25000
    fuel: str = "VLSFO"
    sea_t: float = 4000
    berth_t: float = 150
    intra_share: float = .3
    extra_share: float = .6
    alternative: str = "HVO"
    max_blend: float = .3
    compatible: bool = False
    opening_bank: float = 0
    prior_penalties: int = 0
    ops_ready: bool = False
    ops_fraction: float = 1
    generator_efficiency: float = .4
    ops_efficiency: float = .95
    ops_capex: float = 0
    ops_annual: float = 0
    fuel_consumer: str = ""
    alternative_consumer: str = ""
    pilot_t: float = 0
    alternative_pilot_share: float = 0
    alternative_energy_ratio: float = 1
    fuel_capex: float = 0
    fuel_annual: float = 0
    fuel_systems_confirmed: bool = False
    technical_reference: str = ""
    sea_fuels: list[dict] = field(default_factory=list)
    consumption: list[dict] | None = None
    berth_consumer: str = ""
    wind_mode: str = "none"  # none, retrofit, existing (consumption already net)
    wind_capex: float = 0
    wind_annual: float = 0
    wind_reference: str = ""
    wind_confirmed: bool = False
    wind_reward: bool = False
    wind_power_kw: float = 0
    wind_propulsion_kw: float = 0
    wind_reward_reference: str = ""

    def consumption_entries(self):
        """Annual tonnes by operating category, including existing pilot fuel."""
        if self.consumption is not None:
            return [dict(entry) for entry in self.consumption]
        rows = {}
        def add(code, **quantities):
            row = rows.setdefault(code, dict(fuel=code, intra_t=0, extra_t=0, outside_t=0, eu_berth_t=0, non_eu_berth_t=0))
            for key, value in quantities.items():
                row[key] += value
        for entry in self.sea_fuel_entries():
            tonnes = entry["sea_t"]
            intra, extra = entry["intra_share"], entry["extra_share"]
            add(entry["fuel"], intra_t=tonnes * intra, extra_t=tonnes * extra,
                outside_t=tonnes * max(0, 1 - intra - extra))
        if self.pilot_t or self.berth_t:
            add("MGO", intra_t=self.pilot_t * self.intra_share, extra_t=self.pilot_t * self.extra_share,
                outside_t=self.pilot_t * max(0, 1-self.intra_share-self.extra_share), eu_berth_t=self.berth_t)
        return list(rows.values())

    def berth_fuel_entries(self):
        if self.consumption is None:
            return [dict(fuel="MGO", eu_berth_t=self.berth_t, non_eu_berth_t=0)]
        return [dict(voyage=entry.get("voyage", 1), fuel=entry["fuel"], eu_berth_t=entry.get("eu_berth_t", 0),
                     non_eu_berth_t=entry.get("non_eu_berth_t", 0), ops_share=entry.get("ops_share", self.ops_fraction))
                for entry in self.consumption if entry.get("eu_berth_t", 0) or entry.get("non_eu_berth_t", 0)]

    @property
    def current_pilot_t(self):
        return self.pilot_t if self.consumption is None else 0

    @property
    def total_eu_berth_t(self):
        return fsum(entry["eu_berth_t"] for entry in self.berth_fuel_entries())

    @property
    def total_non_eu_berth_t(self):
        return fsum(entry["non_eu_berth_t"] for entry in self.berth_fuel_entries())

    def sea_fuel_entries(self):
        """Resolve saved fuel rows; an absent mix preserves legacy single-fuel cases."""
        if self.consumption is not None:
            entries = []
            for row in self.consumption:
                tonnes = fsum(row.get(key, 0) for key in ("intra_t", "extra_t", "outside_t"))
                if tonnes:
                    entries.append(dict(voyage=row.get("voyage", 1), fuel=row["fuel"], sea_t=tonnes,
                                        intra_share=row.get("intra_t", 0)/tonnes, extra_share=row.get("extra_t", 0)/tonnes))
            return entries
        entries = self.sea_fuels or [{"fuel": self.fuel, "sea_t": self.sea_t}]
        return [dict(entry, intra_share=entry.get("intra_share", self.intra_share),
                     extra_share=entry.get("extra_share", self.extra_share)) for entry in entries]

    @property
    def total_sea_t(self):
        return fsum(entry["sea_t"] for entry in self.sea_fuel_entries())

    def validate(self, fuels):
        from .wind import validate_wind
        validate_wind(self)
        text_value(self.name, "Vessel name", 100)
        text_value(self.imo, "IMO number", 7, False)
        if self.imo and (not self.imo.isascii() or not self.imo.isdigit() or len(self.imo) != 7 or sum(int(c) * w for c, w in zip(self.imo[:6], range(7, 1, -1))) % 10 != int(self.imo[-1])):
            raise ValueError(f"{self.name}: invalid IMO number or check digit.")
        if self.ship_type not in ("cargo", "tanker", "container", "passenger"):
            raise ValueError("Supported ships: cargo, tanker, container and passenger.")
        if type(self.gt) is not int or not 1 <= self.gt <= 1_000_000:
            raise ValueError("Gross tonnage must be a positive integer.")
        if (self.consumption is None and self.fuel not in fuels) or self.alternative not in fuels:
            raise ValueError("Choose fuels from this case's fuel library.")
        if self.consumption is not None:
            if not isinstance(self.consumption, list) or not 1 <= len(self.consumption) <= 100:
                raise ValueError("Enter 1–100 voyage/fuel groups in the consumption table.")
            seen_consumption = set()
            for entry in self.consumption:
                quantity_keys = ("intra_t", "extra_t", "outside_t", "eu_berth_t", "non_eu_berth_t")
                if not isinstance(entry, dict) or "fuel" not in entry or set(entry) - {"voyage", "fuel", "ops_share", "wind", *quantity_keys}:
                    raise ValueError("Each consumption row needs a fuel and tonnes by operating category.")
                code = entry["fuel"]
                if not isinstance(code, str) or code not in fuels:
                    raise ValueError("Choose each consumption fuel from this case's fuel library.")
                voyage = entry.get("voyage", 1)
                if type(voyage) is not int or not 1 <= voyage <= 100:
                    raise ValueError("Choose a voyage number from 1 to 100.")
                if (voyage, code) in seen_consumption:
                    raise ValueError(f"Combine {code} consumption within Voyage {voyage} into one group.")
                seen_consumption.add((voyage, code))
                for key in quantity_keys:
                    bounded(entry.get(key, 0), f"{code} {key}", 0, 10_000_000)
                if "ops_share" in entry:
                    bounded(entry["ops_share"], f"{code} EU berth share replaceable by shore power", 0, 1)
        if not isinstance(self.sea_fuels, list) or len(self.sea_fuels) > 20:
            raise ValueError("Enter at most 20 sea-fuel rows per vessel.")
        seen = set()
        for entry in self.sea_fuels:
            if not isinstance(entry, dict) or set(entry) - {"fuel", "sea_t", "intra_share", "extra_share"} or not {"fuel", "sea_t"} <= set(entry):
                raise ValueError("Each sea-fuel row needs a fuel and annual tonnes, with optional voyage shares.")
            code = entry["fuel"]
            if not isinstance(code, str) or code not in fuels:
                raise ValueError("Choose each sea fuel from this case's fuel library.")
            if code in seen:
                raise ValueError(f"{self.name}: combine {code} consumption into one sea-fuel row.")
            seen.add(code)
            bounded(entry["sea_t"], f"{self.name} {code} annual tonnes", 0, 10_000_000)
            intra = entry.get("intra_share", self.intra_share)
            extra = entry.get("extra_share", self.extra_share)
            bounded(intra, f"{code} intra-EU share", 0, 1)
            bounded(extra, f"{code} extra-EU share", 0, 1)
            if intra + extra > 1 + 1e-10:
                raise ValueError(f"{code}: intra-EU and extra-EU fuel shares cannot exceed 100%.")
        for consumer in (self.fuel_consumer, self.alternative_consumer, self.berth_consumer):
            if consumer and consumer not in LNG_CONSUMERS:
                raise ValueError("Choose a supported LNG consumer class.")
        text_value(self.technical_reference, "Technical review reference", 1000, False)
        if type(self.fuel_systems_confirmed) is not bool:
            raise ValueError("Fuel-system review must be boolean.")
        for name in ("sea_t", "berth_t", "opening_bank", "ops_capex", "ops_annual", "pilot_t", "fuel_capex", "fuel_annual"):
            bounded(getattr(self, name), f"{self.name} {name}", 0, 100_000_000)
        for name in ("intra_share", "extra_share", "max_blend", "ops_fraction"):
            bounded(getattr(self, name), name, 0, 1)
        bounded(self.alternative_pilot_share, "Alternative pilot energy share", 0, .5)
        bounded(self.alternative_energy_ratio, "Alternative system energy ratio", .25, 4)
        if self.intra_share + self.extra_share > 1 + 1e-10:
            raise ValueError("Intra-EU and extra-EU voyage fuel shares cannot exceed 100%.")
        for name in ("generator_efficiency", "ops_efficiency"):
            bounded(getattr(self, name), name, .05, 1)
        if type(self.prior_penalties) is not int or not 0 <= self.prior_penalties <= 25:
            raise ValueError("Previous consecutive penalty years must be an integer from 0 to 25.")
        if type(self.compatible) is not bool or type(self.ops_ready) is not bool:
            raise ValueError("Technical readiness must be boolean.")
        if self.total_sea_t + self.total_eu_berth_t + self.total_non_eu_berth_t + self.current_pilot_t <= 0:
            raise ValueError(f"{self.name}: enter annual fuel consumption.")
        if self.gt <= 5000 and (self.opening_bank or self.prior_penalties):
            raise ValueError("FuelEU bank and penalty history require a ship above 5,000 GT.")

    def validate_for_run(self, fuels):
        current = [(entry["fuel"], self.fuel_consumer, entry["sea_t"] > 0) for entry in self.sea_fuel_entries()]
        current += [(entry["fuel"], self.berth_consumer, entry["eu_berth_t"] + entry["non_eu_berth_t"] > 0) for entry in self.berth_fuel_entries()]
        for code, consumer, used in current + [(self.alternative, self.alternative_consumer, self.compatible and self.max_blend > 0)]:
            fuel = fuels[code]
            if not used:
                continue
            if fuel.pathway == "methane" and not consumer:
                raise ValueError(f"{self.name}: select the LNG consumer class for {code}; methane slip cannot be inferred from the fuel name.")
            if fuel.pathway != "oil" and (not self.fuel_systems_confirmed or not self.technical_reference.strip()):
                raise ValueError(f"{self.name}: record the fuel-system, pilot-fuel, efficiency and investment review for {code}.")
        for code, _, used in current:
            if used and not fuels[code].available_for_use:
                raise ValueError(f"{self.name}: current fuel {code} requires FuelEU eligibility and complete pathway evidence before comparison.")


def default_fuels():
    # Oil-engine Annex II example pathways. Supplier BDN/monitoring plan overrides matter.
    def oil_wtw(lcv, co2, wtt):
        return wtt + (co2 + .00005 * FUELEU_GWP_CH4 + .00018 * FUELEU_GWP_N2O) * 1e6 / lcv
    return [Fuel("HSFO", "HSFO · residual oil", 40500, oil_wtw(40500, 3.114, 13.5), 3.114, .00005, .00018, 470),
            Fuel("VLSFO", "VLSFO · residual oil assumption", 40500, oil_wtw(40500, 3.114, 13.5), 3.114, .00005, .00018, 575),
            Fuel("MGO", "Marine gas oil", 42700, oil_wtw(42700, 3.206, 14.4), 3.206, .00005, .00018, 720),
            Fuel("HVO", "HVO · supplier pathway required", 44000, 20, 3.114, .00005, .00018, 1550, renewable=True),
            Fuel("FAME", "FAME · non-food/feed pathway required", 37000, 25, 2.834, .00005, .00018, 1150, renewable=True),
            Fuel("LNG", "LNG · select engine on vessel", 49100, None, 2.75, 0, .00011, 700, pathway="methane", wtt=18.5),
            Fuel("LBM", "Bio-LNG / liquefied biomethane", 49100, None, 2.75, 0, .00011, 1400, renewable=True, pathway="methane", ets_eligible=False),
            Fuel("E_LNG", "RFNBO · e-LNG", 49100, None, 2.75, 0, .00011, 2400, renewable=True, pathway="methane", rfnbo=True, ets_eligible=False),
            Fuel("E_METHANOL", "RFNBO · e-methanol · combustion", 19900, None, 1.375, None, None, 1600, renewable=True, pathway="methanol", rfnbo=True, ets_eligible=False),
            Fuel("E_AMMONIA", "RFNBO · e-ammonia · combustion", 18600, None, 0, None, None, 1400, renewable=True, pathway="ammonia", rfnbo=True, ets_eligible=False),
            Fuel("E_HYDROGEN", "RFNBO · hydrogen · fuel cell", 120000, None, 0, 0, 0, 6000, renewable=True, pathway="hydrogen_cell", rfnbo=True, ets_eligible=False),
            Fuel("E_HYDROGEN_ICE", "RFNBO · hydrogen · combustion", 120000, None, 0, 0, None, 6000, renewable=True, pathway="hydrogen_ice", rfnbo=True, ets_eligible=False),
            Fuel("E_DIESEL", "RFNBO · e-diesel", 42700, None, 3.206, .00005, .00018, 2500, renewable=True, rfnbo=True, ets_eligible=False)]


@dataclass
class ScenarioInput:
    start_year: int = 2026
    end_year: int = 2030
    eua_price: float = 90
    eua_escalation: float = .03
    fuel_escalation: float = .02
    discount_rate: float = .07
    pool_enabled: bool = False
    pool_price: float = 250
    pool_cap: float = 10000
    pool_reference: str = ""
    electricity_price: float = 160
    other_annual_cost: float = 0
    scope_confirmed: bool = False
    scope_notes: str = ""
    rfnbo_subtarget: str = "unresolved"
    rfnbo_penalty_pd: float | None = None
    rfnbo_reference: str = ""
    fuels: list[Fuel] = field(default_factory=default_fuels)
    vessels: list[Vessel] = field(default_factory=list)

    def validate(self, for_run=True):
        if type(self.start_year) is not int or type(self.end_year) is not int or not 2025 <= self.start_year <= self.end_year <= 2050:
            raise ValueError("Choose an ordered reporting-year range within 2025–2050.")
        for name in ("eua_price", "pool_price", "electricity_price"):
            bounded(getattr(self, name), name, 0, 50000)
        bounded(self.pool_cap, "Annual external pool capacity", 0, 10_000_000)
        bounded(self.other_annual_cost, "Other annual costs", 0, 100_000_000)
        for name in ("eua_escalation", "fuel_escalation"):
            bounded(getattr(self, name), name, -.5, 1)
        bounded(self.discount_rate, "Discount rate", 0, 1)
        for name in ("pool_enabled", "scope_confirmed"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be boolean.")
        text_value(self.pool_reference, "Pool reference", 1000, False)
        text_value(self.scope_notes, "Scope notes", 2000, False)
        if self.rfnbo_subtarget not in ("unresolved", "assume_active", "assume_inactive"):
            raise ValueError("Choose an RFNBO subtarget planning assumption.")
        text_value(self.rfnbo_reference, "RFNBO subtarget reference", 1000, False)
        if self.rfnbo_penalty_pd is not None:
            bounded(self.rfnbo_penalty_pd, "RFNBO penalty price-difference assumption", 0, 100000)
        if for_run and self.end_year >= 2034 and self.rfnbo_subtarget != "unresolved":
            if not self.rfnbo_reference.strip() or (self.rfnbo_subtarget == "assume_active" and self.rfnbo_penalty_pd is None):
                raise ValueError("Record the future RFNBO subtarget assumption and, if active, its penalty price-difference factor.")
        if self.pool_enabled and not self.pool_reference.strip():
            raise ValueError("Enter the pool quotation or planning-assumption reference.")
        if for_run and not self.scope_confirmed:
            raise ValueError("Confirm voyage scope before running a comparison.")
        if not 1 <= len(self.fuels) <= 20 or len(self.vessels) > 20 or (for_run and not self.vessels):
            raise ValueError("A calculation needs 1–20 vessels and 1–20 fuels.")
        lookup = {f.code: f for f in self.fuels}
        if len(lookup) != len(self.fuels) or "MGO" not in lookup:
            raise ValueError("Fuel codes must be unique and include MGO for the alternative-system pilot reference.")
        if lookup["MGO"].renewable or lookup["MGO"].rfnbo or lookup["MGO"].pathway != "oil":
            raise ValueError("The MGO pilot reference must remain a fossil-oil pathway.")
        for fuel in self.fuels:
            fuel.validate()
        names = set()
        imos = set()
        for vessel in self.vessels:
            vessel.validate(lookup)
            if for_run:
                vessel.validate_for_run(lookup)
            if vessel.name.casefold() in names or (vessel.imo and vessel.imo in imos):
                raise ValueError("Vessel names and non-empty IMO numbers must be unique.")
            names.add(vessel.name.casefold())
            imos.add(vessel.imo)
        if any(v.prior_penalties > self.start_year - 2025 for v in self.vessels):
            raise ValueError("Penalty history cannot predate FuelEU's first reporting year, 2025.")
        if self.start_year == 2025 and any(v.opening_bank for v in self.vessels):
            raise ValueError("There is no pre-2025 FuelEU bank.")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("Scenario must be an object.")
        def construct(kind, raw):
            if not isinstance(raw, dict) or set(raw) - {f.name for f in fields(kind)}:
                raise ValueError(f"Unexpected {kind.__name__} input fields.")
            try:
                return kind(**raw)
            except TypeError as exc:
                raise ValueError(f"Incomplete {kind.__name__} inputs.") from exc
        raw = dict(data)
        for key, kind in (("fuels", Fuel), ("vessels", Vessel)):
            if key in raw:
                if not isinstance(raw[key], list) or len(raw[key]) > 20:
                    raise ValueError(f"{key} must be a list with at most 20 entries.")
                raw[key] = [construct(kind, x) for x in raw[key]]
        return construct(cls, raw)
