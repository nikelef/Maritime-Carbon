# Using LNG and RFNBOs

Available in the Django customer application, engine 6.7.0. These are planning
pathways, not fuel certificates or technical approvals. Prices are illustrative.

## Set up a vessel

1. Open a decision case. Older cases show **Add available fuel pathways**; click
   it to add the new entries while retaining existing prices and saved reports.
2. Select a current sea fuel and an alternative in the vessel editor. LNG,
   bio-LNG and e-LNG each need the correct engine class for the relevant stream.
   An existing LNG vessel can compare e-LNG or bio-LNG; an oil vessel can evaluate
   conversion to LNG, methanol, ammonia or hydrogen where technically supported.
3. Enter annual consumption by fuel, voyage and sea/berth category, including pilot.
   Do not count pilot fuel twice. Enter the alternative system's pilot fraction,
   relative energy requirement, conversion/downtime and incremental annual costs.
4. Confirm technical compatibility and record the technical-review reference.
   Hydrogen fuel cells and hydrogen combustion are distinct pathways. The ammonia
   entry is combustion, not an ammonia fuel-cell installation.

The maximum replacement is a share of the baseline sea **service demand**.
At an energy requirement of 100%, thermal input is conserved; at 80%, the
alternative system consumes 20% less thermal energy for the same service.
Its pilot fraction is inside that alternative energy budget. This setting is
not the final RFNBO energy share and is not a mass/volume blending specification.

## Review the fuel library

- Fossil LNG uses four supported regulatory default engine/slip pathways.
  It does not receive renewable eligibility or RFNBO credit.
- LBM is bio-LNG, not RFNBO. Its certification and carbon-accounting pathway matter.
- RFNBO choices are e-LNG, e-methanol, e-ammonia, hydrogen fuel cell, hydrogen
  combustion and e-diesel. A chemical name alone does not establish RFNBO status.
- Enter the certified **FuelEU-adjusted WtT** factor for RFNBOs/bio-LNG, not a
  complete WtW number. The engine adds physical consumer emissions using FuelEU
  GWP100 CH4=25 and N2O=298. ETS separately uses CH4=28 and N2O=265. Review any
  carbon-accounting adjustment with the supplier/verifier to avoid double counting.
- Provide measured CH4/N2O factors where requested. Blank means unknown, not zero.
  The application will not enable the pathway until the required fields and
  evidence review are complete.
- Confirm FuelEU eligibility and ETS CO2 zero-rating separately. Evidence must
  cover the production route and applicable RED requirements. The app records
  the review; it does not inspect or authenticate certificates.
- The optional RFNBO reward is enabled initially for eligible RFNBOs through 2033.
  It affects the intensity denominator only. Disable it for a no-reward comparison;
  the search does not choose that election for you. Annual attribution minimizes
  attained intensity including the elected reward. It can prioritize RFNBO over
  lower physical-WtW fuel when the denominator benefit improves the total ratio.
  Conventional fuels retain internal lowest-WtW priority. CH4/N2O remain in ETS from 2026.
- Set annual supply caps and actual quoted prices. Conversion costs belong in
  the vessel editor, not in the per-tonne fuel price unless genuinely quoted there.

## Read the result

The operating-choice table shows the service share assigned to the alternative.
The fuel-pathway ledger shows tonnes, pilot, LNG slip, scoped methane, actual
RFNBO fuel-energy share and effective RFNBO reward. CSV and JSON include the
physical and rewarded energy, inputs and versioned calculation record. RFNBO
share and shortfall use physically scoped fuel energy (full intra-EU/EU berth,
half EU/non-EU sea, no outside-scope use), independently of GHG allocation.
Actual shore electricity is excluded. Allocated fuel/RFNBO energy is exported
separately for GHG accounting.

For horizons reaching 2034, the default shows potential 2% RFNBO shortfall without
pricing it. In case assumptions, open **RFNBO subtarget from 2034** to record an
active/inactive future-rule stress test. An active assumption requires a price-
difference Pd in EUR per equivalent 41,000-MJ tonne and its rationale. This is
not EUR/tonne of hydrogen or methanol and not an official future tariff. No separate
RFNBO pool, bank or equivalent-fuel exemption is assumed. The entered Pd is fixed
across years and ships in the case; use separate cases where that assumption differs.

Only one selected alternative system per vessel is searched in a case. Duplicate
the case to compare another technology. The model does not establish a global
fleet optimum or cover mixed-engine/load-dependent slip, additional venting,
non-MGO alternative-system pilot, all port-call obligations or every voyage exemption.
See [the regulatory calculation contract](REGULATORY_BASIS.md) before using
results for a customer decision.

The allocation ledger shows each source's physical WtW, denominator reward,
eligible MJ and allocated MJ. Saved reports retain the original engine and
results. Review older saved complete WtW inputs against the FuelEU 25/298 basis
before rerunning. Noncanonical fossil oil factors block a new comparison until
the case's supported defaults are explicitly restored; historical reports retain
their recorded inputs and results.
