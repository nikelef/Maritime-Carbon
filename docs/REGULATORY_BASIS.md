# Regulatory basis and calculation contract

Allocation source review: 2026-09-10; wind source review: 2026-09-16.
Ruleset: `EU-2026-09-16-wind`. Engine: `6.8.0`.
Earlier dated sections below record the history; the current allocation contract supersedes proportional attribution and the 6.6 physical-WtW ordering when an RFNBO reward applies.
This is a bounded planning model, not a statement of universal legal applicability.

## Sources

- [Regulation (EU) 2023/1805](https://eur-lex.europa.eu/eli/reg/2023/1805/oj/eng): FuelEU applicability, intensity, fuel evidence, flexibility and penalties.
- [Commission FuelEU Q&A](https://transport.ec.europa.eu/transport-modes/maritime/decarbonising-maritime-transport-fueleu-maritime/questions-and-answers-regulation-eu-20231805-use-renewable-and-low-carbon-fuels-maritime-transport_en): operational interpretation, particularly Articles 20–21.
- [Commission maritime ETS FAQ](https://climate.ec.europa.eu/areas-action/transport-decarbonisation/reducing-emissions-shipping-sector/faq-maritime-transport-eu-emissions-trading-system-ets_en): scope, reporting-year phase-in, greenhouse gases and fuel allocation.
- [Delegated Regulation (EU) 2023/2776](https://eur-lex.europa.eu/eli/reg_del/2023/2776/oj/eng): MRV calculation methods and CO2 equivalents.
- [EMSA FuelEU technical introduction](https://www.emsa.europa.eu/we-do/sustainability/environment/reducing-emissions/download/7853/5238/23.html): shore-electricity regulatory intensity and technology treatment.
- [Commission FuelEU overview](https://transport.ec.europa.eu/transport-modes/maritime/decarbonising-maritime-transport-fueleu-maritime_en): OPS implementation and the separate EEA applicability issue.
- [RFNBO production criteria, Regulation (EU) 2023/1184](https://eur-lex.europa.eu/eli/reg_del/2023/1184/oj/eng) and [lifecycle methodology, Regulation (EU) 2023/1185](https://eur-lex.europa.eu/eli/reg_del/2023/1185/oj/eng): eligibility evidence, not an in-app certification service.
- [ETS alternative-fuel monitoring amendment, Regulation (EU) 2024/2493](https://eur-lex.europa.eu/eli/reg_impl/2024/2493/oj/eng): RFNBO CO2 zero-rating conditions are distinct from the FuelEU assertion.

## Units and accounting

Mass is metric tonnes; energy is MJ (electricity is entered/priced in MWh);
intensity is gCO2e/MJ; compliance balances and ETS emissions are tCO2e; money is EUR.
The 1,000,000 conversion is grams per tonne. There are 3,600 MJ per MWh.

Ship annual intensity is an allocated energy-weighted average of entered complete
oil/biofuel intensities or derived fuel/consumer intensities and regulatory
zero-intensity shore electricity, with the elective RFNBO denominator reward.
Baseline fuel quantities include all modelled sea consumption. Proportional
scope determines ETS emissions and the FuelEU Article 2 energy total, never the
cost of purchasing all that fuel. FuelEU source attribution then follows the
annual prioritized allocation contract below.

FuelEU applies above 5,000 GT for supported commercial cargo/passenger types.
ETS includes the 5,000 GT boundary. The application deliberately distinguishes
the thresholds. It does not infer eligibility solely from an IMO number.

Target intensity is 91.16 multiplied by one minus the applicable reduction.
The reductions are 2%, 6%, 14.5%, 31%, 62% and 80% from 2025, 2030, 2035,
2040, 2045 and 2050 respectively. Ship balance is `(target − attained) × E / 1e6`.
A residual deficit uses `deficit_t × 1e6 / (attained × 41000) × 2400`, with
the ship-specific `1 + (n−1)/10` consecutive-penalty multiplier.

ETS uses 70% of scoped CO2 for reporting year 2025 and 100% from 2026, when
CH4 and N2O are included. GWP100 is 28 for methane and 265 for nitrous oxide.
Eligible renewable CO2 treatment affects the CO2 component only.

## Fuel factors and evidence

HSFO uses the Annex II residual-oil reference: LCV 40,500 MJ/t, WtT 13.5,
CO2 3.114 t/t, CH4 0.00005 t/t and N2O 0.00018 t/t. VLSFO initially uses
that pathway as an explicit composition assumption; the actual blend matters.
MGO uses LCV 42,700, WtT 14.4 and CO2 3.206, with the same reference CH4/N2O.
Initial fossil WtW is derived from these factors, rather than a disconnected
rounded value. Users must review changes to the complete WtW factor themselves;
editing individual ETS factors does not implicitly change supplier-pathway WtW.

HVO/FAME prices, full pathway intensities, LCV and engine factors are illustrative
inputs. They are not universally valid regulatory defaults. The eligibility flag
and evidence reference are required before these fuels can be selected by the
search. Technical compatibility must also be confirmed for each ship. The flag
records the user's assertion; it does not authenticate evidence, assess RED
criteria, monitor expiry, or validate a supplier's sustainability certificate.
Food/feed crop pathways are not supported as eligible alternatives.

### LNG and renewable methane

The library includes fossil LNG, LBM (bio-LNG) and RFNBO e-LNG. Baseline and
alternative sea streams each have their own consumer selection. Annex II FuelEU
and Annex I MRV default slip fractions are 0.031 for Otto medium speed, 0.017 for
Otto slow speed, 0.002 for Diesel slow speed and 0.026 for LBSI. There is no silent
generic-engine default. This release implements those default pathways only.

For a methane stream supplied with `m` tonnes and slip fraction `s`, physical
emissions are `m × 2.75 × (1-s)` tonnes CO2, `m × s` tonnes CH4 and
`m × 0.00011 × (1-s)` tonnes N2O. Thus slip is neither added twice nor treated
as combusted CO2. LNG LCV is 49,100 MJ/t. Its FuelEU WtT default is 18.5 g/MJ;
these reference factors are locked in the customer form. Derived intensity is
`WtT + [CO2/t + 25×CH4/t + 298×N2O/t] × 1e6 / LCV`.
ETS uses the same physical consumer factors, applying scope/phase-in and any
separately recorded renewable CO2 zero-rating. WtT never enters ETS emissions.

Bio-LNG and e-LNG need a certified FuelEU-adjusted WtT input. It can include a
negative carbon-accounting adjustment; do not paste a complete lifecycle WtW
number into WtT and then add combustion a second time. The engine does not infer
that adjustment from a fuel name, nor provide a generic renewable certificate.

### RFNBOs and unknown emission factors

Supported RFNBO entries are e-LNG, e-methanol combustion, e-ammonia combustion,
hydrogen fuel cells, hydrogen combustion and e-diesel. The renewable production
route, not merely the chemical fuel, determines RFNBO status. New entries begin
ineligible, without a certified WtT value and without ETS zero-rating. The library
does not classify fossil or low-carbon hydrogen/ammonia as RFNBO automatically.

Methanol CH4/N2O, ammonia CH4/N2O and hydrogen-ICE N2O factors start blank.
These pathways require measured-factor values, review confirmation and evidence
before being enabled. They are not given invented zero factors. This is a
conservative product gate; it does not claim that the legislation prohibits
every Annex II fallback method. Hydrogen fuel cells have a distinct zero-direct-
emission pathway. Ammonia fuel-cell installations are not modelled by its ICE entry.

With physical in-scope energy `E` (including OPS), and eligible RFNBO energy
`R` for which the elective reward is enabled, intensity is
`scoped lifecycle emissions [g] / (E + (reward-1) × R)`.
The reward is 2 through 2033 and 1 from 2034. Annex IV compliance balance still
uses **physical E**, not the rewarded denominator. The per-fuel reward setting
is a fixed case assumption; annual allocation optimizes its denominator benefit. The search does not change the election.

FuelEU eligibility and ETS CO2 zero-rating have separate controls. Both require
an evidence reference; checking a box is not verification of RED certification,
GHG savings, additionality, correlation, batch traceability or evidence validity.
Legacy HVO/FAME combined assertions are retained when loading old cases until
the fuel form is reviewed; RFNBO entries never inherit that combined assertion.

### Conditional RFNBO subtarget: prospective stress testing

Article 5's potential 2% requirement from 2034 is conditional on monitoring and
Commission assessments, including safeguards. Activation, future implementation
and the price-difference factor are not presented as settled by this application.
The default is **unresolved**: potential shortfall is shown but no penalty is
priced, and the report prominently identifies partial cost scope.

Users can record an assumed-active or assumed-inactive case with a rationale.
For an active stress test, the ship shortfall is
`max(0, 0.02 × physical in-scope fuel energy − eligible RFNBO energy)` in MJ.
OPS energy is excluded. The modelled charge is `shortfall / 41000 × assumed Pd`,
with the Article 23 consecutive-penalty uplift. Pd is a user-entered constant
EUR per equivalent 41,000-MJ tonne, shared across the case, not the quoted price
per tonne of the chosen chemical fuel or a verified future statutory tariff.
It does not follow the fuel-price escalation setting. Review it for each ship's
compatible installation; use separate cases if ship-specific assumptions differ.

No RFNBO-subtarget bank, pool or equivalent-savings fuel exemption is assumed.
The GHG-intensity bank/pool cannot erase this separate MJ shortfall. The annual
FuelEU penalty total includes both its GHG and assumed RFNBO components; the
audit/export separates them to prevent double counting. All post-2033 options
remain explicitly labelled as future-rule assumptions or unresolved costs.

### Service demand, pilot fuel and conversion costs

The consumption table records annual tonnes by fuel and operating category:
intra-EU sea, EU/non-EU sea, other sea, EU berth and non-EU berth. Current pilot
fuel is included in its actual fuel/category rows. Legacy sea shares and
separate MGO pilot/berth inputs are converted on edit without modifying saved
reports. Baseline sea thermal input is `E0 = sum(sea_fuel_t × fuel_LCV)`, including
current pilot. Legacy inputs retain their separate pilot term until converted.
For each current sea fuel `i`, the optimizer chooses a replacement fraction
`x_i`, applied to all its sea legs (and legacy separate pilot for MGO). Residual
consumption is `t_i × (1-x_i)`. The aggregate replacement share is
`x = sum(t_i × LCV_i × x_i) / E0`, bounded by the vessel limit. The alternative
system takes `E0 × x × energy_ratio`, inherits the scope of the actual displaced
energy, and is split into
alternative main fuel `(1-p)` and MGO pilot `p`, then converted to tonnes with
their respective LCVs. This preserves service demand under the entered relative
efficiency assumption; it preserves thermal energy only when energy_ratio is 1.
An energy/service allocation is not approval to blend chemicals in one tank.

All fuel, including pilot, is purchased and counted against shared annual supply
caps. Scope never halves purchase costs. Any selected switch incurs its full
initial conversion/downtime cost in the first year and incremental annual cost
each year; costs are not scaled down by its replacement percentage. Zero costs
may be appropriate for an already equipped ship but require technical review for
non-oil systems. One alternative system per ship is evaluated per case.

## Strategy policy versus legal permission

Each ship first uses its own opening bank against its deficit. Current surplus
can be carried forward or allocated in a modelled fleet pool. Existing bank
never transfers to another ship. No bank is converted to cash, sold, or assigned
a terminal value.

For modelling simplicity, a pooling policy settles the full included fleet only
when current surplus and enabled external capacity suffice. Otherwise ships
settle individually. This does not search every possible subset of a fleet pool.
Internal allocation conserves balances and retains positive surplus. External
surplus purchases are conditional on a complete legally valid pool, eligible
counterparties, agreed allocation and verifier/database formalities. The app
does not inspect the counterparty fleet and cannot certify pool validity.
Pool units are compliance balance, not EUAs and not a statutory tradable currency.

Borrowing is not optimized. Its numerical limit helper is 2% of target intensity
times scoped energy. An actual arrangement also needs the following-year 10%
deduction, the consecutive-year prohibition, pooling restrictions and approval.

Shore electricity replaces generator electrical output, using entered generator
and connection efficiencies. The model includes purchased electricity, initial
OPS capital spending and annual incremental operating cost. It does not claim
that grid electricity has zero physical lifecycle emissions.

## Material exclusions and interpretation

- Ordinary EU sea-fuel shares are shared by the two regimes. Confirm actual
  voyage classification; different EEA implementation dates, derogations,
  ice-class adjustments and special port rules are not automatically resolved.
- Mixed sea-consumer classes, measured/load-dependent LNG slip, additional venting
  and boil-off beyond the selected default, non-MGO alternative-system pilot fuel,
  non-GHG-intensity enforcement penalties and mandatory OPS port-call penalties
  require separate assessment. Future RFNBO subtarget charges are stress-test
  assumptions, not verified future obligations. Affected horizons show warnings.
- No optimization of voyage scheduling, speed, charter allocation, allowance
  hedging, financing, taxes or equipment beyond entered fuel-system/OPS costs is claimed.
- Annual consumption and vessel decisions are fixed through the horizon. Prices
  follow user-entered escalation. Other fleet costs are common across strategies.
- Cash costs are attributed to reporting years. NPV discounts from the first
  reporting year; this is not a schedule of actual settlement/surrender dates.
- Supply caps are annual, shared across the modelled fleet. Blank means no
  imposed bound; zero means no supply. Replacement shares refer to baseline
  service demand; they are not Bxx volumes or the final RFNBO energy share.
- The search uses a finite grid, two starts and bounded coordinate passes.
  Price sensitivities reprice saved decisions, without rerunning optimization.

Before relying on a customer case, reconcile its input factors, scope and output
ledger against the customer's approved monitoring plan and independent reference
calculations. Regulatory updates require a reviewed engine/ruleset revision and
new calculation snapshots; old runs must not be silently rewritten.

### Fuel and operating-category table (engine 6.2)

Each fuel uses its own LCV, price and emissions factors in every category.
EU berth has scope 1 independently of sea-voyage allocation; non-EU berth has
scope 0 but remains a fuel purchase and supply-cap cost. Qualifying renewable
berth fuels contribute to the RFNBO numerator and, where elected, reward.
Methane at berth uses its own selected consumer class. HSFO is selectable at
berth for planning; approved sulphur-abatement arrangements and applicable local
operating/discharge rules must be assessed independently of carbon accounting.

OPS replaces only the specified share of each EU berth fuel. Replaced thermal
energy is `sum(EU_berth_t × replaceable_share × LCV)`; shore electricity is this
energy times generator efficiency divided by connection efficiency and 3,600.
The common generator efficiency applies to all replaced EU berth fuels. Boiler
and other non-replaceable fuel must be excluded through each row's replacement
share. Non-EU berth is never replaced by the EU OPS option. Sea-fuel switching
does not change berth fuel. Original and remaining berth mixes are traceable in
saved input JSON, report ledgers and CSV exports.

### Voyage groups (engine 6.3)

Consumption rows carry a voyage number (1–100). The same fuel/category can
repeat on different voyages. Each voyage/fuel group retains its own EU berth
shore-power share. Legacy entries without a number default to Voyage 1. All
voyages are summed in the annual model; the annual plan repeats across the
reporting horizon. Voyage numbers remain in saved inputs and in sea/berth
ledgers and their JSON/CSV exports.

### Replacement by current fuel (engine 6.4)

The search can vary one current fuel or transfer replacement between two fuels
at a fixed aggregate replacement share, including when the vessel cap is full.
Steps are 5% of total baseline sea energy, plus exact remaining-cap and
fuel-exhaustion endpoints. Uniform options remain candidates. Two starts and
up to three fleet passes with three allocation passes per vessel bound the
search; this is not a global optimality guarantee. An already-used alternative
is retained rather than selected to replace itself. No sea-fuel switching
changes berth fuel. Individual sea legs are not optimization variables.

The report records per-fuel fractions, removed and retained annual tonnes, and
alternative tonnes. It compares equal initial steps across all current source
fuels except the alternative itself, by full-horizon fleet NPV, holding other
vessels and this vessel's OPS fixed. It ranks the selected reductions using
these costs. The common step is at most 5% of total baseline sea energy and no
larger than the vessel cap or smallest current source-fuel stream. Supply-infeasible comparisons
produce no priority ranking. Equal costs use fuel-code order. This initial
comparison is distinct from the final jointly evaluated allocation and is not
a chronological switching plan. Sensitivities preserve per-fuel allocations.
Old analysis snapshots retain their original proportional decisions.

### Explaining excluded alternatives (engine 6.4.1)

Case pages and reports explicitly identify selected alternatives excluded by
unconfirmed eligibility or compatibility, missing required measured factors,
zero replacement limits, zero supply, or absent replaceable sea demand. Such a
result is not evidence that the excluded alternative is more expensive. Changing
WtW or carbon prices does not override these input constraints. Renewable fuels
that are evaluated without ETS CO2 zero-rating receive a separate notice: their
physical CO2 factor remains priced under ETS even when FuelEU WtW is low.

New results save these notices in the audit output. Earlier reports derive an
explanation from their own saved inputs without modifying or recomputing the
snapshot. Eligibility assertions are never enabled automatically.

### Actual strategy actions (engine 6.4.2)

Policy permissions are distinct from actions. Both fuel-choice policies can
select shore power. The report names actual sea-fuel replacement, shore-power
electricity, internal fleet transfers and external surplus purchases using the
saved decisions and ledger. Pooling is detected from transferred/purchased
quantities rather than cash cost: internal pooling and zero-price external
purchases must not be described as no pooling.

For equal NPV, comparison retains the reference first, then prefers a policy
without pooling. A pooling-enabled search that selects the same no-pooling
actions therefore cannot displace an identical non-pooling result just because
of its internal key. Existing snapshots keep their saved winner and amounts;
their report derives the clearer action description without recalculation.


### Replacement by voyage and sea leg (engine 6.5)

Each positive voyage/fuel/sea-category demand is a separate replacement
variable. Categories are intra-EU, EU–non-EU and outside-scope sea. The
alternative fuel and its MGO pilot supply replacement energy on that same leg:
`alternative MJ + pilot MJ = removed MJ × relative energy requirement`.
The ship cap uses total original sea energy; fuel supply is shared across the
fleet. Berth consumption is unchanged by sea-fuel switching. Legacy pilot is
included once using its recorded voyage shares.

The previous fuel search supplies a feasible incumbent. Two leg-search starts
(the incumbent and current fuels) run up to three fleet passes. Each coordinate
and energy transfer is sampled at 21 points within feasible bounds. Annual and
cumulative compliance-balance roots and shared fuel-supply boundaries are added
as candidates. Golden-section refinement around the best sampled interval uses
up to 36 iterations, with a parameter interval tolerance of 1e-10. Full-horizon
fleet simulation evaluates each candidate, including banking, pooling,
penalties and full conversion costs. Cost improvements below EUR 0.0001 are
ignored between coordinate updates. These are bounded heuristic searches;
multiple minima, pooling discontinuities and coupled fleet choices mean a
global optimum is not guaranteed.

The report remarks and operating-choice table identify the selected voyage,
sea leg and fuel quantities. JSON and CSV include `leg_replacements` with
original/removed/retained tonnes, removed energy, alternative energy, alternative
tonnes and MGO pilot tonnes. Sensitivities replay the saved leg allocations.
The existing equal-step fuel comparison retains proportional allocation as an
illustration and is distinct from the selected leg recommendation. Earlier
snapshots retain their original allocation and its methodology disclosure.


### Two-percent search grid (engine 6.5.1)

The initial fuel allocation grid now uses 2% of total original sea energy,
including the uniform-start fallback and fuel first-step comparison. Leg
coordinate and pair-transfer searches sample 51 points (50 equal intervals,
2% of each feasible range). Continuous refinement and exact compliance/supply
boundary candidates remain enabled. New reports record and show the grid size;
older saved calculations retain their original grid description.

Strategies remain separate if their operating decisions, ship ledgers, annual
cost components, total cost or NPV differ. Only identical outcomes are grouped;
equality is checked before display rounding. Policy names alone do not make outcomes different. Nonempty first-step
comparisons and priority details displayed in section 03 do keep them separate.


### Annual prioritized FuelEU allocation (engine 6.6)

Basis: [Commission guidance, 8 October 2025, section 4.4, pages 51–52](https://transport.ec.europa.eu/document/download/d4426ccc-ef46-4292-8b6d-5bf7a620f5ba_en?filename=fueleu_guidance_document_for_shipping_companies.pdf#page=51).
The guidance permits annual ship-specific attribution across MRV-reported
consumption, including prioritization among conventional fuels. This is an
elected method, not a compulsory allocation order in the legislative text.

Implementation contract:

- Determine physical consumption after sea substitution, pilot and OPS.
- Calculate covered energy using 100% intra-EU sea/EU berth, 50% EU–non-EU
  sea and 0% outside-scope sea/non-EU berth, plus shore electricity.
- Build a separate annual source inventory using full intra-EU and EU–non-EU
  sea consumption and EU berth consumption. Include alternative and pilot fuel
  only to the extent physically consumed in those eligible categories.
- Group by fuel and consumer. Minimize attained intensity including elected RFNBO
  rewards. Without an active reward, rank by physical WtW, lowest first.
  Shore electricity has zero intensity and reward 1. Conventional fuels retain
  internal lowest-WtW priority. Deterministic ties use physical WtW, code and consumer.
- Fill the covered physical energy total, using a partial final source where
  needed. All source energies remain bounded by their eligible consumption.
- Apply the reward in the intensity denominator while choosing attribution;
  physical compliance energy is not doubled. RFNBO fuel-energy share excludes
  allocated electricity. The reward is 2 through 2033, 1 thereafter, with a
  fixed per-fuel election. The chosen order can change when that reward expires.
- Compute ETS separately from actual mass and proportional voyage scope.
  Purchases and annual supply caps retain all consumption, including excluded use.

Every baseline, candidate, pool calculation and saved-decision sensitivity uses
this accounting. Source-capacity breakpoints partition the continuous leg search;
compliance roots are evaluated within those partitions and verified against the
actual profiles, including nonlinear RFNBO cases. The bounded search retains its
fuel-level incumbent, two starts and fleet passes; it does not prove global
optimality or vary the elected attribution method.

Reports expose eligible and allocated physical MJ by source/consumer/year.
CSV exports add FuelEU_allocation_method and FuelEU_annual_allocation_json;
JSON includes the same row ledger. Engine/ruleset versions identify the change.
Historical results are displayed without recalculation and explicitly identified
as proportional; users must create a new run to apply prioritized attribution.

The current category model excludes outside-scope sea and non-EU berth from the
source inventory. It cannot distinguish MRV-reported FuelEU-exempt activity from
wholly ineligible activity. Such exempt activity, intermediate port stops and
ship-specific EEA/exemption cases still require separate assessment; they must
not be represented as freely eligible outside-scope fuel.


## RFNBO reward-aware allocation and separate GWP100 · engine 6.7.0

Basis: Commission FuelEU guidance sections 4.3.3 (pages 38–39), 4.3.6 (pages
46–50) and 4.4 (pages 51–52), and FuelEU Annex I / RED Annex V Part C(4).
[Official guidance](https://transport.ec.europa.eu/document/download/d4426ccc-ef46-4292-8b6d-5bf7a620f5ba_en?filename=fueleu_guidance_document_for_shipping_companies.pdf#page=38).

FuelEU uses CH4=25 and N2O=298; MRV/ETS uses CH4=28 and N2O=265. Separate named
constants prevent cross-regime reuse. Derived methane/RFNBO intensities, new-case
oil WtW defaults and fossil input consistency checks use the FuelEU values.
ETS gases retain their ETS factors. Manually entered complete WtW values remain
user inputs: old saved fuel values are not silently rewritten. Review those
values against the FuelEU basis before rerunning older cases. Historic reports
remain immutable and display their original method/version.

For each ship/year and physical candidate, solve:

`min I = sum(g_i*x_i) / [E + sum((r_i-1)*x_i)]`

subject to `sum(x_i)=E` and `0 <= x_i <= eligible_energy_i`. Here `E` is physical
Article 2 covered MJ, `g_i` is physical WtW, and `r_i` is 2 for reward-enabled,
eligible RFNBO through 2033 and 1 otherwise. This is the application's elected
minimum-intensity policy under the permitted free-allocation guidance, not a
statutory mandatory ordering. Reward election remains a user assumption.

The engine solves the linear-fractional allocation by iteratively filling the
inventory in ascending `g_i - I*(r_i-1)` and recalculating I until convergence.
At convergence the minimum of `N-I*D` is zero, certifying the fixed-inventory
intensity minimum to numerical tolerance. Physical-WtW sorting and sorting by
`g_i/r_i` alone do not solve this mixed-denominator problem. The calculation
supports OPS, negative intensities, partial final sources and deterministic ties.

Example: with 50 MJ covered and eligible 40 MJ biofuel at 20 g/MJ, 20 MJ RFNBO
at 25 and 40 MJ fossil at 90, the active reward selects 30 bio + 20 RFNBO:
`(30*20+20*25)/(50+20) = 15.7142857 g/MJ`. Physical-WtW-first attribution gives
17.5. With reward disabled or expired, selection returns to 40 bio + 10 RFNBO,
and intensity is 21 g/MJ. Physical purchases, ETS and fuel supply do not change.

The fleet optimizer recomputes this minimum for every baseline and candidate.
Line searches include both source-capacity and reward-order boundaries in every
active reward regime, including horizons crossing 2033/2034. Compliance roots
are checked against actual profiles. The annual attribution problem is solved;
the overall fleet-cost search remains bounded, without a global-optimum claim.
The post-2033 conditional subtarget uses the chosen attribution and its existing
separate shortfall stress test; no new RFNBO flexibility mechanism is introduced.

Exports identify `annual_reward_aware` and include each source's
`reward_multiplier`. The old `annual_lowest_wtw` marker identifies 6.6 snapshots.
See RFNBO_GWP_VERIFICATION.md for independent numerical and integration checks.

## Wind-assisted propulsion (engine 6.8.0)

Wind equipment can be selected together with fuel switching and pooling.
Physical net savings apply only to reviewed sea-propulsion demand; existing
wind baselines are not reduced again. The separate Annex I intensity reward
uses the discrete Pwind/Pprop bands described in Commission guidance 4.5,
Table 4.12. Wind contributes no additional energy-denominator MJ or ETS credit.
See [the wind accounting contract](WIND_ASSISTANCE.md) for equations, evidence
gates, baseline handling, economic assumptions and modelling boundaries.
