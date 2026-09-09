# Filling the Maritime Carbon fleet import workbook

The app and workbook include these same instructions.

## START HERE

This workbook matches the app's consumption table: one row per vessel, voyage, operating category and current fuel. Only Vessels and Consumption are imported. Instructions, Example and Lists are reference sheets.

## 1. Enter vessel profiles

Fill Vessels from row 2, one row per ship. Assign a unique vessel_id and complete the identity, alternative fuel and maximum alternative share. The input sheets are blank so the example cannot be imported accidentally.

## 2. Enter consumption

Fill Consumption from row 2. Repeat the vessel_id from Vessels, select the voyage, category and current fuel, then enter annual tonnes. Multiple fuels on the same leg require separate rows.

## 3. Avoid double counting

A vessel/voyage/category/fuel combination may occur only once. Combine repeated quantities in that row. Do not add total rows to either input sheet. Do not also enter HVO replacement tonnes unless HVO is genuinely part of current baseline consumption.

## 4. Save and upload

Save as Excel Workbook (.xlsx). In the decision case, choose Import vessels, select this file and click Validate & import vessels. Import appends new vessels and keeps existing ones. Uploading it twice adds the ships twice; it is not an update operation.

## 5. Review in the app

Open each imported vessel and check all rows. Alternative compatibility and shore-power readiness start unconfirmed. Review engine class, existing pilot fuel, efficiency, investment costs, eligibility evidence and ship-specific FuelEU history before comparison.

## Limits and file structure

Use at most 20 vessel rows and 2,000 consumption rows, within the company's remaining vessel limit. Each vessel supports at most 100 distinct voyage/fuel groups. The .xlsx file limit is 2 MB. Preserve sheet names and row-1 headers; do not add data columns or password protection.

## Values and percentages

Enter checked values only in the input sheets. Paste special > Values if copying formulas. Blank rows are ignored. Use percentages as numbers from 0 to 100: type 30, not 0.30 or 30%. Use the drop-downs or exact supported labels. Do not halve EU/non-EU tonnes.

## Vessels — vessel_id

Your short ship identifier, 1–50 characters. Use it once in Vessels and repeat it exactly in Consumption. It links rows within this upload; it does not update an existing app vessel.

## Vessels — name and IMO

The vessel name shown in the app, 1–100 characters. Use a distinct vessel_id for every ship even if names are similar. Optional seven-digit IMO number, including its valid check digit. Leave blank for a planning vessel. Store as text; do not enter an invented IMO number.

## Vessels — ship_type

Choose cargo (including bulk carriers), tanker, container or passenger. Use the code in the drop-down, not the longer description.

## Vessels — gt

Gross tonnage as a whole number from 1 to 1,000,000. This is GT, not deadweight or fuel tonnes. The app uses it when assessing regulatory scope.

## Vessels — alternative

The one alternative fuel to evaluate for this vessel, such as HVO. Use a fuel code available in the target case. This nomination does not enable compatibility or confirm fuel eligibility.

## Vessels — max_alternative_pct

Maximum alternative sea-service energy share, 0–100. Enter 30 for 30%, or 100 to permit full replacement. This is a cap, not an instruction to buy that quantity and not a mass blend ratio.

## Consumption — vessel_id and voyage

Repeat the exact vessel_id from Vessels. Whole number 1–100. Use the same number for the sea and berth rows belonging to one voyage. Each vessel may have its own Voyage 1. All rows are annual input quantities for the case.

## Consumption — leg

Choose Intra-EU sea, EU/non-EU sea, Outside-EU sea, EU berth or Non-EU berth. Sea and berth are separate categories. Enter full physical fuel tonnes; the app applies coverage itself.

## Consumption — fuel

Current fuel consumed on this row. Use HSFO, VLSFO, MGO or another case-library code. MGO is the app's MGO / LSMGO entry; LSMGO is accepted and converted to MGO. Include current pilot fuel once in its actual row.

## Consumption — tonnes

Fuel mass consumed during the year on this vessel/voyage/category, from 0 to 10,000,000 tonnes. Enter numbers only, e.g. 1000 or 12.5. Do not enter energy, currency, a total for all fuels or coverage-adjusted tonnes.

## Consumption — eu_berth_ops_pct

Only for EU berth: the share of this row's fuel use that could be replaced by shore power, 0–100. Blank or 0 means none. Leave blank or 0 for every other category. OPS remains disabled until reviewed and enabled in the app.

## What remains in the app

Set reporting years, EUA and pooling prices, fuel prices, regulatory scope and pooling capacity in the decision case. These are not imported by this fleet workbook. Confirm FuelEU eligibility and ETS CO2 zero-rating separately in the fuel library.

## Worked example

Example shows one bulk carrier and Voyage 1: EU/non-EU sea 1,000 t HSFO + 100 t VLSFO + 50 t MGO; intra-EU sea 200 t HSFO + 50 t VLSFO + 50 t MGO; EU berth 30 t MGO. Total physical fuel is 1,480 t. HVO is the nominated replacement fuel; shore power is zero.

## To try the example

Copy Example's vessel row into Vessels row 2, then its seven consumption rows into Consumption rows 2–8. Copy values only, excluding headings and totals. For the video case, separately set 2026 only, EUA 85 and pooling 190 in the app, then complete the technical and fuel reviews.

## CSV compatibility

The optional row-based CSV uses one combined row per consumption entry: repeat identical vessel details each time. Its size limit is 512 KB. The old 11-column CSV remains supported up to 64 KB, but only that older format uses sea totals and voyage percentages.

## Reference

Maritime Carbon application input contract. https://github.com/nikelef/Maritime-Carbon — use the case's fuel library as the authority for available fuel codes. This workbook imports planning inputs; it does not certify compliance.
