"""Prepend the original marketing style and full-width app pages to the approved cut."""
import asyncio
import hashlib
import json
import math
import re
import subprocess
import sys
import wave
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED

import edge_tts
from scripts.video.render import FFMPEG, ROOT, card, run, seconds_in_video
from scripts.video.render_single import caption_image
from scripts.video.single_voyage import OUT, VOICE

OPENING = OUT / "opening"
FPS, RATE = 30, 48000
SHOTS = [
    ("intro", "Which fuel. Which voyage leg. At what cost?",
     "Maritime Carbon. Which fuel, on which voyage leg, at what total cost?", 7),
    ("welcome", "Understand exposure. Compare options. Make a traceable decision.",
     "Better decisions. Lower carbon costs. Understand your exposure and compare your options in one workspace.", 8),
    ("overview", "One bulk carrier · One voyage · 2026 · A complete view of carbon costs",
     "Model your vessel. Compare the complete cost. Keep an auditable record. Let's explore one bulk carrier in twenty twenty-six.", 9),
]


async def prepare():
    OPENING.mkdir(exist_ok=True)
    shots = []
    for key, caption, text, preferred in SHOTS:
        digest = hashlib.sha256((VOICE+"-4%"+text).encode()).hexdigest()[:16]
        mp3 = OPENING / f"{digest}.mp3"
        if not mp3.exists():
            await edge_tts.Communicate(text, VOICE, rate="-4%").save(str(mp3))
        wav = OPENING / f"{key}.wav"
        trim = "silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.04,areverse,silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.04,areverse"
        run(["-i", mp3, "-af", trim, "-ar", RATE, "-ac", "1", "-c:a", "pcm_s16le", wav])
        with wave.open(str(wav), "rb") as audio:
            speech = audio.getnframes()/RATE
        frames = math.ceil(max(preferred, speech+1)*FPS)
        shots.append(dict(key=key, caption=caption, text=text, speech_seconds=speech,
                          lead=.5, frames=frames, duration=frames/FPS))
    (OPENING / "plan.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")
    print(f"Opening: {sum(s['duration'] for s in shots):.2f}s; full video: {80+sum(s['duration'] for s in shots):.2f}s")


def render():
    shots = json.loads((OPENING / "plan.json").read_text())
    capture = json.loads((OPENING / "capture.json").read_text())
    raw = OPENING / "walkthrough.webm"
    offset = capture["recording_wall_seconds"]-seconds_in_video(raw)
    assert abs(offset) < 2
    scenes = {s["key"]:s for s in capture["scenes"]}
    clips, timeline = [], []
    opening_seconds = sum(s["duration"] for s in shots)
    duration = opening_seconds+80
    track = bytearray(round(duration*RATE)*2)
    elapsed = 0
    for s in shots:
        clip = OPENING / f"{s['key']}.mp4"
        if s["key"] == "intro":
            picture = card("intro", example_line="One bulk carrier. One voyage. A real app walkthrough.",
                           destination=OPENING / "intro.png")
            inputs = ["-loop", "1", "-framerate", FPS, "-i", picture]
            filters = ["-vf", "format=yuv420p"]
        else:
            # Full viewport, with no crop or post-production zoom.
            inputs = ["-ss", max(0, scenes[s["key"]]["start"]-offset), "-i", raw,
                      "-loop", "1", "-framerate", FPS, "-i", caption_image(s)]
            filters = ["-filter_complex", "[0:v]fps=30,scale=1920:960,pad=1920:1080:0:0:color=0x102e32[v];[v][1:v]overlay=0:0:format=auto,format=yuv420p[out]", "-map", "[out]"]
        run([*inputs, *filters, "-frames:v", s["frames"], "-c:v", "libx264", "-preset", "fast",
             "-crf", "18", "-threads", "4", "-an", clip])
        clips.append(clip)
        with wave.open(str(OPENING / f"{s['key']}.wav"), "rb") as audio:
            pcm = audio.readframes(audio.getnframes())
        begin = round((elapsed+s["lead"])*RATE)*2
        assert begin+len(pcm) <= round((elapsed+s["duration"]-.45)*RATE)*2
        track[begin:begin+len(pcm)] = pcm
        timeline.append(s | dict(output_start=elapsed, output_end=elapsed+s["duration"]))
        elapsed += s["duration"]
        print(f"OPENING {s['key']}: {s['duration']:.2f}s", flush=True)
    # Copy the entire accepted 80-second picture and original uncompressed voice.
    clips.append(OUT / "picture.mp4")
    with wave.open(str(OUT / "speech" / "narration.wav"), "rb") as audio:
        pcm = audio.readframes(audio.getnframes())
        assert audio.getnframes() == 80*RATE
    track[round(opening_seconds*RATE)*2:] = pcm
    playlist = OPENING / "concat.txt"
    playlist.write_text("".join(f"file '{p.as_posix()}'\n" for p in clips), encoding="utf-8")
    silent = OPENING / "picture.mp4"
    run(["-f", "concat", "-safe", "0", "-i", playlist, "-c", "copy", silent])
    wav = OPENING / "narration.wav"
    with wave.open(str(wav), "wb") as audio:
        audio.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        audio.writeframes(track)
    final = OUT / "Maritime_Carbon_One_Voyage_2026_Pitch.mp4"
    run(["-i", silent, "-i", wav, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ar", RATE, "-ac", "2", "-af", "loudnorm=I=-16:TP=-1.5:LRA=7",
         "-t", duration, "-sn", "-movflags", "+faststart", final])
    run(["-i", final, "-f", "null", "-"])
    assert abs(seconds_in_video(final)-duration) < .05
    meta = subprocess.run([FFMPEG, "-hide_banner", "-i", str(final)], capture_output=True, text=True).stderr
    assert re.findall(r"Stream #0:\d+.*?: (Video|Audio|Subtitle):", meta) == ["Video", "Audio"]
    # Verify compressed picture packets from the walkthrough were preserved.
    def picture_hash(path, seek=None):
        args = [FFMPEG, "-v", "error"]
        if seek is not None:
            args += ["-ss", str(seek)]
        args += ["-i", str(path), "-map", "0:v:0", "-c", "copy", "-f", "hash", "-hash", "sha256", "-"]
        return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()
    assert picture_hash(OUT / "picture.mp4") == picture_hash(final, opening_seconds)
    original = json.loads((OUT / "edit-timeline.json").read_text(encoding="utf-8"))
    timeline += [s | dict(output_start=s["output_start"]+opening_seconds,
                         output_end=s["output_end"]+opening_seconds) for s in original]
    (OPENING / "edit-timeline.json").write_text(json.dumps(timeline, indent=2, ensure_ascii=False), encoding="utf-8")
    transcript = OPENING / "Narration.txt"
    transcript.write_text("Synthetic British English narration. One visible caption layer.\n\n"+"\n\n".join(s["text"] for s in timeline), encoding="utf-8")
    for i, s in enumerate(timeline):
        if i<4 or s["key"] in ("operating", "breakdown", "ledger"):
            run(["-ss", (s["output_start"]+s["output_end"])/2, "-i", final, "-frames:v", "1", OPENING / f"qa-{s['key']}.png"])
    package = OUT / "Maritime_Carbon_One_Voyage_2026_Pitch_Review.zip"
    with ZipFile(package, "w") as archive:
        for p in (final, transcript, OUT / "demo-audit.json", OUT / "demo-inputs.json", ROOT / "docs" / "VIDEO_SINGLE_VOYAGE_REVIEW.md"):
            archive.write(p, p.name, compress_type=ZIP_STORED if p.suffix==".mp4" else ZIP_DEFLATED)
    print(f"READY {duration:.2f}s: {final}; accepted walkthrough picture preserved", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        asyncio.run(prepare())
    elif sys.argv[1] == "render":
        render()
