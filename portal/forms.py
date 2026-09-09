from dataclasses import asdict
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .engine.schema import ScenarioInput, Vessel
from .engine.rules import LNG_CONSUMERS
from .models import Membership


class StyledForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "input"
            if isinstance(field, forms.FloatField):
                field.widget.attrs["step"] = "any"


class ScenarioForm(StyledForm):
    name = forms.CharField(max_length=140, label="Decision case name")
    revision = forms.IntegerField(widget=forms.HiddenInput, required=False)
    start_year = forms.IntegerField(min_value=2025, max_value=2050, label="First reporting year")
    end_year = forms.IntegerField(min_value=2025, max_value=2050, label="Last reporting year")
    eua_price = forms.FloatField(min_value=0, max_value=50000, label="EUA price · EUR/tCO₂e", help_text="Your budget or quoted allowance price; not a live price.")
    eua_escalation = forms.FloatField(min_value=-50, max_value=100, label="Annual EUA price change · %")
    fuel_escalation = forms.FloatField(min_value=-50, max_value=100, label="Annual fuel & electricity price change · %")
    discount_rate = forms.FloatField(min_value=0, max_value=100, label="Future cost discount rate · %", help_text="Gives future costs less weight when comparing strategies, using the first reporting year as the base. At 0%, costs in every year have equal weight. Price increases are set separately below.")
    pool_enabled = forms.BooleanField(required=False, label="Include external pooling offers")
    pool_price = forms.FloatField(min_value=0, max_value=50000, label="Pool purchase price · EUR/tCO₂e balance", help_text="Tonnes of FuelEU compliance balance, not tonnes of fuel or EUAs.")
    pool_cap = forms.FloatField(min_value=0, max_value=10000000, label="Available external surplus · tCO₂e/year", help_text="A shared annual fleet cap. Zero means no external capacity.")
    pool_reference = forms.CharField(max_length=1000, required=False, label="Pool offer / assumption reference", widget=forms.Textarea(attrs={"rows": 2}))
    electricity_price = forms.FloatField(min_value=0, max_value=50000, label="Shore electricity · EUR/MWh")
    other_annual_cost = forms.FloatField(min_value=0, max_value=100000000, label="Other fleet costs · EUR/year", help_text="Include verification, administration and other relevant costs. Applied to every option.")
    scope_confirmed = forms.BooleanField(required=False, label="I have checked that these ordinary EU voyage shares apply to both FuelEU and ETS")
    scope_notes = forms.CharField(max_length=2000, required=False, label="Scope and planning notes", widget=forms.Textarea(attrs={"rows": 3}), help_text="EU voyages only. EEA timing, special ports, exemptions and derogations require separate review.")
    rfnbo_subtarget = forms.ChoiceField(required=False, label="How to include this possible requirement", choices=[("unresolved", "Show potential shortfall only (default)"), ("assume_active", "Assume it applies: estimate extra cost"), ("assume_inactive", "Assume it does not apply: no extra cost")], help_text="The default adds no penalty for this requirement. Only 'Assume it applies' adds an estimated penalty using your cost assumption below. Reports can still show the potential shortfall in all three options.")
    rfnbo_penalty_pd = forms.FloatField(required=False, min_value=0, max_value=100000, label="Assumed shortfall cost · EUR per 41,000 MJ", help_text="Fill this in only for 'Assume it applies'. This is the price-difference factor (Pd): the model multiplies it by the missing e-fuel energy divided by 41,000 MJ, before any repeated-penalty increase. It is your planning assumption, not an official penalty rate or a price per tonne of fuel.")
    rfnbo_reference = forms.CharField(max_length=1000, required=False, label="Reason for your assumption / source", widget=forms.Textarea(attrs={"rows": 2}), help_text="For plans including 2034 or later, explain your choice if you assume the requirement applies or does not apply. If adding a cost, also record where your estimate comes from. Leave blank for the default option.")

    @staticmethod
    def initial_for(name, data, revision=None):
        initial = data.to_dict() | {"name": name, "revision": revision}
        initial["rfnbo_penalty_pd"] = data.rfnbo_penalty_pd if data.rfnbo_penalty_pd is not None else ""
        for key in ("eua_escalation", "fuel_escalation", "discount_rate"):
            initial[key] *= 100
        return initial

    def apply(self, data):
        for key in ScenarioInput.__dataclass_fields__:
            if key in self.cleaned_data:
                value = self.cleaned_data[key]
                if key == "rfnbo_subtarget" and not value:
                    value = "unresolved"
                setattr(data, key, value / 100 if key in ("eua_escalation", "fuel_escalation", "discount_rate") else value)
        data.validate(for_run=False)
        return data


def fuel_choices(fuels):
    return [(f.code, "MGO / LSMGO · marine gas oil" if f.code == "MGO" else f.name) for f in fuels]


class SeaFuelForm(StyledForm):
    fuel = forms.ChoiceField(label="Fuel type")
    sea_t = forms.FloatField(min_value=0, max_value=10000000, label="Annual consumption · tonnes")
    intra_share = forms.FloatField(required=False, min_value=0, max_value=100, label="Intra-EU voyages · %", help_text="Blank uses the default voyage mix below.")
    extra_share = forms.FloatField(required=False, min_value=0, max_value=100, label="EU ↔ non-EU voyages · %", help_text="Blank uses the default voyage mix below.")

    def __init__(self, *args, fuels, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fuel"].choices = [("", "Choose a fuel")] + fuel_choices(fuels)


class BaseSeaFuelFormSet(forms.BaseFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        seen = set()
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            code = form.cleaned_data["fuel"]
            if code in seen:
                raise forms.ValidationError(f"Combine {code} consumption into one row.")
            seen.add(code)


SeaFuelFormSet = forms.formset_factory(SeaFuelForm, formset=BaseSeaFuelFormSet, extra=0,
                                      can_delete=True, min_num=1, validate_min=True,
                                      max_num=20, validate_max=True, absolute_max=40)


CONSUMPTION_LEGS = [("intra_t", "Intra-EU sea voyage · 100%"),
                    ("extra_t", "EU ↔ non-EU sea voyage · 50%"),
                    ("outside_t", "Other sea voyage · 0%"),
                    ("eu_berth_t", "EU berth · 100%"),
                    ("non_eu_berth_t", "Non-EU berth · 0%")]


class ConsumptionFuelForm(StyledForm):
    voyage = forms.TypedChoiceField(label="Voyage", choices=[(i, f"Voyage {i}") for i in range(1, 101)],
                                    coerce=int, initial=1, required=False, empty_value=1)
    leg = forms.ChoiceField(label="Voyage / berth category", choices=[("", "Choose a category")] + CONSUMPTION_LEGS)
    fuel = forms.ChoiceField(label="Fuel type")
    tonnes = forms.FloatField(min_value=0, max_value=10000000, label="Annual tonnes")
    ops_share = forms.FloatField(required=False, min_value=0, max_value=100, label="EU berth replaceable by shore power · %")

    def __init__(self, *args, fuels, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fuel"].choices = [("", "Choose a fuel")] + fuel_choices(fuels)
        self.fields["ops_share"].widget.attrs["placeholder"] = "Default"


class BaseConsumptionFormSet(forms.BaseFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        seen = set()
        for form in self.forms:
            row = form.cleaned_data
            if not row or row.get("DELETE"):
                continue
            pair = row["voyage"], row["fuel"], row["leg"]
            if pair in seen:
                raise forms.ValidationError(f"Combine {pair[1]} consumption for the same voyage/berth category in Voyage {pair[0]} into one row.")
            seen.add(pair)


ConsumptionFormSet = forms.formset_factory(ConsumptionFuelForm, formset=BaseConsumptionFormSet,
    extra=0, can_delete=True, min_num=1, validate_min=True, max_num=100, validate_max=True, absolute_max=200)


def consumption_initial_rows(vessel):
    rows = []
    for entry in vessel.consumption_entries():
        for leg, _ in CONSUMPTION_LEGS:
            if entry.get(leg, 0):
                row = {"voyage": entry.get("voyage", 1), "fuel": entry["fuel"], "leg": leg, "tonnes": entry[leg]}
                if leg == "eu_berth_t" and "ops_share" in entry:
                    row["ops_share"] = entry["ops_share"] * 100
                rows.append(row)
    return sorted(rows, key=lambda row: row["voyage"]) or [{"voyage": 1, "fuel": vessel.fuel, "leg": "intra_t", "tonnes": 0}]


class VesselForm(StyledForm):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    name = forms.CharField(max_length=100, label="Vessel name")
    imo = forms.CharField(max_length=7, required=False, label="IMO number", help_text="Optional for a planning vessel; check digit is validated when supplied.")
    ship_type = forms.ChoiceField(choices=[("cargo", "Cargo / bulk carrier"), ("tanker", "Tanker"), ("container", "Container ship"), ("passenger", "Passenger ship")], label="Ship type")
    gt = forms.IntegerField(min_value=1, max_value=1000000, label="Gross tonnage · GT")
    fuel = forms.ChoiceField(label="Current fuel at sea")
    sea_t = forms.FloatField(min_value=0, max_value=10000000, label="Annual sea fuel · tonnes", help_text="Current main fuel across all voyages, excluding separately entered MGO pilot and EU berth fuel. Repeated for each year.")
    berth_t = forms.FloatField(min_value=0, max_value=1000000, label="Annual EU berth MGO · tonnes", help_text="Additional to sea fuel; includes eligible EU port operations.")
    intra_share = forms.FloatField(min_value=0, max_value=100, label="Default intra-EU voyages · %")
    extra_share = forms.FloatField(min_value=0, max_value=100, label="Default EU ↔ non-EU voyages · %", help_text="Used for blank voyage shares in the fuel rows and for separately entered pilot fuel. The remaining share is outside scope. Use consumption shares, not voyage counts.")
    alternative = forms.ChoiceField(label="Alternative to evaluate")
    max_blend = forms.FloatField(min_value=0, max_value=100, label="Maximum alternative energy share · %", help_text="Overall cap across all current sea fuels, including current pilot. The optimizer chooses which fuels to reduce; an individual fuel may be fully replaced within this total cap. Reductions and replacement energy are allocated to the same voyage and sea leg. Equals thermal energy share only at energy ratio 1; not a Bxx mass/volume specification.")
    compatible = forms.BooleanField(required=False, label="Technical compatibility and blend limit have been checked")
    opening_bank = forms.FloatField(min_value=0, max_value=100000000, label="Opening FuelEU bank · tCO₂e", help_text="Verified surplus belonging to this ship only.")
    prior_penalties = forms.IntegerField(min_value=0, max_value=25, label="Immediately preceding consecutive penalty years")
    ops_ready = forms.BooleanField(required=False, label="Evaluate shore power: ship and intended ports are compatible")
    ops_fraction = forms.FloatField(min_value=0, max_value=100, label="Default EU berth share replaceable by shore power · %", help_text="Used for EU berth rows with a blank shore-power percentage. Exclude boiler and other fuel use that shore electricity cannot replace. Each EU berth row can override this default.")
    generator_efficiency = forms.FloatField(min_value=5, max_value=100, label="Generator electrical efficiency · %", help_text="One efficiency applies to all EU berth fuel selected for shore-power replacement.")
    ops_efficiency = forms.FloatField(min_value=5, max_value=100, label="Shore connection efficiency · %")
    ops_capex = forms.FloatField(min_value=0, max_value=100000000, label="OPS initial investment · EUR")
    ops_annual = forms.FloatField(min_value=0, max_value=100000000, label="OPS extra annual operating cost · EUR")
    fuel_consumer = forms.ChoiceField(required=False, choices=[("", "Not applicable / select for methane fuel")] + [(key, label) for key, (label, _) in LNG_CONSUMERS.items()], label="Current LNG / bio-LNG / e-LNG engine")
    berth_consumer = forms.ChoiceField(required=False, choices=[("", "Not applicable / select for methane fuel")] + [(key, label) for key, (label, _) in LNG_CONSUMERS.items()], label="LNG / bio-LNG / e-LNG engine at berth", help_text="Berth engines may have different methane slip from the engines used at sea.")
    alternative_consumer = forms.ChoiceField(required=False, choices=[("", "Not applicable / select for methane fuel")] + [(key, label) for key, (label, _) in LNG_CONSUMERS.items()], label="Alternative LNG / bio-LNG / e-LNG engine")
    pilot_t = forms.FloatField(required=False, min_value=0, max_value=10000000, label="Current annual sea MGO pilot · tonnes", help_text="Additional pilot consumption for engines that need it. Exclude these tonnes from the fuel rows above. Uses the default voyage mix.")
    alternative_pilot_share = forms.FloatField(required=False, min_value=0, max_value=50, label="Alternative system MGO pilot energy share · %", help_text="Within the alternative system's total thermal input, not added on top. Manufacturer/load-dependent assumption.")
    alternative_energy_ratio = forms.FloatField(required=False, min_value=25, max_value=400, label="Alternative system energy requirement · % of baseline", help_text="100% means equal thermal input for the same service. For example, 80% means 20% less thermal input. Include the pilot system and use a reviewed efficiency estimate.")
    fuel_capex = forms.FloatField(required=False, min_value=0, max_value=100000000, label="Fuel conversion & downtime investment · EUR", help_text="Full initial incremental cost if switching is selected; not scaled down by the replacement share. Zero for an already equipped ship where appropriate.")
    fuel_annual = forms.FloatField(required=False, min_value=0, max_value=100000000, label="Fuel system extra annual operating cost · EUR")
    fuel_systems_confirmed = forms.BooleanField(required=False, label="Fuel system, pilot consumption, efficiency and investment assumptions have been reviewed")
    technical_reference = forms.CharField(required=False, max_length=1000, label="Fuel-system technical review reference", widget=forms.Textarea(attrs={"rows": 2}), help_text="Required for methane, methanol, ammonia and hydrogen use. Record engine/fuel-system approval, pilot needs, fuel-cell vs combustion pathway, and cost/efficiency basis.")

    def __init__(self, *args, fuels, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fuel"].choices = fuel_choices(fuels)
        self.fields["alternative"].choices = fuel_choices(fuels)
        self._use_table = not self.is_bound or "consumption-TOTAL_FORMS" in self.data
        self._use_mix = not self._use_table and "sea_fuels-TOTAL_FORMS" in self.data
        entries = self.initial.get("sea_fuels") or [{"fuel": self.initial.get("fuel", "VLSFO"), "sea_t": self.initial.get("sea_t", 4000)}]
        initial_rows = [{key: value * 100 if key in ("intra_share", "extra_share") else value for key, value in entry.items()} for entry in entries]
        self.sea_fuel_formset = SeaFuelFormSet(self.data if self.is_bound and self._use_mix else None, initial=initial_rows,
                                             prefix="sea_fuels", form_kwargs={"fuels": fuels})
        if self._use_mix:
            self.fields.pop("fuel")
            self.fields.pop("sea_t")
        self.consumption_formset = ConsumptionFormSet(self.data if self.is_bound and self._use_table else None,
            initial=self.initial.get("consumption_rows", []), prefix="consumption", form_kwargs={"fuels": fuels})
        if self._use_table:
            for key in ("fuel", "sea_t", "berth_t", "intra_share", "extra_share", "pilot_t"):
                self.fields.pop(key)

    @property
    def input_formset(self):
        return self.consumption_formset if self._use_table else self.sea_fuel_formset

    def is_valid(self):
        valid = super().is_valid()
        if self._use_table:
            table_valid = self.consumption_formset.is_valid()
            return valid and table_valid
        if self.initial.get("consumption") is not None:
            self.add_error(None, "The consumption table is missing. Reload the vessel before saving.")
            return False
        if self._use_mix:
            mix_valid = self.sea_fuel_formset.is_valid()
            return valid and mix_valid
        if self.initial.get("sea_fuels"):
            self.add_error(None, "The fuel rows are missing. Reload the vessel before saving.")
            return False
        return valid

    @staticmethod
    def initial_for(vessel, revision):
        initial = asdict(vessel) | {"revision": revision, "consumption_rows": consumption_initial_rows(vessel)}
        if vessel.consumption is None:
            initial.pop("consumption")
        for key in ("intra_share", "extra_share", "max_blend", "ops_fraction", "generator_efficiency", "ops_efficiency", "alternative_pilot_share", "alternative_energy_ratio"):
            initial[key] *= 100
        if vessel.sea_fuels:
            initial.update({"sea_fuels-TOTAL_FORMS": len(vessel.sea_fuels), "sea_fuels-INITIAL_FORMS": len(vessel.sea_fuels)})
            for index, entry in enumerate(vessel.sea_fuels):
                for key, value in entry.items():
                    initial[f"sea_fuels-{index}-{key}"] = value * 100 if key in ("intra_share", "extra_share") else value
        if vessel.consumption is not None:
            rows = initial["consumption_rows"]
            initial.update({"consumption-TOTAL_FORMS": len(rows), "consumption-INITIAL_FORMS": len(rows)})
            for index, row in enumerate(rows):
                for key, value in row.items():
                    initial[f"consumption-{index}-{key}"] = value
        return initial

    def vessel(self):
        values = {k: v for k, v in self.cleaned_data.items() if k != "revision"}
        for key in ("pilot_t", "alternative_pilot_share", "fuel_capex", "fuel_annual"):
            if key in values and values[key] is None:
                values[key] = 0
        if values["alternative_energy_ratio"] is None:
            values["alternative_energy_ratio"] = 100
        for key in ("intra_share", "extra_share", "max_blend", "ops_fraction", "generator_efficiency", "ops_efficiency", "alternative_pilot_share", "alternative_energy_ratio"):
            if key in values:
                values[key] /= 100
        if self._use_table:
            entries = {}
            for form in self.consumption_formset:
                row = form.cleaned_data
                if not row or row.get("DELETE"):
                    continue
                entry = entries.setdefault((row["voyage"], row["fuel"]), {"voyage": row["voyage"], "fuel": row["fuel"]})
                entry[row["leg"]] = row["tonnes"]
                if row["leg"] == "eu_berth_t" and row["ops_share"] is not None:
                    entry["ops_share"] = row["ops_share"] / 100
            values.update(consumption=list(entries.values()), sea_t=0, berth_t=0, pilot_t=0,
                          intra_share=0, extra_share=0, fuel=next(iter(entries.values()))["fuel"])
        if self._use_mix:
            entries = []
            for form in self.sea_fuel_formset.forms:
                row = form.cleaned_data
                if not row or row.get("DELETE"):
                    continue
                entry = {"fuel": row["fuel"], "sea_t": row["sea_t"]}
                for key in ("intra_share", "extra_share"):
                    if row[key] is not None:
                        entry[key] = row[key] / 100
                entries.append(entry)
            values["sea_fuels"] = entries
            values["fuel"] = entries[0]["fuel"]
            values["sea_t"] = sum(entry["sea_t"] for entry in entries)
        return Vessel(**values)


class FuelForm(StyledForm):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    price = forms.FloatField(min_value=0, max_value=50000, label="Fuel price · EUR/tonne")
    lcv = forms.FloatField(min_value=1000, max_value=150000, label="Lower calorific value · MJ/tonne")
    wtw = forms.FloatField(min_value=-100, max_value=500, label="Well-to-wake intensity · gCO₂e/MJ", help_text="Complete pathway intensity, including non-CO₂ gases; must match evidence and engine pathway.")
    co2 = forms.FloatField(min_value=0, max_value=10, label="Physical CO₂ factor · t/tonne fuel", help_text="Before eligible renewable CO₂ zero-rating.")
    ch4 = forms.FloatField(required=False, min_value=0, max_value=1, label="Combustion CH₄ factor · t/tonne fuel", help_text="Do not add LNG slip here: it is calculated separately from each vessel's engine selection.")
    n2o = forms.FloatField(required=False, min_value=0, max_value=1, label="Combustion N₂O factor · t/tonne fuel")
    supply_t = forms.FloatField(min_value=0, max_value=10000000, required=False, label="Annual fleet supply cap · tonnes", help_text="Blank means unconstrained; zero means unavailable.")
    eligible = forms.BooleanField(required=False, label="RED sustainability and FuelEU pathway eligibility have been checked", help_text="Required to include this renewable fuel in the optimizer. When unchecked, the fuel is excluded regardless of its WtW value or the EUA/pooling prices. Record the supporting reference below.")
    ets_eligible = forms.BooleanField(required=False, label="Separately confirm ETS CO₂ zero-rating eligibility", help_text="FuelEU eligibility does not by itself establish ETS zero-rating. CH4 and N2O are not zero-rated.")
    wtt = forms.FloatField(required=False, min_value=-200, max_value=500, label="FuelEU well-to-tank factor · gCO₂e/MJ", help_text="For RFNBO/bio-LNG use the certified FuelEU-adjusted WtT, not a complete WtW value. Include the applicable carbon-accounting adjustment; physical combustion emissions are added by the engine.")
    factors_confirmed = forms.BooleanField(required=False, label="Measured CH₄ / N₂O factors and pathway evidence have been reviewed", help_text="Required for methanol/ammonia combustion and hydrogen ICE. Blank is unknown, not zero. Enter zero only where supported by the evidence.")
    reward_enabled = forms.BooleanField(required=False, label="Apply the elective FuelEU RFNBO reward through 2033", help_text="Doubles only this eligible RFNBO's contribution to the intensity denominator through 2033. The optimizer treats this as a fixed assumption; disable it to compare a no-reward case.")
    evidence = forms.CharField(max_length=1000, required=False, label="Evidence / pathway reference", widget=forms.Textarea(attrs={"rows": 3}), help_text="Record supplier proof, feedstock/production pathway, validity, measured engine factors and monitoring-plan reference. RFNBOs need applicable renewable-electricity/additionality, correlation and GHG-saving evidence. The app does not authenticate documents. Food/feed crop biofuels are not supported as eligible alternatives.")

    def __init__(self, *args, fuel, **kwargs):
        super().__init__(*args, **kwargs)
        if fuel.rfnbo or fuel.pathway == "methane":
            self.fields.pop("wtw")
        else:
            self.fields.pop("wtt")
        if not fuel.renewable:
            self.fields["eligible"].disabled = True
            self.fields["ets_eligible"].disabled = True
        if not fuel.measured_factors_required:
            self.fields.pop("factors_confirmed")
        if not fuel.rfnbo:
            self.fields.pop("reward_enabled")
        if fuel.pathway in ("methane", "hydrogen_cell"):
            for key in ("co2", "ch4", "n2o"):
                self.fields[key].disabled = True
        if fuel.pathway == "methane":
            self.fields["lcv"].disabled = True
        if fuel.code == "LNG":
            self.fields["wtt"].disabled = True


class MemberForm(StyledForm):
    username = forms.RegexField(regex=r"^[\w.@+-]+$", max_length=150, label="Username")
    email = forms.EmailField(label="Work email")
    role = forms.ChoiceField(choices=Membership.ROLES)
    password = forms.CharField(widget=forms.PasswordInput, label="Initial password", help_text="At least 12 characters. Share it through your approved secure channel; the user can change it after login.")

    def clean_username(self):
        name = self.cleaned_data["username"]
        if get_user_model().objects.filter(username__iexact=name).exists():
            raise forms.ValidationError("This username is unavailable.")
        return name

    def clean(self):
        data = super().clean()
        if data.get("password"):
            user = get_user_model()(username=data.get("username", ""), email=data.get("email", ""))
            validate_password(data["password"], user)
        return data


class VesselImportForm(StyledForm):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    csv_file = forms.FileField(label="Fleet Excel or CSV file", help_text="Excel .xlsx up to 2 MB, or UTF-8 CSV up to 512 KB; up to 20 vessels and 2,000 consumption rows. Import adds vessels and retains existing ones.", widget=forms.ClearableFileInput(attrs={"accept": ".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"}))
