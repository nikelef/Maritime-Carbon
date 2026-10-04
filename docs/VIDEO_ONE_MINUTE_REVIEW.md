# Maritime Carbon — one-minute edition

The new file is `Maritime_Carbon_One_Minute.mp4` in the repository root.
The original `Maritime_Carbon.mp4` is preserved. All inputs in this edition are
fictional, and the displayed prices are illustrative assumptions.

## Editorial structure

| Time | Purpose |
| --- | --- |
| 0:00–0:05 | Brief title: a clearer route to carbon costs. |
| 0:05–0:13 | Current fuels, pooling, fuel and shore-power choices, combined policy. |
| 0:13–0:22 | Demo Aurora's conventional-fuel starting point. |
| 0:22–0:31 | Eligible FAME and already-installed shore power. |
| 0:31–0:40 | Four evaluated costs and the reference comparison. |
| 0:40–0:50 | Selected physical actions and absence of external pooling. |
| 0:50–0:55 | A traceable decision based on the user's assumptions. |

The seven scenes total **55.20 seconds**. Large graphics carry the story; focused
captures of the actual application show the input and report evidence. The voice
is synthetic British English (`en-GB-RyanNeural`), with natural pauses and no
speech acceleration in post-production. Only fictional narration text is sent
to the speech service. The production source is in `scripts/video/short_film.py`.

## Fictional case

One 30,000 GT cargo ship, **Demo Aurora**, for the single year **2026**. The annual
consumption is grouped under Voyage 1 for this demonstration.

| Fuel / leg | Baseline consumption |
| --- | ---: |
| VLSFO, intra-EU sea | 400 t |
| VLSFO, extra-EU sea | 1,000 t |
| MGO, intra-EU sea | 50 t |
| MGO, extra-EU sea | 50 t |
| MGO, EU berth | 40 t |

Assumed prices: VLSFO EUR 575/t; MGO EUR 720/t; FAME EUR 1,050/t;
electricity EUR 140/MWh; EU allowances EUR 90/tCO2e; external FuelEU surplus
EUR 250/tCO2e of compliance balance. These are scenario inputs, not market quotes.

FAME has an assumed non-food/feed pathway of 25 gCO2e/MJ. FuelEU eligibility and
the separate ETS zero-rating conditions are assumed satisfied for this fictional
case. Technical compatibility is assumed checked. There is a 20% cap on
alternative sea energy; this is not a statement that a B20 blend is universally
approved. No real fuel certificate is represented.

Shore power is **already installed**: no new capital cost, EUR 2,000 additional
annual operating cost. It can replace 75% of EU-berth MGO. Generator efficiency
is 40% and shore-connection efficiency 95%. This is an optional planning case
for a cargo ship in 2026, not a claim of a universal legal OPS requirement.

## Reconciled result

Engine **6.8.1**, ruleset **EU-2026-10-01-review**.

| Evaluated policy | Total modelled 2026 cost |
| --- | ---: |
| Current fuels; settle residual deficits | EUR 1,255,598.54 |
| Current fuels plus external pooling | EUR 1,219,134.42 |
| Fuel and shore-power choices | EUR 1,191,461.96 |
| Fuel and shore-power choices, pooling allowed | EUR 1,191,461.96 |

The last two policies reach the same cost and require no external pooling. Both
remain visible in the film. The reference saving is **EUR 64,136.58**, or **5.1%**.
This is the app's total modelled cost, including fuel, electricity, ETS, FuelEU
settlement and entered implementation costs; it is not total vessel operating
cost or an ETS-only saving.

Selected quantities:

- **17.9642 t FAME**, shown as 18.0 t, replacing 15.5662 t MGO on the intra-EU
  sea leg. Substitution preserves energy at the entered fuel calorific values.
- **149.8246 MWh shore electricity**, shown as 149.8 MWh, replacing 30 t MGO
  at EU berth. The remaining 10 t berth MGO is retained.
- **No external pooling** and **EUR 0 modelled FuelEU GHG-intensity penalty**.

The narration rounds these to 18 tonnes, 150 MWh, EUR 1.19 million and roughly
EUR 64,000. The film labels the case illustrative and the result the lowest
evaluated option; it does not assert a guaranteed global optimum.

## Verification and reproduction

See `scripts/video/README.md` for the production commands. Dependencies used only
for video production are isolated in `.tmp/video-short-deps`.

`scripts.video.capture_short` passed against a temporary Django database. It
checks the inputs before filming and after the actual form save, replays every
strategy, verifies report costs, verifies saved results and the downloaded JSON
audit, and asserts no browser page errors. The eight vessel sections initially
appear closed in the capture, matching the updated interface.

The renderer checks that each measured narration fits its scene, inspects video
and audio streams, decodes the entire final MP4, measures audio loudness/peak,
and enforces the 60-second maximum. Layout previews and encoded frame samples
are retained for visual inspection. Detailed machine results are stored in
`video-artifacts/one-minute/qa/verification.json`.

Final checks passed: **55.20 seconds**, **3,626,941 bytes**, full audio/video decode,
and all seven narration clips within their scene boundaries. Measured output
audio is **-16.43 LUFS** with **-4.34 dBTP** true peak. The seven-scene layout sheet
and encoded comparison/action frames were visually inspected for legibility,
cropping and agreement with the app's numbers.

Delivery format: **1920 × 1080, 30 fps, H.264 video and 48 kHz stereo AAC audio**,
with fast-start MP4 layout. Audio normalization targets -16 LUFS and -1.5 dB
true peak. The root MP4 contains one video and one audio stream. Optional English
captions are stored separately in `video-artifacts/one-minute/optional-captions/`;
their sentence timings are approximate, derived from the measured scene speech.
The narration transcript is `video-artifacts/one-minute/Narration.txt`.

This production does not alter app calculations or publish anything externally.
The application UI and regulatory sanity review are documented separately in
[SANITY_CHECK_2026-10-01.md](SANITY_CHECK_2026-10-01.md).
