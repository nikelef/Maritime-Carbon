# Maritime Carbon desktop pitch production

This workflow records real application interactions against Django's isolated test
database. It does not open or modify `workspace.sqlite3`. Fixtures are fictional.
The latest recording contains one bulk carrier and Voyage 1 in 2026, the owner's
specified three-fuel consumption, HVO assumptions and the actual selected result.
See [the single-voyage review notes](../../docs/VIDEO_SINGLE_VOYAGE_REVIEW.md).

## Current pitch and earlier revisions

The current review edition adds four ranked strategy explanations, removes spoken
section numbers from the result descriptions, and ends with a narrated thank-you
page. After producing the opening and single-voyage cuts below, run:

```powershell
$env:PYTHONPATH='.tmp/video-deps'
.\.venv\Scripts\python.exe -m scripts.video.pitch_final prepare
$env:DJANGO_DEBUG='1'
.\.venv\Scripts\python.exe manage.py test scripts.video.capture_strategies --noinput
.\.venv\Scripts\python.exe -m scripts.video.pitch_final render
```

Outputs are `Maritime_Carbon_One_Voyage_2026_Final.mp4` and its `_Review.zip`
under `video-artifacts/single-voyage/`. The real strategy-card capture verifies
the four displayed costs against a fresh calculation and the saved audit. Speech
finishes before the next card appears. The original best-strategy click then
continues into the report, and the thank-you page follows the ledger. Duration is
approximately 2 minutes 15 seconds; opening and input clips are reused.

The latest pitch edition adds the original branded introduction, followed by
full-width welcome and dashboard pages, before this complete 80-second cut.
After producing the single-voyage cut below, run:

```powershell
$env:PYTHONPATH='.tmp/video-deps'
.\.venv\Scripts\python.exe -m scripts.video.pitch_opening prepare
$env:DJANGO_DEBUG='1'
.\.venv\Scripts\python.exe manage.py test scripts.video.capture_opening --noinput
.\.venv\Scripts\python.exe -m scripts.video.pitch_opening render
```

This creates `Maritime_Carbon_One_Voyage_2026_Pitch.mp4` and its `_Review.zip`
under `video-artifacts/single-voyage/`. Total duration is approximately 107 seconds.
The renderer verifies that the accepted walkthrough's compressed picture packets
are preserved, and retains its speech timing. The opening uses the same synthetic
voice and one visible caption layer. It does not reuse the old two-vessel data.

After installing the production dependencies below, run these commands in order:

```powershell
$env:PYTHONPATH='.tmp/video-deps'
.\.venv\Scripts\python.exe -m scripts.video.render_single prepare
$env:DJANGO_DEBUG='1'
$env:PLAYWRIGHT_CHANNEL='msedge'
.\.venv\Scripts\python.exe manage.py test scripts.video.capture_single --noinput
.\.venv\Scripts\python.exe -m scripts.video.render_single render
```

Speech preparation needs network access. The measured speech duration sets each
mouse-over hold, including a pause after speech finishes. The total is exactly 80
seconds. The last scenes select the lowest evaluated strategy, show sections 03
and 04, and open the ship-by-ship ledger. Browser checks verify the saved inputs,
audit and numerical result, including zero shore electricity.

Outputs are under `video-artifacts/single-voyage/`, with the narrated
`Maritime_Carbon_One_Voyage_2026.mp4` and matching `_Review.zip`. There is one
burned-in caption layer and no SRT file. The fixture and narration are in
`single_voyage.py`; `shot-plan.json`, `capture.json` and `edit-timeline.json`
retain the speech and picture timings. Frames for visual review are in `qa/`.

## Dependencies and earlier two-vessel version

The application environment needs Playwright and its FFmpeg recorder. Microsoft
Edge is used by default. Install production-only graphics tools into a separate
folder; they are not application dependencies:

```powershell
.\.venv\Scripts\python.exe -m playwright install ffmpeg
.\.venv\Scripts\python.exe -m pip install --target .tmp/video-deps imageio-ffmpeg Pillow
$env:DJANGO_DEBUG='1'
$env:PLAYWRIGHT_CHANNEL='msedge'
.\.venv\Scripts\python.exe manage.py test scripts.video.capture --noinput
$env:PYTHONPATH='.tmp/video-deps'
.\.venv\Scripts\python.exe scripts/video/render.py
.\.venv\Scripts\python.exe -m pip install --target .tmp/video-deps edge-tts
.\.venv\Scripts\python.exe -m scripts.video.narrate
```

Run each command only after the preceding command succeeds. The filming harness
contains deliberate pauses. Its checks compare the final saved inputs, engine
results and exported audit with the original fixture and independent calculation.
Any numerical caption change requires a fresh capture and verification.

The renderer uses Segoe UI from `C:/Windows/Fonts`. `VIDEO_FONT_DIR` and `FFMPEG_EXE`
can override the font directory and encoder executable. The production dependencies
are Pillow 12.3.0 and imageio-ffmpeg 0.6.0; Playwright uses the app's existing tooling.

## Outputs

Files are written under the ignored `video-artifacts/` directory:

- `Maritime_Carbon_Desktop_Demo.mp4`: 1920 × 1080, 30 fps, H.264, caption-led master.
- `Maritime_Carbon_Teaser_30s.mp4`: 30-second edit from the same footage.
- `_Narrated.mp4` versions: synthetic English narration timed to both cuts, with the same visible caption layer.
- Optional `.srt` files under `optional-captions/`. Keep them there: placing an identically named SRT beside a captioned MP4 can cause players to display duplicate subtitles.
- `Narration_transcript.txt` and `narration/voice-timing.json`: actual spoken text and timing checks.
- `demo-inputs.json`, `demo-audit.json` and `demo-results.csv`: fictional case and frozen result evidence.
- `raw/walkthrough.webm`: original full-resolution browser capture, without post-production zoom or caption graphics.
- `capture.json` and `edit-timeline.json`: recording and final edit timings.
- `qa/`: representative encoded frames for visual review.

Browser recordings and the original masters are silent. The narrated versions use
the synthetic British English voice `en-GB-RyanNeural`, via edge-tts 7.2.8. Set
`VIDEO_VOICE` to change it. Only fictional narration text is sent to the speech
service. The audio is normalized to a target of -16 LUFS with a -1.5 dB true-peak
limit. Narration fits within scene boundaries without overlapping speech.

The narration step copies the existing video stream unchanged, adds AAC audio,
and includes no selectable subtitle stream. It verifies the copied video hash,
duration and audio/video stream counts, and decodes both final videos completely.
The ZIP review package contains only narrated MP4s at its top level; optional
captions are in a subfolder. No voiceover or LinkedIn text has been published.

Speech tool documentation: https://github.com/rany2/edge-tts

The master trims navigation pauses and applies smooth zooms in post-production.
A cursor and click halo are added during capture. Application inputs and results
are never replaced with graphic mockups. Most fields are prepared before filming;
selected prices and consumption quantities are re-entered on screen.

Full video files are kept out of Git. Source scripts and documentation can be synced
normally; deliver the MP4s directly or through the owner's preferred file service.
