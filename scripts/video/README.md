# Maritime Carbon desktop pitch production

This workflow records real application interactions against Django's isolated test
database. It does not open or modify `workspace.sqlite3`. Fixtures are fictional.
The recording contains two vessels, prices and consumption entries, HVO assumptions,
the live comparison, leg recommendations and real CSV/JSON downloads.

## Reproduce on Windows

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
- Matching `.srt` files, with captions also burned into the video.
- `demo-inputs.json`, `demo-audit.json` and `demo-results.csv`: fictional case and frozen result evidence.
- `raw/walkthrough.webm`: original full-resolution browser capture, without post-production zoom or caption graphics.
- `capture.json` and `edit-timeline.json`: recording and final edit timings.
- `qa/`: representative encoded frames for visual review.

The first review cut has no voiceover or music. Browser recordings are silent.
The accompanying voiceover and LinkedIn text are drafts, not published messages.

The master trims navigation pauses and applies smooth zooms in post-production.
A cursor and click halo are added during capture. Application inputs and results
are never replaced with graphic mockups. Most fields are prepared before filming;
selected prices and consumption quantities are re-entered on screen.

Full video files are kept out of Git. Source scripts and documentation can be synced
normally; deliver the MP4s directly or through the owner's preferred file service.
