# LinkedIn desktop pitch video — proposed production plan

Latest revision: [80-second single-voyage video](VIDEO_SINGLE_VOYAGE_REVIEW.md), using one bulk carrier in 2026, the owner's revised fuel quantities, and narration that finishes before the next field is shown. The earlier production status and concept below are retained as background.

Status: an approximately 82-second master and a 30-second teaser have been produced with synthetic English narration and one visible caption layer. Both use one consistent two-vessel HVO case throughout. Optional SRT files are kept separately to avoid duplicate subtitle display. See [review notes and draft LinkedIn text](VIDEO_REVIEW_NOTES.md) and [reproduction instructions](../scripts/video/README.md). The original concept below is retained as background. No publication or outreach has been performed.

## Recommended concept

A 75–90 second desktop demonstration: “Which fuel, on which voyage leg, at what total cost?” Use two fictional vessels and show real application interactions. Finish with a precise same-leg recommendation and a saved audit trail. Create a 1920×1080 master at 30 fps, with readable captions and an optional voiceover. These are proposed production settings, not a statement of LinkedIn upload limits.

The product claim should be “Compare modelled FuelEU and ETS costs under your assumptions”. Avoid “guaranteed lowest cost”, “certified compliance” or an unqualified real-world saving. Keep “Illustrative case · planning assumptions” visible during result scenes. Do not use customer names, real IMO numbers, private quotations or genuine supplier-certificate identifiers.

## Suggested storyboard

- 0–7 seconds: open on the report and the problem statement, “Fuel, allowances or pooling — which combination makes sense?” Hold a clean overview before moving back to the case.
- 7–18 seconds: show a case named “2026 fleet planning — illustrative demo”, with the reporting year, assumed EUA and pooling prices. Type only the essential figures at a readable speed; prefill the rest off-camera.
- 18–34 seconds: show Demo Atlas and Demo Boreas. On Atlas, add MGO on an intra-EU sea leg and on an EU/non-EU leg. Zoom toward the voyage, category and tonnes fields so the viewer can follow the data. Show Boreas already entered, then briefly open its berth/OPS settings.
- 34–44 seconds: show the nominated alternative and the evidence/technical review controls. Caption: “Reviewed assumptions. Separate FuelEU and ETS treatment.” Use explicit fictional references rather than suggesting the demo establishes certification.
- 44–50 seconds: click Save, then Compare strategies. Wait for the real calculation result. Edit out excess waiting time with a short visible cut rather than showing a fabricated instant result.
- 50–68 seconds: hold the cost comparison, then move to the strategy remarks. Zoom into “Voyage … Intra-EU sea: replace … MGO with … HVO/FAME”. Highlight that removed and replacement energy stay on the same leg. Read the actual values from the generated report.
- 68–78 seconds: select the current-fuel pooling policy and return to the selected operating strategy. Show the comparison in context, including any applicable partial-scope warning. Do not compare a reference from one input set with an optimized result from another.
- 78–88 seconds: click Audit file or Download CSV, then end on “From annual consumption to a traceable fleet decision.” Optional closing line: “Contact me for a walkthrough.”

## Data options

Option A, simplest story: use the guide's one-vessel HVO example first, with a second vessel prefilled only in a later scene. The one-vessel reference is reproducible and makes the small targeted replacement easy to understand. Clearly mark the transition to a two-vessel case; do not imply the one-vessel saving describes the combined fleet.

Option B, strongest fleet story: use the release fixture with two ships sharing FAME supply, a ship-specific bank and OPS. It shows that the application evaluates the fleet together. This requires a slightly longer explanation of internal pooling, so use only one main number and one leg recommendation in the video. Recalculate the final filming dataset and freeze its audit before drafting numerical captions.

## How I can produce it

Recommended: automate a repeatable desktop walkthrough with the app's existing Playwright test stack, using a dedicated temporary database. Record the browser context at full output resolution and save the actual actions as source footage. Playwright supports per-context video recording and saves the completed recording when the context closes. Its default recorder sizing must be overridden for crisp full-resolution UI. Source: https://playwright.dev/python/docs/videos

Then edit the source capture using FFmpeg: crop/scale for focus, controlled zoom/pan, trimmed pauses, crossfades, title and caption overlays, and an optional supplied voiceover. Slow cursor movements and click markers can be included in the capture or added consistently during editing. Zoom should be added in post-production so the app's real layout and values remain intact. Source: https://ffmpeg.org/ffmpeg-filters.html#zoompan

An alternative is a guided manual desktop recording followed by the same editing process. This allows more natural mouse motion but is harder to reproduce when a field label or result changes. A short silent caption-led version is the easiest first review artifact; narration can be added after the message and numbers are approved.

## Visual direction

- Capture only the application window, with a clean fictional workspace and no unrelated tabs, notifications, credentials or desktop files.
- Use one consistent focus style: a subtle pointer/click halo and restrained 1.25–1.6× zoom, with 0.5–0.8 second transitions and readable holds.
- Zoom out before navigating to another screen, then zoom into the next relevant control. Avoid rapid full-page scrolling or zooming while typing a number.
- Keep captions concise and away from the values being discussed. Explain one point per shot and leave several seconds for the leg recommendation.
- Preserve chart, strategy and ledger consistency. Exported audit figures are the numerical source of truth; visible currency is rounded by the app.

## Proposed deliverables for a later production task

- A 75–90 second MP4 desktop master and a 30-second teaser derived from the same approved story.
- A caption file, voiceover script and a draft LinkedIn post for the owner to review and publish.
- Reusable fictional input data, recording script, raw capture and editing instructions, so the video can be updated after product changes.

No mobile application testing or mobile UI footage is proposed. A different video aspect ratio can be considered later as an editing decision, independently of mobile app development.
