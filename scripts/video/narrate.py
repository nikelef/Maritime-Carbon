"""Add synthetic English narration while preserving the single burned-in caption layer.

Run after capture/render: python -m scripts.video.narrate
Requires edge-tts in the isolated video dependency folder and network access.
Only the fictional narration text is sent to the speech service.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import wave
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED

import edge_tts
from scripts.video.render import FFMPEG, OUT, ROOT, run, seconds_in_video


VOICE = os.environ.get("VIDEO_VOICE", "en-GB-RyanNeural")
RATE = 48000
MASTER = [
    ("intro", "fleet", "Maritime Carbon. Which fuel, on which voyage leg, at what total cost? Let's compare two fictional vessels."),
    ("allowances", "pool_price", "Allowances: eighty-five euros per tonne. Pooling: one hundred and ninety euros per tonne of compliance balance."),
    ("atlas", "atlas_legs", "Demo Atlas uses eighty tonnes of M G O on intra-European legs, and twenty tonnes on E U to non E U legs."),
    ("alternative", "alternative", "Evaluate H V O within the vessel's technical and energy limits."),
    ("boreas", "boreas_legs", "Demo Boreas has its own voyage profile, including three hundred tonnes of very low sulphur fuel oil."),
    ("evidence", "evidence", "Fuel E U and E T S eligibility are checked separately."),
    ("calculate", "calculate", "Save the inputs, then compare the fleet's operating choices."),
    ("result", "result", "Here, the lowest evaluated option uses targeted H V O replacement."),
    ("policies", "policies", "Compare the alternatives against current fuels and pooling."),
    ("pool_result", "pool_result", "First, the current-fuel pooling option."),
    ("best_result", "best_result", "Targeted H V O saves around eighteen hundred and sixty-eight euros."),
    ("leg_remarks", "leg_remarks", "The recommendation identifies each vessel, voyage leg, and precise replacement quantity."),
    ("energy", "energy", "Replacement energy stays on the same leg."),
    ("audit", "audit", "Export the saved inputs and calculations, ready for review."),
    ("outro", "outro", "Maritime Carbon. Let's talk about your fleet."),
]
TEASER = [
    ("intro", 3, "Maritime Carbon."),
    ("fleet", 3, "Compare two fictional vessels."),
    ("atlas_legs", 4, "Record fuel consumption by voyage and leg."),
    ("alternative", 3, "Evaluate alternative fuels within technical limits."),
    ("calculate", 3, "Compare the fleet's operating choices."),
    ("best_result", 4, "Targeted H V O beats pooling in this example."),
    ("leg_remarks", 6, "See which ship, which voyage leg, and how much fuel to replace."),
    ("outro", 4, "Maritime Carbon. Let's talk about your fleet."),
]


async def speech(text):
    key = hashlib.sha256((VOICE + text).encode()).hexdigest()[:16]
    path = OUT / "narration" / f"{key}.mp3"
    if not path.exists():
        await edge_tts.Communicate(text, VOICE, rate="+0%").save(str(path))
    assert path.stat().st_size > 1000, f"Empty speech file: {path}"
    return path


async def narrate(name, timeline, duration):
    track = bytearray(round(duration * RATE) * 2)
    report = []
    for index, (start, end, text) in enumerate(timeline):
        source = await speech(text)
        clean = OUT / "narration" / f"{name}-{index:02d}-clean.wav"
        # Remove only quiet leading/trailing padding, preserving internal pauses.
        trim = "silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.04,areverse,silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.04,areverse"
        run(["-i", source, "-af", trim, "-ar", RATE, "-ac", "1", "-c:a", "pcm_s16le", clean])
        with wave.open(str(clean), "rb") as audio:
            speech_seconds = audio.getnframes() / RATE
        available = end-start
        tempo = max(1.0, speech_seconds / (available-.04))
        assert tempo <= 1.28, f"Shorten narration {name}/{index}: {tempo:.2f}x required ({text})"
        fitted = OUT / "narration" / f"{name}-{index:02d}.wav"
        run(["-i", clean, "-af", f"atempo={tempo:.6f},afade=t=in:d=0.008,apad,atrim=duration={available:.6f}",
             "-ar", RATE, "-ac", "1", "-c:a", "pcm_s16le", fitted])
        with wave.open(str(fitted), "rb") as audio:
            pcm = audio.readframes(audio.getnframes())
        begin = round(start*RATE)*2
        assert begin+len(pcm) <= len(track)
        track[begin:begin+len(pcm)] = pcm
        report.append(dict(start=start, end=end, text=text, original_speech_seconds=speech_seconds, tempo=tempo))
        print(f"VOICE {name}/{index:02}: {speech_seconds:.2f}s in {available:.2f}s; tempo {tempo:.2f}", flush=True)
    wav = OUT / "narration" / f"{name}-voice.wav"
    with wave.open(str(wav), "wb") as audio:
        audio.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        audio.writeframes(track)
    source = OUT / f"{name}.mp4"
    final = OUT / f"{name}_Narrated.mp4"
    run(["-i", source, "-i", wav, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ar", RATE, "-ac", "2",
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=7", "-t", duration, "-sn", "-dn",
         "-metadata", "comment=Synthetic English narration; illustrative fleet; single burned-in caption layer",
         "-movflags", "+faststart", final])
    run(["-i", final, "-f", "null", "-"])
    info = subprocess.run([FFMPEG, "-hide_banner", "-i", str(final)], capture_output=True, text=True).stderr
    assert len(re.findall(r"Stream #.*Video:", info)) == 1
    assert len(re.findall(r"Stream #.*Audio:", info)) == 1
    assert "Subtitle:" not in info
    assert abs(seconds_in_video(final)-duration) < .06
    # Copying the video stream preserves the existing upper caption pixels exactly.
    hashes = []
    for path in (source, final):
        result = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-map", "0:v:0", "-c", "copy", "-f", "hash", "-hash", "sha256", "-"], capture_output=True, text=True, check=True)
        hashes.append(result.stdout.strip())
    assert hashes[0] == hashes[1], "The captioned video stream changed"
    return final, report


async def main():
    (OUT / "narration").mkdir(exist_ok=True)
    captions = OUT / "optional-captions"
    captions.mkdir(exist_ok=True)
    # Keep separately selectable subtitles away from identically named MP4s so
    # players cannot auto-load a duplicate beneath the burned-in captions.
    for filename in ("Maritime_Carbon_Desktop_Demo.srt", "Maritime_Carbon_Teaser_30s.srt"):
        old = OUT / filename
        if old.exists():
            old.replace(captions / filename)
    cuts = json.loads((OUT / "edit-timeline.json").read_text(encoding="utf-8"))
    by_key = {c["key"]: c for c in cuts}
    master = [(by_key[first]["start"]+.13, by_key[last]["end"]-.13, text) for first, last, text in MASTER]
    first, first_report = await narrate("Maritime_Carbon_Desktop_Demo", master, cuts[-1]["end"])
    elapsed = 0
    teaser = []
    for key, duration, text in TEASER:
        teaser.append((elapsed+.13, elapsed+duration-.13, text))
        elapsed += duration
    second, second_report = await narrate("Maritime_Carbon_Teaser_30s", teaser, elapsed)
    qa = {"voice": VOICE, "synthetic_voice": True, "master": first_report, "teaser": second_report,
          "video_streams_unchanged": True, "subtitle_streams": 0, "audio_loudness_target_lufs": -16}
    (OUT / "narration" / "voice-timing.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")
    transcript = ["Maritime Carbon — synthetic English narration", f"Voice: {VOICE}", "", "FULL WALKTHROUGH", ""]
    transcript += [s[2] for s in master]
    transcript += ["", "30-SECOND TEASER", ""] + [s[2] for s in teaser]
    (OUT / "Narration_transcript.txt").write_text("\n\n".join(transcript), encoding="utf-8")
    package = OUT / "Maritime_Carbon_Video_Review_Package.zip"
    with ZipFile(package, "w") as archive:
        for path in (first, second, OUT / "Narration_transcript.txt", ROOT / "docs" / "VIDEO_REVIEW_NOTES.md",
                     OUT / "demo-inputs.json", OUT / "demo-audit.json", OUT / "demo-results.csv"):
            archive.write(path, path.name, compress_type=ZIP_STORED if path.suffix == ".mp4" else ZIP_DEFLATED)
        for path in captions.glob("*.srt"):
            archive.write(path, f"optional-captions/{path.name}", compress_type=ZIP_DEFLATED)
    print("Narrated videos and single-caption review package ready.", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
