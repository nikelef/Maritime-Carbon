# Commercial application rebuild

## Scope and decisions

The supported product is a Django application backed by a relational database. All
application code, tests and development/container entry points use Django.
Customer data remains in the relational database and is excluded from Git.

Implementation work:

- [x] Independent, versioned regulatory engine with strict validation and reference cases.
- [x] Ship-specific annual calculations, cash costs, banking, conditional pooling,
  compatible fuel substitution, shore power, and transparent strategy search.
- [x] Responsive fleet/scenario workflow with assumptions, comparison, CSV import and exports.
- [x] Password authentication, tenant isolation, roles, subscription entitlement,
  immutable calculation snapshots, and administrative account provisioning.
- [x] Regression/security checks, real-browser acceptance and deployment configuration/documentation.

Sources are checked against EU legal texts and Commission guidance on 2026-09-07.
Planning estimates are not verified compliance submissions. Unsupported exemptions,
engine pathways, and future conditional obligations must be visible to customers.

Commercial starting point: company subscriptions activated by the operator after
invoicing. Payment processing and live deployment require a provider/account/domain
and are not silently connected. Default fleet scope: conventional cargo/tanker ships.

## LNG and RFNBO restoration · engine 6.0.0

The initial customer rebuild narrowed the original fuel coverage too far. This
revision restores LNG, LBM and RFNBO pathways in the customer application, with
consumer-specific slip, certified FuelEU WtT, measured-factor gates and separate
ETS eligibility. Hydrogen combustion and fuel cells are separate choices.
Pilot fuel, relative efficiency and conversion/annual costs enter the optimization.
Future RFNBO subtarget costs are explicit stress-test assumptions, not invented
statutory tariffs. Existing cases extend their library only by a revision-checked
user action, and historical reports are not rewritten.

## Audit findings

1. Certified zero-rating erased CH4 and N2O, including from 2026.
2. Unused surplus was valued at the statutory penalty rate and deducted as cash.
3. Segment penalties and pooled annual fleet penalties conflated legal accounting units.
4. Repeated annual deficits lacked the ship-specific 10% penalty escalation.
5. Shore power replaced thermal fuel energy 1:1, omitted electricity cash cost, and
   double-counted added electricity in one output.
6. Alternative fuels were offered without technical compatibility or evidence gates.
7. Shared scenario JSON and plaintext authentication could not isolate customers.
8. Unbounded assumptions and optimistic defaults were presented as subscription ready.

The new application addresses these in a separate engine and tenant-aware workflow.
Regression tests use independent expected values for the current calculation contract.

Implementation verification is recorded in `VERIFICATION.md`. Production hosting,
PostgreSQL deployment validation and independent regulatory/security sign-off are
external launch requirements, not claims of this local implementation.

## Annual FuelEU attribution · engine 6.6.0

FuelEU now uses a separate annual lowest-WtW source allocator, covering both
alternative and conventional fuels. ETS, physical consumption, fuel purchases
and supply constraints remain proportional/physical. The continuous optimizer
checks attribution capacity boundaries and verifies compliance roots. Reports
and CSV/JSON expose source energy; saved earlier reports remain unchanged.
See REGULATORY_BASIS.md for the elected method and excluded activity.
