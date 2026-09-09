# Maritime Carbon — single-voyage video review

Current review edition: `Maritime_Carbon_One_Voyage_2026_Final.mp4` adds 20 seconds explaining all four evaluated strategies from lowest to highest cost before selecting the best option. The two HVO evaluations reach the same lowest cost; allowing pooling does not lead to a pooling purchase in this case. Current fuels with pooling cost EUR 1,613.55 more, and current fuels with penalties have the highest total cost. The pointer highlights each actual strategy card while its narration finishes.

The operating-choice narration now describes the ship replacing gas oil with HVO on the intra-EU leg directly. Spoken section numbers are removed from both the operating-choice and cost-breakdown descriptions. A seven-second branded “THANK YOU” page closes the video, with spoken thanks and an invitation to discuss the viewer's fleet. Total duration is approximately 2 minutes 15 seconds. The matching package is `Maritime_Carbon_One_Voyage_2026_Final_Review.zip`.

The retained pitch introduction uses the original “Which fuel. Which voyage leg. At what cost?” design with wording for one bulk carrier. It is followed by full-width recordings of the app's welcome and dashboard pages, with matching marketing narration and no zoom or crop. This 27.27-second opening previously led into the accepted 80-second walkthrough, for a total of approximately 1 minute 47 seconds. All input and result figures below remain the same.

The previous deliverables, `Maritime_Carbon_One_Voyage_2026_Pitch.mp4` and `Maritime_Carbon_One_Voyage_2026_Pitch_Review.zip`, remain in the same local output folder, alongside the original 80-second cut. The current edition retains the opening and input scenes, the real click selecting the best strategy, and the operating-choice and ledger content. The cost-breakdown hold is extended slightly to accommodate its revised narration without rushing.

This revision uses one fictional bulk carrier, Demo Atlas, one voyage and reporting year 2026 only. It replaces the earlier two-vessel video for review. The video has synthetic British English narration and one visible caption layer. No video has been published.

## Inputs shown

- Vessel: bulk carrier, 25,000 GT; Voyage 1 throughout.
- EUA price: EUR 85 per tonne CO2 equivalent.
- External pooling price: EUR 190 per tonne of FuelEU compliance balance.
- EU/non-EU sea consumption: HSFO 1,000 tonnes; VLSFO 100 tonnes; LSMGO 50 tonnes.
- Intra-EU sea consumption: HSFO 200 tonnes; VLSFO 50 tonnes; LSMGO 50 tonnes.
- EU berth consumption: LSMGO 30 tonnes only.
- HVO is the nominated alternative fuel. Shore electricity is disabled.

The app identifies LSMGO under its MGO / LSMGO fuel entry, with internal code MGO. The current consumption totals 1,480 tonnes. The user's “intra/outra” category is interpreted as EU/non-EU sea legs.

Other illustrative assumptions retain fuel prices of EUR 470/t for HSFO, EUR 575/t for VLSFO, EUR 720/t for MGO and EUR 1,550/t for HVO. HVO compatibility, FuelEU eligibility and separate ETS CO2 zero-rating eligibility are enabled with fictional evidence references. The alternative energy cap is 100%; the optimizer selects a much smaller quantity. Equal thermal efficiency and zero conversion costs apply. These are demonstration assumptions, not supplier or vessel certifications.

## Selected result

The lowest evaluated annual cost is EUR 1,001,422.09. The recommendation replaces 26.252 tonnes of MGO/LSMGO with 25.476 tonnes of HVO on Voyage 1's intra-EU sea leg. Replacement energy is supplied on that same leg.

Fuel costs are EUR 764,436.56 and ETS costs are EUR 236,985.53. The selected strategy has zero external pooling cost, zero FuelEU penalty and zero shore electricity use. It costs EUR 1,613.55 less than the current-fuel external-pooling strategy under these assumptions. Displayed values are rounded; the included audit retains full precision.

## Viewing sequence

The pointer highlights each relevant field and remains there until its narration finishes. Zooms settle before the explanation. The final scenes click the lowest-cost strategy, show “03 / THE OPERATING CHOICE”, show “04 / THE COMPLETE BREAKDOWN”, and open the “Ship-by-ship annual calculation ledger”. More time is allocated to these report sections.

The source is a real browser recording against an isolated Django test database. Most fields are prepared before filming. The saved calculation and downloaded audit are checked against the fixture and a separate engine invocation. User decision cases and saved reports are not modified.

## Deliverables and reproduction

- `Maritime_Carbon_One_Voyage_2026.mp4`: exactly 80 seconds, 1920 × 1080, 30 fps, H.264 picture and AAC narration.
- `Maritime_Carbon_One_Voyage_2026_Review.zip`: video, narration transcript, scenario inputs, calculation audit and these notes.
- Local output folder: `video-artifacts/single-voyage/`.
- Source and commands: [video production instructions](../scripts/video/README.md).

The MP4 contains no selectable subtitle stream and the package has no SRT file, preventing a second caption layer from being loaded alongside the visible captions. Speech is generated at a slightly slower rate and its measured duration determines each field's hold time; speech is not accelerated to fit the edit.
