# Maritime Carbon

## Analyst operating guide

Review draft · Desktop application · Engine 6.5.2 · 9 September 2026

This guide explains how to build, check and interpret a fleet planning case in the FuelEU Maritime and EU ETS application. It is intended for analysts preparing budget comparisons and management recommendations. It describes the implemented model and its input requirements; it does not certify a fuel, approve a pool or replace a verifier's assessment.

The guide uses paragraphs, subparagraphs and bullets throughout. All worked examples are fictional planning assumptions. Default fuel prices and pathway values are illustrative, not current supplier quotations. References at the end provide the primary regulatory context; operational details describe this version of the application.

## 1. Start with the decision you need to make

### 1.1 Define a consistent comparison

Decide whether the question concerns the coming reporting year, a multi-year budget, a fuel conversion, shore power, or purchasing FuelEU surplus. Write down the common service requirement before changing fuels: the same annual voyages and transport activity must be supported in every strategy. Otherwise, an apparent saving may reflect less activity rather than a better compliance choice.

The app compares total modelled cost: purchased fuel, shore electricity, ETS allowances, FuelEU penalties, external pooling, incremental investment and operating costs, and other fleet costs. It ranks the lowest evaluated present cost over the selected reporting horizon. A higher fuel bill can therefore be economical if allowance and FuelEU settlement savings exceed it.

The app evaluates one nominated alternative fuel system per vessel in each case. It chooses which existing fuel, voyage and sea-leg category to replace and how much to replace. To compare HVO against FAME on the same vessel, duplicate the case, change the nominated alternative and its relevant assumptions, and run a separate comparison. Different vessels in one case can nominate different alternatives.

### 1.2 Prepare the input pack

- Annual fuel consumption by vessel, voyage identifier, fuel and operating category, including existing pilot fuel and berth consumption.
- The fuel library: delivered prices, lower calorific values, lifecycle and combustion factors, sustainability documentation and annual supply limits.
- Vessel characteristics, engine categories, blend or substitution limits, relative efficiency, pilot requirements and any conversion costs.
- Shore-power compatibility, eligible berth loads, generator and connection efficiencies, electricity tariffs and incremental costs.
- The reporting horizon, allowance-price assumptions, discount rate, verified ship-specific opening banks and immediately preceding penalty history.
- Any external pool quotation, its price unit and available annual surplus, plus notes supporting the scope assumptions.

### 1.3 Keep units consistent

Enter percentages as ordinary percentages in the interface: 80 means 80%, not 0.8. Fuel quantities and fuel prices use metric tonnes. Energy content is in MJ per tonne, not MJ per kilogram: 42.7 MJ/kg equals 42,700 MJ/tonne. Shore electricity uses MWh. FuelEU pool prices are per tonne of compliance balance, while EUA prices are per tonne of ETS CO2-equivalent emissions; these are different quantities.

## 2. Access, cases and saved reports

### 2.1 Sign in and choose the right workspace

Use the account supplied by your administrator. A company administrator manages colleagues, an analyst can edit and calculate, and a viewer can read and export. Company access and vessel limits must permit the intended work. The public example fleet is a demonstration, not your company's stored case.

The overview provides access to decision cases and saved reports. Open a case to edit assumptions or vessels. Open a report to inspect an immutable calculation snapshot. These serve different purposes: changing today's case does not change a report already produced from an earlier revision.

### 2.2 Create, duplicate and revise

Choose New decision case and give it a name that identifies its purpose, fleet and assumption set. Duplicate a case for a controlled alternative such as another fuel technology or pooling quote. Keep the service demand, reporting period and unrelated assumptions constant when comparing duplicates.

Saving a case, vessel or fuel assumption advances the case revision. If the app reports that the case changed in another session, reload before saving or calculating. This protects against overwriting another analyst's inputs. After all changes, choose Compare strategies to create a new report. Do not expect the old report to refresh automatically.

### 2.3 Account administration

Company administrators create users with a username, work email, role and initial password. The role determines access, not calculation assumptions. Users can change their own password through Account. Deactivating a colleague preserves historical reports. Analysts should request administrator help for account or access problems rather than creating duplicate identities.

## 3. Decision-case fields

### 3.1 Decision case name

Use a descriptive title such as “2026 budget — two tankers — HVO quoted supply”. The name identifies the case and is captured in each report. It does not change any calculation. Include a concise assumption label rather than putting lengthy evidence in the title.

### 3.2 First reporting year and last reporting year

These are emissions reporting years, not the later dates when allowances or penalties are paid. The supported range is 2025–2050, with the last year no earlier than the first. A single-year case is easiest to reconcile; a multi-year case captures modelled target changes, banking, penalty history, escalated prices and discounting.

Annual consumption and selected operating quantities repeat in every reporting year. The app does not optimize a different fuel mix or a later conversion date for each year. Initial investment is charged in the first reporting year when the corresponding action is selected. Use separate cases for materially different future activity plans.

### 3.3 EUA price and annual EUA price change

EUA price is the allowance-budget assumption in EUR/tCO2e for the first reporting year. Enter a reviewed budget, forward assumption or quote and record its basis in your working papers. The app has no live allowance-price feed. Changing this price affects ETS expenditure, not the physical emissions calculation.

Annual EUA price change compounds from the first reporting year. For example, EUR 90 with 3% growth becomes EUR 92.70 in the second year. Enter 0% for a constant price path. The model applies the ETS reporting-year phase-in and the entered voyage scope separately from the price assumption.

### 3.4 Annual fuel and electricity price change

This common escalation rate applies to fuel-library prices and the shore-electricity price. It compounds annually from the first reporting year. It does not increase fuel quantities or the external-pool price. If you need different price trajectories for different fuels, use separate scenario assumptions; this version has one common escalation rate.

### 3.5 Future cost discount rate

The discount rate expresses future costs in first-year present-value terms. At 7%, a EUR 107 cost one year after the first year contributes EUR 100 to present cost. The first reporting year's cost is not discounted. A 0% rate makes present cost equal the undiscounted total. Escalation changes the future cash cost; discounting changes its weight in today's comparison.

Use the same nominal or real basis consistently across prices, escalation and discounting. The app does not make that economic choice for you. For a one-year case, changing the discount rate has no effect on the ranking.

### 3.6 Include external pooling offers

Tick this to allow the pooling policies to use externally supplied FuelEU surplus under your entered terms. Unticking it prevents external purchases, while a self-sufficient internal fleet pool may still be evaluated. Permission to use pooling does not mean the selected strategy actually buys surplus; inspect its action remarks and ship ledger.

The implementation settles a complete modelled fleet pool when it is feasible. It does not search every possible subset of ships, sell surplus or negotiate a pool agreement. Opening banks are used by their own ships before pooling. A pool remains a planning assumption subject to the relevant commercial and verification arrangements.

### 3.7 Pool purchase price

Enter EUR per tonne of FuelEU compliance balance. Do not enter EUR per tonne of biofuel, EUR per EUA, or a quote per unit of energy without converting it to the required basis. The model multiplies externally purchased compliance balance by this price. Internal transfers do not incur a separate transfer price in the model.

The quote is constant over the reporting horizon; the fuel and EUA escalation fields do not escalate it. Put any fixed pool-arrangement or administrative charge into an appropriate additional-cost assumption and explain its treatment.

### 3.8 Available external surplus

Enter the maximum external surplus available to the whole fleet each year, in tCO2e of compliance balance. The cap is shared, not renewed separately for every vessel. Zero means no external capacity. Insufficient capacity can prevent the complete fleet pool from being used and leave ship-level penalties; partial purchase of all available surplus is not guaranteed.

### 3.9 Pool offer or assumption reference

Record the provider or internal source, quotation date, applicable years, unit, capacity and any conditions material to the estimate. An enabled external-pool assumption requires a reference. For an exploratory case, label it clearly as an unconfirmed planning assumption. Entering a reference does not authenticate an offer or execute a purchase.

### 3.10 Shore electricity price

Enter EUR/MWh of purchased shore electricity. Include applicable energy and usage charges in the assumed tariff; capture separate fixed incremental costs in the OPS cost fields. Purchased electricity depends on the berth fuel energy removed, generator efficiency and shore connection efficiency. A cheap tariff alone cannot enable shore power on an incompatible vessel.

### 3.11 Other fleet costs

This is an annual EUR amount applied equally to every strategy, such as common verification or administration costs. It changes total expenditure and percentage savings, but normally not the ranking because all options receive the same amount. Technology-specific costs belong in that vessel's fuel-system or OPS fields rather than here. This amount repeats without the fuel-price escalation rate.

### 3.12 Voyage-scope confirmation and scope notes

Confirm scope only after reviewing the actual routes and applicability for both regimes. The app uses the same ordinary-EU category weights for FuelEU and ETS: 100% for intra-EU sea and EU berth, 50% for EU/non-EU sea and 0% for outside-scope sea and non-EU berth. The confirmation records your review; it does not investigate port calls or resolve exceptions automatically.

Use Scope and planning notes for the source of the annual consumption allocation, route assumptions, excluded activity and any qualifications. EEA timing differences, special ports, transhipment exclusions and derogations require separate assessment. The legal regimes have different boundaries; a convenient consumption category is not proof of applicability.

### 3.13 Possible RFNBO requirement from 2034

For a horizon reaching 2034, “How to include this possible requirement” offers three planning treatments. The default shows potential shortfall without adding a penalty. “Assume it applies” adds a stress-test cost using your price-difference factor. “Assume it does not apply” adds no such cost. Reports may show the potential energy shortfall under all three treatments.

“Assumed shortfall cost” is EUR per 41,000 MJ. It is the Pd factor used with the missing RFNBO energy divided by 41,000 MJ, followed by any modelled consecutive-penalty uplift. It is not an official fixed penalty rate or a price per tonne of fuel. An active assumption requires a value, and a non-default future assumption requires a reason or source reference.

The conditional requirement, possible equivalent-fuel routes and final treatment need separate regulatory assessment. The model does not settle this separate energy shortfall using a ship's ordinary GHG bank or pool. A “no residual GHG-intensity deficit” result may still carry an RFNBO shortfall or an unpriced-scope warning. See the Commission FuelEU Q&A in the references.

## 4. Vessel identity and consumption

### 4.1 Vessel name, IMO number, ship type and gross tonnage

Vessel name must be unique within the case so the analyst can trace decisions and ledgers. The optional IMO number is checked for its seven-digit checksum when entered; use real identifiers only for real vessel cases. Leaving it blank is suitable for a fictional planning vessel.

Ship type is cargo/bulk carrier, tanker, container or passenger. It influences the model's scope warnings, including its treatment of future shore-power obligations. Gross tonnage is GT, not deadweight or displacement. The implemented threshold is above 5,000 GT for FuelEU and at least 5,000 GT for ETS for its supported ship types. A ship at exactly 5,000 GT is therefore treated differently under the two calculations.

### 4.2 Voyage

Voyage 1–100 is an analyst-assigned grouping identifier. It preserves which annual consumption belongs together and appears in replacement remarks. It does not define actual origin/destination ports, dates or the number of repetitions. If Voyage 1 represents a repeated route, enter its total annual consumption, not just one sailing's tonnes.

Use a consistent naming convention outside the app, for example “Voyage 1 = annual Rotterdam–Hamburg service”. The optimizer may recommend a different replacement fraction on each voyage and category. It does not reschedule voyages or verify that fuel can actually be bunkered at the proposed location.

### 4.3 Voyage or berth category

- Intra-EU sea voyage: enter all fuel consumed on the relevant sea activity; the model gives it 100% regulatory scope.
- EU/non-EU sea voyage: enter the full physical tonnes, not half. The app applies the 50% regulatory weight itself.
- Other sea voyage: physical fuel is purchased and counted in the vessel's sea-service demand, but its modelled regulatory scope is zero.
- EU berth: enter eligible EU port consumption separately from sea fuel. Shore power can replace the eligible share of these rows.
- Non-EU berth: fuel cost remains included, but the model applies zero regulatory scope and does not replace it with OPS.

Regulatory coverage scales the applicable emissions and energy, not the supplier's fuel invoice. For example, 100 tonnes on an EU/non-EU leg still costs the price of 100 tonnes.

### 4.4 Fuel type and annual tonnes

Choose the current physical fuel and enter annual metric tonnes for that voyage/category. Include existing MGO pilot as its own MGO consumption row, in the category where it is actually used. Do not count it again as main fuel. Several different fuels may appear on the same voyage.

Use Add another fuel to create another row and Remove to delete an unwanted row before saving. Combine duplicate rows for the same voyage, fuel and category. The interface supports up to 100 consumption rows per vessel. Fuel names such as HVO or FAME do not automatically establish eligibility; review the fuel library before calculating.

### 4.5 EU berth replaceable by shore power

This row-level percentage overrides the vessel's default for that EU berth row. Blank means use the default; zero explicitly means no replacement. Exclude boilers and other loads that the connection cannot replace. The value applies only to EU berth fuel, not sea fuel or non-EU berth consumption.

For example, if a 100-tonne EU berth MGO row has 60% replaceable share, selecting OPS removes 60 tonnes from that row. It does not mean that the optimizer will independently choose any percentage between zero and 60%; OPS is an on/off vessel choice using the entered eligible shares.

### 4.6 Excel import and legacy CSV fields

Older cases and the basic CSV may use Current fuel at sea, Annual sea fuel, Annual EU berth MGO, default intra-EU and EU/non-EU percentages, and separate Current annual sea MGO pilot. These quantities are converted to consumption rows when the vessel is edited. Legacy voyage percentages describe shares of fuel consumption, not shares of voyage counts. Any remaining sea share is outside scope.

Download the Excel fleet template from Import vessels. Fill Vessels with one row per ship and a unique vessel_id. Fill Consumption with one row per vessel, voyage, category and current fuel, repeating the exact vessel_id to link the rows. Enter full annual physical tonnes; do not halve EU/non-EU quantities. The app applies coverage itself. MGO is the MGO / LSMGO entry; LSMGO is also accepted on import. Percentages are numbers from 0 to 100: enter 30 for 30%. Leave the shore-power share blank or zero when no OPS replacement is planned, and always for non-EU-berth categories.

The workbook contains detailed Instructions, field comments, drop-down lists and a separate Example sheet. Only Vessels and Consumption are imported. Both input sheets start blank; copy the example only if you want to try it. Preserve the sheet names and exact headers in row 1. Use values only, with no formula cells, total rows or duplicate vessel/voyage/category/fuel rows. Combine duplicate quantities before upload.

Save as .xlsx, up to 2 MB. Each upload supports up to 20 vessels and 2,000 consumption rows, subject to the company's remaining vessel limit and at most 100 distinct voyage/fuel groups per ship. Import appends ships and retains the existing fleet; uploading twice adds the ships twice. Validation is all-or-nothing. Prices, years, regulatory scope, technical confirmations and fuel eligibility remain in the app. Review every imported vessel before comparison: alternative compatibility and OPS readiness start unconfirmed.

The optional row-based UTF-8 CSV supports the same voyage/leg/fuel structure, up to 512 KB, with identical vessel details repeated on every row for each vessel_id. The original 11-column CSV remains supported up to 64 KB and 20 vessels. Only that older format imports one sea fuel, sea and berth totals and voyage percentages, which can then be expanded in the vessel editor.

## 5. Alternative-fuel and engine fields

### 5.1 Alternative to evaluate

This is the alternative system considered for the vessel. It is separate from current consumption rows. Choosing an alternative does not compel its use. If the current fuels remain cheaper, the result can retain them. The optimizer also excludes substitution when compatibility, eligibility or supply requirements prevent it.

### 5.2 Maximum alternative energy share

This is a cap on the fraction of the vessel's original total sea-service demand replaced, measured using original fuel energy. It is shared across all current sea fuels and legs, including current pilot demand. A 10% ship-level cap does not impose a 10% limit on each row: a small row can be fully replaced if the total stays within the cap.

It is not a Bxx mass- or volume-blend specification. At a relative energy requirement other than 100%, it is also not simply the alternative's thermal-energy share of the resulting fuel mix. Translate any manufacturer blend restriction into an appropriate service-share cap and verify the selected row-level quantities remain operable.

### 5.3 Technical compatibility and blend-limit confirmation

Tick this after reviewing the nominated alternative against the engine, storage, fuel handling and applicable operating restrictions. Without it, the optimizer keeps current sea fuels. The fuel-library eligibility checkbox is an independent gate: a certified fuel cannot overcome a vessel's incompatibility, and a compatible vessel cannot establish a fuel's sustainability status.

### 5.4 Current methane engine, berth methane engine and alternative methane engine

Select the relevant consumer class wherever LNG, bio-LNG or e-LNG is used. The app offers Otto dual-fuel medium speed, Otto dual-fuel slow speed, Diesel dual-fuel slow speed and lean-burn spark ignition, with its versioned methane-slip defaults. Sea and berth engines may have different classes. The alternative engine describes the nominated methane system, not necessarily the existing engine.

Methane slip changes ETS CO2-equivalent emissions and FuelEU intensity; a low gas price does not establish a low overall compliance cost. The current model applies one current sea class, one berth class and one alternative class per vessel. It does not resolve multiple engines or load-dependent slip within the same category. The methane fuel-library combustion CH4 field excludes slip because the engine adds it separately.

### 5.5 Alternative system MGO pilot energy share

Enter pilot as a percentage of the alternative system's total thermal input. It is included within that system, not added on top of a 100% alternative-fuel allowance. If the alternative system needs 100,000 MJ and pilot share is 3%, MGO supplies 3,000 MJ and the nominated alternative supplies 97,000 MJ.

Use an engine/load-dependent reviewed estimate. The model supports MGO as alternative pilot; it does not support another pilot fuel. Current pilot already entered in the baseline consumption rows is a separate quantity and must not be confused with the replacement system's new pilot.

### 5.6 Alternative system energy requirement

This percentage compares the alternative system's thermal input with the baseline thermal input needed for the same service. At 100%, energy input is conserved exactly. At 80%, the model assumes the alternative needs 20% less total thermal input, including its pilot. A value above 100% means more input is needed. This is a relative input requirement, not an absolute engine efficiency.

For equal useful service, the ratio can be derived from baseline efficiency divided by alternative-system efficiency. For example, 40% divided by 50% gives an 80% energy requirement. Use comparable operating conditions and include the complete system boundary; the app does not derive this from an engine selection.

The calculation is performed on the same selected leg: removed tonnes multiplied by their LCV gives removed energy. That energy multiplied by the relative requirement gives replacement-system energy. Split it into alternative and MGO pilot energy, then divide each by its own LCV to obtain added tonnes. Equal service does not generally imply equal fuel tonnes.

### 5.7 Fuel conversion and downtime investment

Enter the full incremental first-year investment, including relevant conversion and downtime cost. It is charged when any sea-fuel switching is selected, even if the replacement percentage is small. It is not scaled by the selected blend. Enter zero when justified for an already equipped vessel, rather than silently omitting a necessary conversion.

### 5.8 Fuel system extra annual operating cost

Enter the additional annual EUR cost that applies whenever the alternative system is used, such as incremental maintenance or fuel handling. It is charged in every reporting year with switching and is not scaled by replacement share or escalated by the fuel-price rate. Avoid duplicating fuel purchase costs, which the engine calculates directly from tonnes and library prices.

### 5.9 Reviewed-system confirmation and technical reference

The system-review checkbox records review of fuel handling, pilot demand, relative efficiency and investment assumptions. The technical reference should identify the engine/system basis, relevant approval, cost source and operating restrictions. Methane, methanol, ammonia and hydrogen pathways require this review for applicable use. Merely selecting a consumer class is insufficient.

## 6. FuelEU history and shore power

### 6.1 Opening FuelEU bank

Enter verified surplus belonging to this vessel at the start of the first reporting year, in tCO2e of compliance balance. It is not a fuel inventory, EUA holding or company-wide cash asset. There is no pre-2025 FuelEU bank. The app first uses a ship's bank against its own deficit and carries unused surplus forward.

The optimizer does not sell a remaining bank or assign it a terminal cash value. Consequently, a horizon ending with substantial surplus can make extra fuel purchases look uneconomic even if you expect future value. Inspect the closing-bank ledger and choose a suitable horizon.

### 6.2 Immediately preceding consecutive penalty years

Enter the uninterrupted number of penalty years immediately before the first reporting year, not the total number of past penalties. The model increments the streak when the ship incurs a relevant modelled penalty and resets it when that year's relevant deficits are settled. The history cannot predate the first FuelEU reporting year. Incorrect history can overstate or understate future penalties.

### 6.3 Evaluate shore power

Tick this only when both vessel and intended ports can support the assumed connection and service. It permits the optimizer to compare OPS off and on. It does not force OPS selection or establish that every port call is eligible. Fuel switching and shore power can be chosen together.

### 6.4 Default EU berth share replaceable by shore power

This percentage applies to EU berth rows that leave their row-level percentage blank. Explicit row percentages take precedence. For a realistic estimate, identify the electrical loads and time at equipped berths; do not assume all berth fuel can be replaced if boilers or other independent loads remain.

### 6.5 Generator electrical efficiency

This converts the thermal energy in removed berth fuel to the useful electrical energy formerly produced onboard. One generator-efficiency assumption applies across all replaced EU berth fuels. At 40%, removing 100,000 MJ of fuel energy corresponds to 40,000 MJ of useful electrical demand.

### 6.6 Shore connection efficiency

This accounts for losses between purchased electricity and useful onboard electricity. Purchased MWh equals removed fuel MJ multiplied by generator efficiency, divided by connection efficiency and by 3,600. A lower connection efficiency therefore increases purchased electricity. Enter 95 for 95%, not 0.95.

### 6.7 OPS initial investment and extra annual operating cost

Initial investment is the full incremental first-year EUR cost if OPS is selected. Extra annual operating cost is charged in each selected year; electricity purchases are calculated separately. Neither amount is scaled automatically by the berth replacement share. Use consistent ownership and charter-party assumptions to decide which costs belong in the company comparison.

## 7. Review every fuel-library field

### 7.1 Price and annual fleet supply cap

Fuel price is EUR per delivered tonne in the first reporting year. It applies to all use of that fuel code across the case, including existing consumption, substitution, relevant berth use and MGO pilot. It is not a quote per tonne of energy or per tonne of avoided emissions. Fuel-price escalation is applied later by the scenario.

The annual supply cap is shared across the entire fleet and all those uses. Blank is unconstrained; zero makes the fuel unavailable. The cap is on total fuel use, not only the incremental alternative purchase. If baseline consumption itself exceeds a cap, the app rejects the comparison and asks for a coherent baseline/cap rather than constructing a reference it cannot supply.

### 7.2 Lower calorific value

Enter MJ per tonne on the correct lower-heating-value basis. This determines energy demand, substitution tonnes and intensity weighting. Do not substitute higher heating value or confuse MJ/kg with MJ/tonne. Methane pathways use the model's fixed default LCV and may show a disabled field. Different HVO and FAME LCVs explain why their purchased tonnes differ for the same displaced service.

### 7.3 Well-to-wake intensity

For applicable oil/biofuel pathways, enter the complete lifecycle intensity in gCO2e/MJ, including the relevant non-CO2 contribution. Use a value supported by the supplier pathway and applicable accounting basis. It affects FuelEU performance; lowering it does not independently zero the fuel's CO2 under ETS.

The value represents the fuel code throughout the case. If batches have different lifecycle values or only some quantities qualify, do not present the whole code as a single certified low-carbon batch without reconciling those differences. This version does not provide separate batch-level certification or blended renewable-fraction inputs.

### 7.4 FuelEU well-to-tank factor

For methane and RFNBO pathways, the form uses WtT rather than a directly entered complete WtW value. The engine adds the relevant physical combustion and methane-slip contribution. Enter the certified FuelEU-adjusted WtT on the accounting basis expected by this model, including any applicable carbon-accounting adjustment. Entering a complete WtW value here would count part of the emissions twice.

An adjusted WtT can be negative where the applicable pathway accounting requires an adjustment; it is not permission to invent an offset. Review the certificate and methodology together. Fossil LNG uses the fixed WtT default implemented in the rules, so that field cannot be freely varied.

### 7.5 Physical CO2 factor

Enter tonnes of physical CO2 per tonne of fuel before any ETS renewable zero-rating. This is distinct from lifecycle intensity. The ETS calculation zero-rates eligible renewable CO2 through its separate checkbox; it does not require you to overwrite the physical factor with zero. Some pathway defaults are locked to preserve the model's consumer contract.

### 7.6 Combustion CH4 factor and combustion N2O factor

Both are tonnes of gas per tonne of fuel, not gCO2e/MJ. The app converts them to CO2-equivalent using its versioned factors. Do not put methane slip into the combustion CH4 field for LNG: slip is calculated from the vessel's selected methane engine. CH4 and N2O remain included in ETS for reporting years from 2026 even when renewable CO2 is zero-rated.

Blank means unknown where measured pathway factors are required. Enter zero only when supported. In particular, a fuel containing no carbon does not automatically prove zero N2O from combustion. Hydrogen fuel-cell and hydrogen combustion pathways are separate selections with different evidence requirements.

### 7.7 RED sustainability and FuelEU pathway eligibility

This checkbox records your review of the renewable fuel's sustainability and applicable FuelEU pathway. It is required for the optimizer to use that renewable alternative. A low entered WtW value does not override an unticked eligibility box. Existing renewable fuel consumption also requires valid pathway/evidence inputs before comparison.

Record supplier proof and the supported feedstock/production route. This application does not support food/feed crop biofuels as eligible alternative pathways. The checkbox is the analyst's assertion based on evidence, not a certification generated by the app.

### 7.8 Separately confirm ETS CO2 zero-rating eligibility

Tick this only after checking that the fuel qualifies for its CO2 contribution to ETS allowance emissions to be treated as zero. For HVO/FAME, the supplier's Proof of Sustainability should support the applicable criteria and relevant quantity. A renewable fuel name, low lifecycle number or FuelEU tick alone does not establish that entitlement. The same evidence can support both reviews; “separately” does not necessarily require a second certificate.

When ticked for an eligible renewable fuel code, the calculator removes its CO2 contribution from the ETS calculation. When unticked, it uses the physical CO2 factor. CH4 and N2O, including methane slip where applicable, remain included. The physical fuel can still emit CO2, and its FuelEU lifecycle intensity is not changed by this checkbox. The switch applies to the whole represented fuel quantity, so mixed eligible/ineligible batches require separate treatment outside this simple assertion. See Commission guidance section 5.2.2.

### 7.9 Measured factors and pathway evidence reviewed

For methanol and ammonia combustion and hydrogen internal-combustion pathways, this confirms that required CH4/N2O factors and supporting evidence have been reviewed. It does not turn blank values into zero. Complete the factors and reference together before enabling the pathway. The field appears only where the model requires it.

### 7.10 Elective FuelEU RFNBO reward through 2033

When enabled for a qualifying RFNBO, the model doubles that fuel's eligible contribution to the intensity denominator through 2033; from 2034 the multiplier is one. It does not double physical energy, halve the fuel invoice or zero ETS gases. This is a fixed assumption, not an optimized choice. Duplicate the case with the reward disabled if you need to examine its influence.

### 7.11 Evidence and pathway reference

Record the supplier/batch reference, relevant quantities and validity, feedstock or production route, pathway factors, certification basis and monitoring-plan reference. For RFNBOs, include the applicable production/electricity and greenhouse-gas-saving evidence. For combustion pathways requiring measured factors, identify the measurement or technical source. The text field records a reference; it does not upload, authenticate or approve the underlying documents.

### 7.12 Add available fuel pathways

An older case may have a smaller fuel library. Use the case's Add available fuel pathways action to add supported pathways without replacing existing prices or evidence. Review each new pathway before use. Saved reports retain their original fuel-library inputs and rules; extending today's case does not reinterpret those snapshots.

## 8. Run and interpret the comparison

### 8.1 Before clicking Compare strategies

- Reconcile annual tonnes with the source consumption records. Confirm that EU/non-EU quantities have not already been halved.
- Check that pilot and berth fuel are each counted once, the voyage/category mapping is intentional, and the sea-service demand is comparable.
- Confirm alternative compatibility, evidence, energy requirement and pilot assumptions; check full fixed costs even for a small replacement.
- Check shared fuel supply and external-pool capacity against the whole fleet, including baseline use.
- Review banks, penalty history, horizon and scope confirmation. Save all edits, then calculate the current revision.

### 8.2 The four policy evaluations

Current fuels / settle deficits is the reference: keep baseline consumption and settle ship-level deficits after the automatic bank treatment. Current fuels / pooling allowed retains fuels but permits feasible pooling. Fuel choices permits alternative sea-fuel substitution and, where enabled, shore power without pooling. Fuel choices / pooling allowed combines those operating choices with feasible pooling.

Policy names describe permissions. The large recommendation names what the evaluated result actually does. A pooling-enabled policy can buy no external surplus. Shore electricity is an operating purchase and must not be interpreted as pooling expenditure. Exactly matching outcomes may be grouped; differences in the detailed operating choices or cost ledgers keep evaluations separate.

### 8.3 Lowest evaluated cost and savings

The app ranks the present cost of the evaluated strategies. Savings are measured against the current-fuel/ship-settlement reference, not necessarily against last year's invoice or your existing external pool. Undiscounted total is the sum of nominal modelled costs over the horizon. In a one-year case the present and undiscounted totals coincide.

“Lowest evaluated” is deliberate. The search starts with a fuel-level incumbent, then varies voyage/fuel/leg allocations using sampled ranges, continuous refinement, compliance candidates and supply boundaries. It also transfers selected energy between legs. The bounded search does not guarantee the global mathematical minimum across all fleet allocations, technologies or voyage schedules.

### 8.4 Strategy remarks and operating choices

Read the selected vessel, voyage and category together. A remark such as “Voyage 1 · Intra-EU sea: replace 21.876 t/year of MGO with 21.230 t/year of HVO” describes an annual same-leg substitution. It does not instruct you to spread the replacement proportionally across the vessel's other legs. The quantities repeat for each reporting year.

The operating-choice section also shows retained current fuels, total alternative tonnes, service replaced, OPS status and any pilot requirement. Summary tonnes are rounded for readability; use the JSON audit's unrounded leg quantities when reproducing a calculation or sizing a precise compliance-closing substitution. Re-evaluate any practical purchase rounding rather than assuming it preserves the exact balance.

First-step comparisons are explanatory comparisons of equal original sea-energy steps with other ships and OPS held fixed. Their fuel-level illustration uses proportional leg allocation. “Replace first” is not a chronological conversion schedule or a separate independent instruction. The complete selected voyage-leg quantities determine the recommendation.

### 8.5 Annual cost outlook and cost breakdown

The chart compares selected-strategy and reference annual costs. Click another strategy to change the selected view. Use the annual cost breakdown for exact reconciliation of fuel, electricity, ETS, FuelEU penalties, pooling and implementation/other costs. Large first-year costs can come from investments charged in full when a technology is selected.

The interface rounds currency and may abbreviate thousands or millions. The audit and CSV retain more precision. Tiny settlement residuals below the action-reporting tolerance are not labelled as a separate pooling action, while their raw ledger values are retained.

### 8.6 Ship-by-ship compliance ledger

Attained intensity is the modelled gCO2e/MJ after fuel and energy treatment; target intensity is the reporting-year limit. A positive raw compliance balance is surplus and a negative balance is a deficit. Bank open, bank used and bank close track the vessel's own carried surplus. Pool transfer records internal movements; a negative donor transfer supplies other ships and a positive recipient transfer receives surplus. Pool buy is external purchase. Residual deficit is what remains for penalty treatment.

Reconcile the sequence, not just the raw balance: a ship can start with a negative annual balance and end without a penalty because its own bank or a feasible pool covers it. Conversely, a fleet-level surplus does not imply every ship is settled in a policy that prohibits pooling.

### 8.7 Fuel pathway, methane and RFNBO ledger

Use this section to inspect current fuel tonnes by voyage/category, berth fuel, alternative tonnes, separate MGO pilot, methane-slip assumptions, scoped CH4 and RFNBO energy measures. Physical energy and rewarded energy are different quantities. The possible RFNBO shortfall is an energy measure, not a tonne-of-CO2 balance.

A partial-cost-scope warning takes priority over a headline saving. Mandatory OPS port-call penalties, unresolved RFNBO costs or other excluded mechanisms may remain unpriced. Do not describe the selected cost as complete compliance expenditure when the report explicitly says it is partial.

### 8.8 Sensitivities

The report reprices the evaluated strategies under EUA minus/plus 20%, pool price plus 20% and alternative fuel price plus 20%. It retains each strategy's saved voyage-leg allocations. This identifies which saved strategy is cheapest under the changed price; it does not rerun the optimizer to find a newly sized mix.

For a decision that depends strongly on a sensitivity, duplicate the case, enter the changed assumption and run a new comparison. That allows the fuel/leg quantities and other permitted operating choices to adapt. Compare the new report with the original using consistent reference assumptions.

## 9. Worked desktop exercises

### 9.1 One vessel: concentrate a small HVO substitution

Create a fictional 2026-only cargo-vessel case. Set EUA price to EUR 85/tCO2e, enable external pooling at EUR 190/tCO2e balance with 100,000 tCO2e annual capacity, and enter a clear fictional reference. For the vessel, confirm HVO compatibility, allow up to 100% original sea service replacement, use 100% relative energy requirement, zero alternative pilot and zero incremental fuel-system costs. Leave OPS disabled.

Enter Voyage 1 HSFO: 200 tonnes intra-EU and 800 tonnes EU/non-EU; MGO: 80 tonnes intra-EU, 20 tonnes EU/non-EU and 50 tonnes EU berth; VLSFO: 10 tonnes intra-EU and 50 tonnes EU/non-EU. Retain the library's illustrative prices: HSFO 470, VLSFO 575, MGO 720 and HVO 1,550 EUR/tonne. For this exercise only, record assumed HVO evidence and enable both renewable eligibility and ETS CO2 zero-rating. Retain its illustrative WtW of 20 and LCV of 44,000 MJ/tonne.

With these inputs, the checked regression result replaces approximately 21.875943 tonnes of MGO with 21.229608 tonnes of HVO on Voyage 1's intra-EU sea category. Total annual cost is approximately EUR 833,155.12, compared with EUR 834,499.72 for the current-fuel external-pooling option. The replacement supplies the removed energy on that same leg and closes the modelled GHG deficit without pooling. These figures are reproducibility examples, not forecasts for a real vessel.

### 9.2 Two vessels: test scarce supply, a bank and OPS

Duplicate the exercise and nominate FAME for both fictional ships. Review its separate illustrative evidence and retain its own price/LCV rather than copying HVO values. Give the first vessel an additional Voyage 2 with 40 tonnes of MGO outside scope and 10 tonnes at non-EU berth. Set a shared FAME supply cap of 15.123456 tonnes/year.

Add a second fictional vessel with Voyage 2 VLSFO of 70 tonnes intra-EU and 300 tonnes EU/non-EU, and Voyage 3 MGO of 40 tonnes intra-EU and 70 tonnes EU berth. Give that vessel a 5 tCO2e opening bank. Enable OPS, set the EU berth row's replaceable share to 65%, and use explicitly reviewed generator, connection and incremental-cost assumptions. In the release fixture these are 40% generator efficiency, 95% connection efficiency and zero OPS investment/annual cost, with EUR 160/MWh electricity.

Check that total FAME use across ships stays within the common cap; a cap is not a per-ship entitlement. Inspect whether FAME is concentrated on the second ship, whether OPS changes its balance, and whether its surplus then helps the first ship through internal pooling. Disable external pooling and rerun to distinguish internal feasibility from an external purchase assumption. Change one assumption at a time and preserve each report.

### 9.3 Gas and synthetic-fuel exercises

For an LNG/bio-LNG comparison, select the actual current and alternative methane consumer classes and review pilot/efficiency inputs. Compare otherwise identical cases with and without ETS zero-rating for the eligible renewable gas. Methane slip and N2O remain, so zero-rated CO2 does not make the entire ETS ledger zero.

For methanol, ammonia or hydrogen, start with a separate duplicate and complete technical review and the required measured-factor evidence. Do not copy oil factors into these pathways. A 2033–2035 case is useful for seeing the RFNBO reward expire and the separate future-subtarget assumption appear. These exercises test understanding of the model; they do not establish that a proposed conversion is technically or commercially available.

## 10. Export, review and hand over

### 10.1 Download CSV

The CSV includes the evaluated strategies and their ship/year cost and compliance records, plus explicit company other-cost rows. Some fields contain JSON describing detailed fuel inventories and voyage-leg replacements. It is an audit-friendly export, not a flat bunkering instruction. Filter by strategy and reporting year before summing, and avoid double-counting different policy evaluations as if they were additional vessels.

### 10.2 Audit file

The JSON audit captures the input snapshot, results, input fingerprint, case revision, engine/ruleset version and source references. Keep it with supplier and technical evidence outside the app. It permits unrounded reconstruction of the displayed recommendation. A matching SHA-256 digest supports input traceability; it does not validate the truth of the inputs or prove regulatory compliance.

### 10.3 Print report and report retention

Print report invokes the browser print workflow. Select the strategy you want to present before printing and inspect the print preview. Saved reports remain accessible after later case edits. To reproduce an old result, use its saved inputs and engine context; the current case or current engine may produce different results.

### 10.4 Analyst review before management circulation

- State the case revision, reporting horizon and assumption date; distinguish illustrative prices from quotations.
- Explain the proposed vessel, fuel, voyage and category, and reconcile removed energy, added fuel and pilot.
- Separate nominal total, present cost, savings against the reference and actual external-pool expenditure.
- Check shared supply, berth operability, full fixed costs, banks and the limits of future assumptions.
- Include unpriced-scope warnings and material sensitivity findings alongside the recommendation.
- Retain the report, CSV/JSON and supporting evidence. Do not present a planning checkbox as verifier approval.

## 11. Common questions and model boundaries

### 11.1 Why is the nominated alternative not selected?

First inspect the exclusion notices: eligibility, required factors, compatibility, maximum share or zero supply can prevent substitution. If it is available, inspect full-horizon cost. The alternative can lose because of price, pilot demand, relative efficiency, fixed investment, existing banks or cheap pooling. A low WtW number alone is insufficient. Changing eligibility is not a legitimate way to force an economical answer without supporting evidence.

### 11.2 Why is one leg preferred?

A fully covered leg can deliver more modelled compliance benefit per tonne purchased than a half-covered or outside-scope leg. Fuel price, displaced LCV/intensity, system efficiency, vessel limits and fleet settlement also influence the choice. The optimizer retains each replacement on its original leg; it does not move renewable fuel onto a covered part of a voyage merely for accounting credit.

### 11.3 Why does a higher alternative share not always improve the recommendation?

Extra alternative fuel can cost more than the compliance benefit it adds. Once a deficit is closed, further surplus may only be banked without terminal value. Fixed conversion cost creates a jump when switching begins, and shared supply or pool feasibility can change the fleet outcome. Review the complete cost and bank position rather than maximizing renewable tonnes alone.

### 11.4 What is outside this version?

The model does not optimize voyage scheduling, bunkering ports, alternative technologies within one vessel/case, year-by-year conversion timing, borrowing, surplus sales or all possible pool subsets. It does not model all special geographic exemptions, mandatory OPS port-call penalties, mixed/load-dependent engines, non-MGO alternative pilot, batch certification, or the complete commercial and technical consequences of a conversion.

Current activity and selected quantities repeat annually. Some multi-year rules are stress assumptions rather than settled future tariffs. A bounded search can miss a better allocation, especially in complex fleets with interacting supply and pooling limits. Use the app to prepare a transparent comparison and direct further analysis, not to claim guaranteed global optimality.

## 12. References and version control

The following sources were consulted for the regulatory context. The guide's descriptions of field behavior, search limits, accounting sequence and exports are based on the application's engine 6.5.2, forms and release tests. Regulatory changes after the recorded ruleset date require review before use; the guide does not assert a new legal ruleset.

- European Commission, Maritime ETS general guidance, especially section 5.2.2 on sustainable-fuel CO2 zero-rating: https://climate.ec.europa.eu/document/download/31875b4f-39b9-4cde-a4e2-fbb8f65ee703_en?filename=policy_transport_shipping_gd1_maritime_en.pdf
- European Commission, Maritime ETS questions and answers, including reporting-year coverage and treatment of alternative fuels: https://climate.ec.europa.eu/areas-action/transport-decarbonisation/reducing-emissions-shipping-sector/faq-maritime-transport-eu-emissions-trading-system-ets_en
- European Commission, FuelEU Maritime questions and answers, including pooling and conditional RFNBO treatment: https://transport.ec.europa.eu/transport-modes/maritime/decarbonising-maritime-transport-fueleu-maritime/questions-and-answers-regulation-eu-20231805-use-renewable-and-low-carbon-fuels-maritime-transport_en
- Application regulatory basis and its primary legislative links: docs/REGULATORY_BASIS.md in the project repository.
- Project repository: https://github.com/nikelef/Maritime-Carbon

Review status: prepared for the owner's review. Before external distribution, confirm terminology, commercial assumptions, company-specific procedures and the intended scope of any compliance statements.
