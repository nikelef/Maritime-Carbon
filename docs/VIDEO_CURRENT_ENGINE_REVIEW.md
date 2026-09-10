# Maritime Carbon — current-engine video revision

This edition reruns the owner's single-voyage case with engine **6.7.0** and rule
set **EU-2026-09-10-r2**. It replaces the historical review film for current
calculations. Earlier MP4s, source recordings and audits are preserved.

## Requested changes

- “HVO is selected as the replacement fuel for this case”, followed by “But more
  options exist.” The actual replacement-fuel dropdown opens and scrolls through
  the available options. HVO stays selected.
- “The shore power is not considered as an option for this case.” The pointer
  highlights the unchecked “Evaluate shore power: ship and intended ports are
  compatible” field in the expanded shore-power assumptions.
- “Let's now compare the available strategies and identify which one gives the
  lower cost.” The actual comparison button is then clicked.
- Before the ship-by-ship annual ledger, the current allocation table opens:
  “Annual FuelEU allocation prioritizes HVO, then lower-intensity conventional
  fuels.” The pointer moves from HVO's allocated energy to MGO's allocated energy.

The brief allocation description is specific to this HVO case; it does not
describe the RFNBO reward ordering for other cases. See the current methodology
and [RFNBO/GWP verification](RFNBO_GWP_VERIFICATION.md) for that calculation.

## Fresh results

The fictional inputs remain one bulk carrier, Demo Atlas, Voyage 1, reporting
year 2026, EUA EUR 85/t and external pooling EUR 190/t of compliance balance.
Annual fuel consumption is HSFO 1,200 t, VLSFO 150 t and MGO/LSMGO 130 t, with the
same voyage and berth distribution as the original case. The rerun uses the
current default oil WtW factors. HVO eligibility and ETS treatment remain
illustrative assumptions supported by fictional evidence, with HVO WtW 20 g/MJ.

| Evaluated strategy | Annual cost |
| --- | ---: |
| HVO, pooling allowed but none used | EUR 1,002,106.93 |
| HVO without pooling | EUR 1,002,106.93 |
| Current fuels with pooling | EUR 1,003,833.12 |
| Current fuels with penalties | EUR 1,041,272.27 |

The two HVO policies have the same cost to currency precision. The first is the
selected result in this rerun; the video follows the actual displayed order.
The selected strategy replaces **27.590 t MGO** with **26.775 t HVO** on the
intra-EU sea leg. Fuel costs are **EUR 765,486.38**, ETS costs
**EUR 236,620.55**, and pooling, FuelEU penalty and shore-power use are zero.
Savings against current fuels with pooling are **EUR 1,726.18**.

Covered annual physical energy is **36,883,500 MJ**. The allocation is:

| Source | WtW gCO2e/MJ | Allocated FuelEU MJ |
| --- | ---: | ---: |
| HVO | 20.000 | 1,178,102.50 |
| MGO | 90.767 | 4,372,897.50 |
| HSFO | 91.744 | 31,332,500.00 |
| VLSFO | 91.744 | 0.00 |

HSFO and VLSFO have equal WtW under these inputs; fuel-code order breaks the tie.
Attained intensity is **89.3368 gCO2e/MJ**, equal to the 2026 target, and the raw
compliance balance is zero. Values shown are rounded; the audit keeps precision.
Allocation is annual accounting, separate from the physical replacement on the
intra-EU leg and ETS's proportional voyage scope.

## Production and checks

The branded opening is retained. Every subsequent input and result scene is
freshly recorded in the real app against an isolated Django test database.
Customer cases and reports are untouched. The recording checks the fixture,
fresh engine comparison, stored report and downloaded audit for equality. It
also checks all four card costs, each allocation row, the unchanged HVO selection,
unchecked shore-power option, zero electricity across all strategies, and the
absence of browser JavaScript errors.

The fuel picker uses the browser's `base-select` appearance, applied only by the
filming harness so the actual open picker is included in the browser recording.
The app's options, input values and production styles are not changed. A pointer
and focus outline are also recording annotations. Report tables retain the full
width; no figures are composited over the app.

Synthetic British English narration uses the existing Ryan voice at -4% rate.
Each shot is timed from measured speech, with a pause before the next explanation.
The film has one visible caption strip and no selectable subtitle stream. The
renderer checks sequence order, speech fit, resolution, frame rate, duration and
complete decoding. Representative encoded frames are retained for visual review.

## Deliverables

Folder: `video-artifacts/single-voyage/current-engine/`.

- `Maritime_Carbon_Updated.mp4`: the current narrated 1920 × 1080, 30 fps video,
  approximately **2 minutes 39 seconds** (159.07 seconds).
- `Maritime_Carbon_Updated_Review.zip`: video, timed narration, fixture, fresh
  audit, editing timeline and these notes.
- `qa/`: encoded review frames, including the dropdown before/after scrolling
  and the two allocation pointer positions.

Reproduction commands are in [the video README](../scripts/video/README.md).
Videos remain local and excluded from Git. No social-media publication occurs.
