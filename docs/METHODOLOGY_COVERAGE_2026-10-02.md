# Rules & methodology coverage — 2 October 2026

The existing local guide contained a short wind section near the bottom, without
a section anchor or a link from the wind editor. It did not explain the full wing
setup workflow. Shore power, fuel eligibility, pooling and scope were embedded
in longer sections; financial escalation and saved-strategy sensitivities lacked
an explicit explanation.

The guide now contains 13 compact, independently expandable sections. Wings is
first, with a visible shortcut and direct URL `/methodology/#wind-assistance`.
The vessel's wind editor links to that explanation in a new tab, preserving
unsaved vessel inputs. A visible **Guide updated 2 October 2026** stamp identifies
the new page independently of the engine and regulatory source-review dates.

## Feature-to-guide check

| Section | Features and limits checked against implementation |
| --- | --- |
| Wings & wind-assisted propulsion | Retrofit/existing/none modes; reviewed propulsion shares and net savings per sea row; auxiliary demand; existing-baseline treatment; capital/annual costs; separate reward power/evidence; four reward bands; order relative to switching; package reconciliation; imports and fixed-performance limits. |
| Strategy search | Four policies; wind within the equipment policies; same-leg replacement; bounded grid/continuous search; extra all-wind starting point; fixed decisions; no global-optimum claim. |
| FuelEU Maritime | Ship threshold, intensity, physical compliance balance, GWP100, penalty and consecutive-year uplift, statutory target pathway. |
| EU ETS | Distinct GT boundary, proportional scope, 2025/2026 phase-in and gases, separate renewable CO2 treatment, reporting versus payment year. |
| Voyage scope & annual allocation | Sea/berth categories, purchase costs outside scope, pilot demand, physical leg assignment, optional reward-aware annual allocation and its inventory boundaries. |
| Fuel eligibility, switching & supply | Complete WtW versus WtT plus physical factors; evidence gates; separate ETS eligibility; measured-factor requirements; compatibility, relative energy, alternative pilot, fleet caps and conversion costs. |
| LNG consumers & methane slip | Current sea/berth/alternative defaults, slipped versus combusted fractions, distinct GWP values, absence of measured/mixed/load-dependent inference. Displayed defaults come from the same rule data as the engine. |
| Shore power | Readiness, row/default replaceable shares, generator and connection efficiencies, MWh conversion, full investment, annual costs, zero regulatory intensity and port-call obligation limitations. |
| RFNBO pathways | Consumer-specific inputs, denominator reward through 2033, physical balance energy, conditional 2034 subtarget/Pd assumptions, excluded OPS, unimplemented RFNBO-specific flexibility. |
| Banking, pooling & borrowing | Ship banks; model restriction on bank-funded/subset/partial pools; current surplus and external capacity; no optimized borrowing or terminal surplus cash value. |
| Costs & present value | Units, first-year discount convention, cost components, different price escalations, fixed pool/equipment/common annual costs, first-year capital, saved-choice price sensitivities versus re-optimization. |
| Reports & limits | Ranked choices, physical action ledgers, package accounting, CSV/JSON evidence, historical snapshots, scope confirmations and unsupported technologies/procedures. |
| Primary sources | Existing official regulatory and Commission guidance links retained, with direct wind citations inside the wind section. |

Implementation checked: `portal/engine/schema.py`, `wind.py`, `rules.py`,
`calculator.py`, `leg_optimizer.py`, vessel fields and wind/strategy/report
templates. The [wind accounting contract](WIND_ASSISTANCE.md) supplies additional
equations and independent examples.

The strategy-search explanation was subsequently rewritten as six plain-language
steps: cost objective, four policies, chosen variables, constraints, search
procedure, and reading the result. It includes present-cost and saving formulas,
the shared energy-weighted switch limit, and simple EUR/percentage examples.
It distinguishes the initial grid from continuous refinement, explains fixed
multi-year decisions and wind starts, and retains the no-global-optimum limit.
The explanation was checked against `optimize_fuels`, `optimize_legs`, `simulate`
and the report's first-step comparisons. Eight existing voyage-leg/financial
regression checks and the desktop/mobile disclosure browser workflow passed.
The running local page and its new formulas were also inspected at desktop and
mobile widths. Calculation code was not changed by this clarification.
The first three search steps now also distinguish the original-energy grid from
the 50-interval adjustment grid, explain replacement transfers at a full ship
limit, and illustrate supply/allocation/compliance thresholds and the RFNBO
reward change. The 7.5% endpoint, 0.4-percentage-point interval and 20% transfer
examples were checked, and the expanded section was viewed in the running app.

The official [Commission Q&A, Annex I A.2–A.3](https://transport.ec.europa.eu/transport-modes/maritime/decarbonising-maritime-transport-fueleu-maritime/questions-and-answers-regulation-eu-20231805-use-renewable-and-low-carbon-fuels-maritime-transport_en)
was rechecked for the separate wind-intensity reward and assessed effective
power. The guide retains the previously reviewed Commission guidance section
4.5/Table 4.12 for the discrete bands. Its PDF could not be retrieved again by
the web tool during this follow-up. This is a coverage/clarity update; the
[1 October source review](SANITY_CHECK_2026-10-01.md) remains separately dated.

## Verification

- 39 portal, wind-accounting and static-asset regression tests passed.
- The existing desktop/mobile disclosure browser workflow passed, extended to
  check all 13 sections, visible wind discovery, each shortcut, same-hash reopen,
  direct wind navigation, the reward table, no mobile page overflow, and printing
  all sections while restoring the reader's open/closed state.
- Desktop/mobile layouts and the expanded mobile wind explanation were visually
  inspected. Screenshots and the print sample are under the ignored
  `test-artifacts/compact-sections/` directory.
- Django system checks passed.
- Static assets were collected. A read-only request to the running local app at
  `http://127.0.0.1:8000/methodology/` returned HTTP 200 with the 2 October guide
  stamp, wind anchor and all 13 section headings.

No calculation or regulatory factor was changed in this follow-up. Engine
6.8.1 and ruleset EU-2026-10-01-review remain in place. The running local app was
verified; no remote deployment was performed.
